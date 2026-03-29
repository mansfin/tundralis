from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import traceback
import uuid
from functools import wraps
from pathlib import Path

from flask import Flask, Response, abort, jsonify, render_template, request, send_from_directory, url_for
import csv
import io

from tundralis.analysis import run_kda
from tundralis.charts import chart_importance_bar, chart_model_fit, chart_quadrant
from tundralis.ingestion import load_mapping_config, resolve_config, validate_resolved_config
from tundralis.prep import build_prep_bundle
from tundralis.utils import prepare_sparse_model_data

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "app_runtime"
UPLOAD_DIR = RUNTIME_DIR / "uploads"
MAPPING_DIR = RUNTIME_DIR / "mappings"
ARTIFACT_DIR = RUNTIME_DIR / "artifacts"
INSPECT_ERROR_LOG = RUNTIME_DIR / "inspect-errors.log"
REQUEST_ERROR_LOG = RUNTIME_DIR / "request-errors.log"
for p in [UPLOAD_DIR, MAPPING_DIR, ARTIFACT_DIR]:
    p.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, template_folder=str(ROOT / "web" / "templates"), static_folder=str(ROOT / "web" / "static"))

MAX_INLINE_COLUMN_PROFILES = 40


class Args:
    target = None
    predictors = None


def _auth_ok() -> bool:
    required_user = os.environ.get("TUNDRALIS_BASIC_AUTH_USER")
    required_pass = os.environ.get("TUNDRALIS_BASIC_AUTH_PASS")
    if not required_user or not required_pass:
        return True
    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
        user, pw = decoded.split(":", 1)
    except Exception:
        return False
    return user == required_user and pw == required_pass


def _require_auth():
    return Response("Authentication required", 401, {"WWW-Authenticate": 'Basic realm="tundralis"'})


def basic_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not _auth_ok():
            return _require_auth()
        return view(*args, **kwargs)
    return wrapped


def _job_dir(job_id: str) -> Path:
    p = ARTIFACT_DIR / job_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _mapping_path(job_id: str) -> Path:
    return MAPPING_DIR / f"{job_id}.json"


def _parse_json_field(value: str | None) -> list[dict]:
    try:
        return json.loads(value) if value else []
    except json.JSONDecodeError:
        return []


TARGET_KEYWORDS_STRONG = [
    "overall_sat", "overall satisfaction", "overall_satisfaction", "satisfaction", "sat",
    "recommend", "likelihood_to_recommend", "nps", "recommendation", "experience", "value",
]
TARGET_KEYWORDS_WEAK = ["overall", "brand", "rating", "score"]
TARGET_KEYWORDS_CANONICAL_OUTCOME = [
    "nps", "recommend", "likelihood_to_recommend", "engagement", "index", "overall_sat", "overall_satisfaction", "overall_experience",
]
ATTRIBUTE_STYLE_TOKENS = [
    "quality", "support", "friendliness", "handling", "checkin", "ease", "reliability", "tools", "setup", "reporting", "recognition", "growth", "workload", "feature", "implementation", "trust", "bag", "staff", "fare",
]
CANONICAL_OUTCOME_BONUS_TOKENS = [
    "engagement_index", "nps_score", "overall_experience", "overall_sat", "overall_satisfaction", "likelihood_to_recommend",
]
DEFAULT_RECOMMENDED_DRIVER_LIMIT = 24
MAX_PER_FAMILY = 3
EXCLUSION_REASON_LABELS = {
    "likely_identifier": "Likely ID",
    "high_cardinality": "High-cardinality field",
    "high_missingness": "High missingness",
    "mixed_numeric_text": "Mixed numeric/text",
    "text": "Open text or free text",
    "categorical": "Categorical metadata field",
    "meta_candidate": "Better treated as segment/metadata",
    "admin": "Administrative/system field",
    "derived_target": "Looks derived from the outcome",
    "target": "Selected outcome",
    "family_overrepresented": "Too many similar fields in this family",
    "shortlist_overflow": "Not in default shortlist",
    "weak_family": "Lower-priority field family",
    "text_artifact": "Text/open-end artifact",
    "geo_artifact": "Geography/postal artifact",
    "battery_artifact": "Question battery artifact",
    "opaque_code": "Opaque code-style field",
    "choice_order_artifact": "Choice/display-order artifact",
}




def _semantic_text(column: str, profile: dict) -> str:
    return str(profile.get("semantic_text") or profile.get("question_text") or column).lower()


def _clean_label_text(text: str | None) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    value = re.sub(r'\s+', ' ', value)
    value = re.sub(r'^[QSV]\d+(?:\.\d+)?\s*[\-:|]?\s*', '', value, flags=re.IGNORECASE)
    value = re.sub(r'\b(importid|question text|display order|selected choice|choice order)\b.*$', '', value, flags=re.IGNORECASE)
    value = value.strip(' -|:_')
    return value.strip()


def _recommended_display_label(column: str, profile: dict) -> str | None:
    question_text = _clean_label_text(profile.get("question_text"))
    semantic_text = _clean_label_text(profile.get("semantic_text"))
    inferred_type = profile.get("inferred_type", "")

    candidates = [question_text, semantic_text]
    for candidate in candidates:
        if not candidate:
            continue
        lower = candidate.lower()
        if lower == column.lower():
            continue
        if _looks_like_vendor_plumbing(candidate) or _looks_like_choice_order_artifact(candidate):
            continue
        if len(candidate) < 6:
            continue
        if inferred_type in {"numeric", "numeric_like_text", "categorical"}:
            return candidate
    return None


def _looks_like_descriptive_construct(column: str, profile: dict) -> bool:
    lower = _semantic_text(column, profile)
    inferred_type = profile.get("inferred_type", "")
    warnings = set(profile.get("warnings", []))
    descriptive_tokens = [
        "support", "manager", "workload", "growth", "recognition", "quality", "value",
        "trust", "ease", "tools", "systems", "friendliness", "experience", "opportunities",
    ]
    if inferred_type not in {"numeric", "numeric_like_text"}:
        return False
    if "likely_likert_or_coded_categorical" not in warnings:
        return False
    if any(token in lower for token in descriptive_tokens):
        return True
    return False

def _is_admin_like(column: str) -> bool:
    lower = column.lower()
    admin_tokens = [
        "startdate", "enddate", "recordeddate", "status", "ipaddress", "recipient", "email", "phone",
        "externalreference", "latitude", "longitude", "distributionchannel", "userlanguage", "duration",
        "progress", "finished", "location", "fraud", "duplicate", "responseid", "respondentid",
    ]
    return any(token in lower for token in admin_tokens)


def _column_family(column: str) -> str:
    lower = column.lower()
    normalized = lower.replace("-", "_").replace(".", "_")
    normalized = re.sub(r"_+", "_", normalized)
    normalized = re.sub(r"(_?\d+)+$", "", normalized)
    normalized = re.sub(r"^q\d+_?", "q", normalized)
    normalized = re.sub(r"^v\d+$", "v_generic", normalized)
    return normalized.strip("_") or lower


def _is_low_signal_code_name(column: str) -> bool:
    lower = column.lower()
    return bool(
        re.fullmatch(r"v\d+", lower)
        or re.fullmatch(r"q\d+(?:_\d+)+", lower)
        or re.fullmatch(r"q\d+", lower)
        or re.fullmatch(r"s\d+(?:_\d+)?", lower)
        or re.fullmatch(r"[a-z]{1,3}", lower)
    )


def _looks_like_brand_tracker_debris(column: str) -> bool:
    lower = column.lower()
    debris_tokens = [
        "alaska", "allegiant", "american", "breeze", "frontier", "hawaiian", "jetblue",
        "delta", "southwest", "spirit", "united", "sun country", "sun_country",
    ]
    if lower in {token.replace(" ", "_") for token in debris_tokens} or lower in {token.replace(" ", "") for token in debris_tokens} or lower in debris_tokens:
        return True
    if lower.startswith("seg_") or re.fullmatch(r"seg[_-]?[a-z0-9]+", lower):
        return True
    if re.fullmatch(r"q\d+(?:\.\d+)?(?:_[a-z0-9]+)?(?:fav|unfav)", lower):
        return True
    return False


def _looks_like_text_artifact(column: str) -> bool:
    lower = column.lower()
    return any(token in lower for token in ["_text", "text_", "free_text", "comment", "openend", "open_end", "specify", "verbatim"])


def _looks_like_geo_artifact(column: str) -> bool:
    lower = column.lower()
    return bool(re.fullmatch(r"zip\d*", lower) or any(token in lower for token in ["postal", "zipcode", "zip_code", "state", "county", "dma", "msa", "geo"]))


def _looks_like_battery_artifact(column: str) -> bool:
    lower = column.lower()
    return bool(re.fullmatch(r"q\d+(?:\.\d+)?_\d+_text", lower) or re.fullmatch(r"q\d+(?:\.\d+)?_\d+", lower))


def _looks_like_vendor_plumbing(column: str) -> bool:
    lower = column.lower()
    vendor_tokens = [
        "purespectrum", "redirecturl", "redirect_url", "transaction_id", "signaturevalue",
        "session_id", "panelist", "panel_id", "vendor", "supplier", "sample_source",
    ]
    return any(token in lower for token in vendor_tokens)


def _looks_like_choice_order_artifact(column: str) -> bool:
    lower = column.lower()
    return bool(
        re.fullmatch(r"[a-z]?q?\d+_do_\d+", lower)
        or re.fullmatch(r"s\d+_do_\d+", lower)
        or re.fullmatch(r"q\d+_do", lower)
        or "display order" in lower
        or lower.endswith("_do")
    )


def _looks_like_segment_meta_candidate(column: str, profile: dict) -> bool:
    lower = column.lower()
    warnings = set(profile.get("warnings", []))
    distinct = int(profile.get("distinct_count", 0) or 0)
    inferred_type = profile.get("inferred_type", "")
    if _looks_like_descriptive_construct(column, profile):
        return False
    meta_tokens = [
        "segment", "wave", "cohort", "market", "region", "department", "location",
        "country", "state", "team", "role", "title", "persona", "industry", "size",
        "company_size", "employee_count", "age", "gender", "tenure", "function", "gc",
    ]
    if any(token in lower for token in meta_tokens):
        return True
    if _looks_like_choice_order_artifact(column) or 'display order' in lower:
        return True
    if inferred_type == "categorical" and 2 <= distinct <= 20 and (lower.startswith("s") or lower.startswith("demo_")):
        return True
    if inferred_type in {"numeric", "numeric_like_text"} and distinct <= 12 and lower.endswith("_do"):
        return True
    if inferred_type in {"categorical", "numeric_like_text"} and _is_low_signal_code_name(column) and distinct <= 20 and (lower.startswith("s") or len(lower) <= 3):
        return True
    if inferred_type == "categorical" and "likely_likert_or_coded_categorical" not in warnings and 2 <= distinct <= 20 and len(lower) <= 5 and '_' not in lower and ' ' not in lower:
        return True
    return False


def _interpretability_score(column: str) -> float:
    lower = column.lower()
    score = 0.0
    if _is_low_signal_code_name(column):
        score -= 6
    if lower.startswith('v') and re.fullmatch(r'v\d+', lower):
        score -= 8
    if lower.startswith('q') and re.fullmatch(r'q\d+(?:\.\d+)?(?:_\d+)?', lower):
        score -= 5
    if _looks_like_text_artifact(column) or _looks_like_geo_artifact(column) or _looks_like_battery_artifact(column):
        score -= 6
    if len(re.sub(r'[^a-z]+', '', lower)) >= 8:
        score += 4
    if any(token in lower for token in ['satisfaction', 'recommend', 'sentiment', 'effort', 'appeal', 'feeling', 'reason', 'type', 'quality', 'value']):
        score += 4
    if '_' in lower or '-' in lower or ' ' in lower:
        score += 1
    return score


def _family_score(family: str, items: list[dict]) -> float:
    score = 0.0
    descriptive = family not in {"q", "v_generic"} and len(family) >= 6
    if descriptive:
        score += 6
    if family in {"q", "v_generic"}:
        score -= 6
    if any("likely_likert_or_coded_categorical" in item.get("warnings", []) for item in items):
        score += 3
    if any(_looks_like_brand_tracker_debris(item["name"]) for item in items):
        score -= 5
    score += min(len(items), 4)
    score += sum(item.get("score", 0) for item in items[:3]) / 6
    return round(score, 2)


def _target_score(column: str, profile: dict) -> float:
    lower = _semantic_text(column, profile)
    inferred_type = profile.get("inferred_type", "")
    warnings = set(profile.get("warnings", []))
    distinct = int(profile.get("distinct_count", 0) or 0)
    missing_pct = float(profile.get("missing_pct", 0) or 0)
    non_null = int(profile.get("non_null_count", 0) or 0)

    if inferred_type not in {"numeric", "numeric_like_text"}:
        return -999
    if "likely_identifier" in warnings or _is_admin_like(column):
        return -999
    if _looks_like_text_artifact(column) or _looks_like_text_artifact(lower):
        return -999
    if any(token in lower for token in ["other (please specify)", "other please specify", "open end", "free text", "verbatim"]):
        return -999
    if _looks_like_choice_order_artifact(column) or 'display order' in lower or 'selected choice' in lower:
        return -999
    if _looks_like_vendor_plumbing(column) or _looks_like_vendor_plumbing(lower):
        return -999
    if non_null < 25 or distinct < 2:
        return -999

    score = 0.0
    if any(token in lower for token in TARGET_KEYWORDS_STRONG):
        score += 12
    if any(token in lower for token in TARGET_KEYWORDS_WEAK):
        score += 4
    if any(token in lower for token in TARGET_KEYWORDS_CANONICAL_OUTCOME):
        score += 5
    if any(token in lower for token in CANONICAL_OUTCOME_BONUS_TOKENS):
        score += 6
    if any(token in lower for token in ["index", "engagement", "overall_experience", "overall_value"]):
        score += 3
    if "likely_likert_or_coded_categorical" in warnings:
        score += 3
    if 3 <= distinct <= 11:
        score += 4
    if missing_pct <= 20:
        score += 2
    if distinct > 40:
        score -= 4
    if _looks_like_brand_tracker_debris(column) or _looks_like_brand_tracker_debris(lower):
        score -= 8
    if _looks_like_vendor_plumbing(column) or _looks_like_vendor_plumbing(lower):
        score -= 14
    if _looks_like_choice_order_artifact(column) or 'display order' in lower:
        score -= 14
    if _looks_like_segment_meta_candidate(column, profile) or _looks_like_segment_meta_candidate(lower, profile):
        score -= 8
    if distinct <= 3 and not any(token in lower for token in TARGET_KEYWORDS_CANONICAL_OUTCOME) and _is_low_signal_code_name(column):
        score -= 6
    if any(token in lower for token in ATTRIBUTE_STYLE_TOKENS) and not any(token in lower for token in TARGET_KEYWORDS_CANONICAL_OUTCOME):
        score -= 3
    if lower.startswith('q') or lower.startswith('v') or re.fullmatch(r's\d+(?:_\d+)?', lower):
        score -= 5
    if _is_low_signal_code_name(column):
        score -= 5
    if "text" in lower or "comment" in lower or "open" in lower:
        score -= 8
    score += _interpretability_score(column)
    return score


def _detect_target(columns: list[str], numeric_columns: list[str], column_profiles: dict[str, dict]) -> str | None:
    scored = []
    for col in columns:
        profile = column_profiles.get(col, {})
        score = _target_score(col, profile)
        if score > -999:
            scored.append((score, col))
    scored.sort(key=lambda item: (-item[0], item[1]))
    if scored and scored[0][0] >= 2:
        return scored[0][1]
    fallback = []
    for col in numeric_columns:
        if _is_admin_like(col):
            continue
        profile = column_profiles.get(col, {})
        if _target_score(col, profile) <= -999:
            continue
        if _looks_like_choice_order_artifact(col) or _looks_like_segment_meta_candidate(col, profile):
            continue
        if _is_low_signal_code_name(col):
            continue
        fallback.append(col)
    return fallback[0] if fallback else None


def _predictor_score(column: str, profile: dict, inferred_target: str | None) -> float:
    lower = _semantic_text(column, profile)
    inferred_type = profile.get("inferred_type", "")
    warnings = set(profile.get("warnings", []))
    distinct = int(profile.get("distinct_count", 0) or 0)
    missing_pct = float(profile.get("missing_pct", 0) or 0)
    family = _column_family(column)
    score = 0.0

    if inferred_type in {"numeric", "numeric_like_text"}:
        score += 4
    if "likely_likert_or_coded_categorical" in warnings:
        score += 5
    if 3 <= distinct <= 11:
        score += 2
    if missing_pct <= 20:
        score += 1
    if _is_admin_like(column):
        score -= 8
    if "likely_identifier" in warnings:
        score -= 10
    if inferred_type == "text":
        score -= 8
    if inferred_type == "mixed":
        score -= 6
    if "high_cardinality" in warnings and inferred_type not in {"numeric", "numeric_like_text"}:
        score -= 4
    if inferred_target:
        target_lower = inferred_target.lower()
        target_family = _column_family(inferred_target)
        if lower == target_lower:
            score -= 12
        if target_lower in lower or lower in target_lower:
            score -= 5
        if family == target_family:
            score -= 6
    if any(token in lower for token in ["other", "specify", "text", "open end", "comment", "selected choice"]):
        score -= 8
    if _looks_like_text_artifact(column) or _looks_like_text_artifact(lower):
        score -= 10
    if _looks_like_geo_artifact(column) or _looks_like_geo_artifact(lower):
        score -= 9
    if _looks_like_battery_artifact(column) or _looks_like_battery_artifact(lower):
        score -= 7
    if _looks_like_choice_order_artifact(column) or 'display order' in lower:
        score -= 12
    if _looks_like_segment_meta_candidate(column, profile) or _looks_like_segment_meta_candidate(lower, profile):
        score -= 7
    if _looks_like_brand_tracker_debris(column) or _looks_like_brand_tracker_debris(lower):
        score -= 9
    if _looks_like_vendor_plumbing(column) or _looks_like_vendor_plumbing(lower):
        score -= 15
    score += _interpretability_score(column)
    if family in {"q", "v_generic"}:
        score -= 4
    if len(family) >= 6 and not _is_low_signal_code_name(column):
        score += 2
    return score


def _predictor_recommendation(column: str, profile: dict, inferred_target: str | None) -> tuple[bool, list[str], str, float]:
    if column == inferred_target:
        return False, ["target"], "numeric", -999

    inferred_type = profile.get("inferred_type", "")
    warnings = set(profile.get("warnings", []))
    lower = column.lower()
    reasons = []

    if _is_admin_like(column):
        reasons.append("admin")
    if "likely_identifier" in warnings:
        reasons.append("likely_identifier")
    if "high_cardinality" in warnings and inferred_type not in {"numeric", "numeric_like_text"}:
        reasons.append("high_cardinality")
    if inferred_type == "text":
        reasons.append("text")
    if inferred_type == "mixed":
        reasons.append("mixed_numeric_text")
    if _looks_like_text_artifact(column) or _looks_like_text_artifact(lower):
        reasons.append("text_artifact")
    if _looks_like_geo_artifact(column) or _looks_like_geo_artifact(lower):
        reasons.append("geo_artifact")
    if _looks_like_battery_artifact(column) or _looks_like_battery_artifact(lower):
        reasons.append("battery_artifact")
    if _looks_like_choice_order_artifact(column):
        reasons.append("choice_order_artifact")
    if _looks_like_segment_meta_candidate(column, profile) or _looks_like_segment_meta_candidate(lower, profile):
        reasons.append("meta_candidate")
    if _looks_like_brand_tracker_debris(column):
        reasons.append("weak_family")
    if _looks_like_vendor_plumbing(column) or _looks_like_vendor_plumbing(lower):
        reasons.append("admin")
    if inferred_type == "categorical" and not profile.get("numeric_summary") and "likely_likert_or_coded_categorical" not in warnings:
        reasons.append("categorical")
    if inferred_target and (inferred_target.lower() in lower or lower in inferred_target.lower()) and column != inferred_target:
        reasons.append("derived_target")

    interpretability = _interpretability_score(column)
    if interpretability < -4:
        reasons.append("opaque_code")

    score = _predictor_score(column, profile, inferred_target)
    include = score > 0 and not reasons
    if not include and "likely_likert_or_coded_categorical" in warnings and score > 1 and reasons == ["categorical"]:
        include = True
        reasons = []

    kind = "numeric" if inferred_type in {"numeric", "numeric_like_text"} else "categorical"
    return include, reasons, kind, score


def _build_recommendation(columns: list[str], column_profiles: dict[str, dict], numeric_columns: list[str], saved_predictors: list[str] | None = None, saved_target: str | None = None) -> dict:
    target = saved_target if saved_target in columns else _detect_target(columns, numeric_columns, column_profiles)
    predictor_pool = []
    excluded = []
    for col in columns:
        profile = column_profiles.get(col, {})
        include, reasons, kind, score = _predictor_recommendation(col, profile, target)
        item = {
            "name": col,
            "kind": kind,
            "warnings": profile.get("warnings", []),
            "reasons": reasons,
            "reason_labels": [EXCLUSION_REASON_LABELS.get(reason, reason.replace('_', ' ')) for reason in reasons],
            "score": round(score, 2),
            "recommended_label": _recommended_display_label(col, profile),
            "question_text": profile.get("question_text"),
        }
        if include:
            predictor_pool.append(item)
        else:
            excluded.append(item)

    predictor_pool.sort(key=lambda item: (-item["score"], item["name"]))
    family_groups: dict[str, list[dict]] = {}
    for item in predictor_pool:
        family = _column_family(item["name"])
        item["family"] = family
        family_groups.setdefault(family, []).append(item)

    ranked_families = sorted(
        ((family, _family_score(family, items), items) for family, items in family_groups.items()),
        key=lambda row: (-row[1], row[0]),
    )

    predictors = []
    overflow_predictors = []
    family_counts: dict[str, int] = {}
    for family, family_score, items in ranked_families:
        for item in items:
            if len(predictors) >= DEFAULT_RECOMMENDED_DRIVER_LIMIT:
                overflow_predictors.append({**item, "reasons": ["shortlist_overflow"], "reason_labels": [EXCLUSION_REASON_LABELS["shortlist_overflow"]]})
                continue
            if family_score < 1:
                overflow_predictors.append({**item, "reasons": ["weak_family"], "reason_labels": [EXCLUSION_REASON_LABELS["weak_family"]]})
                continue
            if family_counts.get(family, 0) >= MAX_PER_FAMILY:
                overflow_predictors.append({**item, "reasons": ["family_overrepresented"], "reason_labels": [EXCLUSION_REASON_LABELS["family_overrepresented"]]})
                continue
            predictors.append({**item, "family_score": family_score})
            family_counts[family] = family_counts.get(family, 0) + 1

    excluded.extend(overflow_predictors)

    meta_candidates = []
    remaining_excluded = []
    for item in excluded:
        if "meta_candidate" in item.get("reasons", []):
            meta_candidates.append(item)
        else:
            remaining_excluded.append(item)
    excluded = remaining_excluded
    meta_candidates.sort(key=lambda item: (-item.get("score", 0), item["name"]))

    outcome_candidates = []
    for col in columns:
        profile = column_profiles.get(col, {})
        score = _target_score(col, profile)
        if score > -999 and not _looks_like_text_artifact(col) and not _looks_like_choice_order_artifact(col):
            outcome_candidates.append({"name": col, "score": round(score, 2)})
    outcome_candidates.sort(key=lambda item: (-item["score"], item["name"]))

    if saved_predictors:
        saved_set = {col for col in saved_predictors if col in columns and col != target}
        if saved_set:
            predictors = [item for item in predictor_pool if item["name"] in saved_set]
            excluded = [item for item in excluded if item["name"] not in saved_set]

    usable_rows = None
    if target and target in column_profiles:
        usable_rows = column_profiles[target].get("non_null_count")

    confidence = "low"
    if target and len(predictors) >= 8:
        confidence = "high"
    elif target and len(predictors) >= 3:
        confidence = "medium"

    top_outcome_score = outcome_candidates[0]["score"] if outcome_candidates else -999
    schema_clarity = "described"
    if (not target) or top_outcome_score < 8:
        schema_clarity = "codes_only"

    recommended_labels = {}
    for item in [*predictors, *meta_candidates[:12], *excluded]:
        label = item.get("recommended_label")
        if label:
            recommended_labels[item["name"]] = label
    if target and target in column_profiles:
        target_label = _recommended_display_label(target, column_profiles.get(target, {}))
        if target_label:
            recommended_labels[target] = target_label

    return {
        "target": target,
        "predictors": predictors,
        "excluded": excluded,
        "meta_candidates": meta_candidates[:12],
        "recommended_labels": recommended_labels,
        "usable_rows": usable_rows,
        "confidence": confidence,
        "outcome_candidates": outcome_candidates[:5],
        "driver_shortlist_limit": DEFAULT_RECOMMENDED_DRIVER_LIMIT,
        "driver_pool_count": len(predictor_pool),
        "schema_clarity": schema_clarity,
        "family_limit": MAX_PER_FAMILY,
        "ranked_families": [{"family": family, "score": score, "count": len(items)} for family, score, items in ranked_families[:8]],
    }


def _predictor_candidates(recommendation: dict) -> list[dict]:
    return recommendation.get("predictors", [])


def _display_filename(filename: str) -> str:
    raw_name = Path(filename).name
    parts = raw_name.split("_", 1)
    if len(parts) == 2 and len(parts[0]) == 12:
        return parts[1]
    return raw_name


def _lookup_uploaded_filename(job_id: str) -> str | None:
    matches = sorted(UPLOAD_DIR.glob(f"{job_id}_*"))
    return matches[0].name if matches else None


def _normalize_mapping_state(mapping: dict | None) -> dict:
    mapping = mapping or {}
    return {
        "target_column": mapping.get("target_column") or "",
        "predictor_columns": mapping.get("predictor_columns") or [],
        "segment_columns": mapping.get("segment_columns") or [],
        "segment_definitions": mapping.get("segment_definitions") or [],
        "recode_definitions": mapping.get("recode_definitions") or [],
        "display_name_map": mapping.get("display_name_map") or {},
    }


def _load_mapping_state(job_id: str) -> dict:
    mapping_path = _mapping_path(job_id)
    if not mapping_path.exists():
        return _normalize_mapping_state(None)
    try:
        return _normalize_mapping_state(json.loads(mapping_path.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return _normalize_mapping_state(None)


def _persist_mapping_state(job_id: str, mapping: dict) -> Path:
    mapping_path = _mapping_path(job_id)
    mapping_path.write_text(json.dumps(_normalize_mapping_state(mapping), indent=2), encoding="utf-8")
    return mapping_path


def _parse_codebook_file(file_storage) -> dict[str, str]:
    if not file_storage or not file_storage.filename:
        return {}
    raw = file_storage.read()
    try:
        text = raw.decode("utf-8-sig")
    except Exception:
        return {}
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        return {}
    key_candidates = ["column", "column_name", "name", "field", "variable"]
    label_candidates = ["label", "display_name", "question", "question_text", "description"]
    mapping = {}
    for row in rows:
        key = next((row.get(candidate, "").strip() for candidate in key_candidates if row.get(candidate, "").strip()), "")
        value = next((row.get(candidate, "").strip() for candidate in label_candidates if row.get(candidate, "").strip()), "")
        if key and value:
            mapping[key] = value
    return mapping


def _select_inline_profiles(all_profiles: dict[str, dict], selected_columns: list[str], inferred_target: str | None) -> dict[str, dict]:
    preferred = []
    for col in [inferred_target, *selected_columns, *all_profiles.keys()]:
        if col and col in all_profiles and col not in preferred:
            preferred.append(col)
        if len(preferred) >= MAX_INLINE_COLUMN_PROFILES:
            break
    return {col: all_profiles[col] for col in preferred}


def _mapping_context(
    filename: str,
    *,
    job_id: str,
    mapping_state: dict | None = None,
    recode_definitions: list[dict] | None = None,
    segment_definitions: list[dict] | None = None,
) -> dict:
    mapping_state = _normalize_mapping_state(mapping_state)
    effective_recodes = recode_definitions if recode_definitions is not None else mapping_state["recode_definitions"]
    effective_segments = segment_definitions if segment_definitions is not None else mapping_state["segment_definitions"]

    bundle = build_prep_bundle(
        UPLOAD_DIR / filename,
        recode_definitions=effective_recodes,
        segment_definitions=effective_segments,
    )
    df = bundle.working_df
    columns = list(df.columns)
    numeric_columns = df.select_dtypes(include="number").columns.tolist()
    recommendation = _build_recommendation(
        columns,
        bundle.column_profiles,
        numeric_columns,
        saved_predictors=mapping_state["predictor_columns"],
        saved_target=mapping_state["target_column"],
    )
    inferred_target = recommendation["target"]
    inferred_predictors = mapping_state["predictor_columns"] or [item["name"] for item in recommendation["predictors"]]
    inline_profiles = _select_inline_profiles(bundle.column_profiles, inferred_predictors, inferred_target)
    return {
        "job_id": job_id,
        "filename": filename,
        "display_filename": _display_filename(filename),
        "columns": columns,
        "numeric_columns": numeric_columns,
        "inferred_target": inferred_target,
        "inferred_predictors": inferred_predictors,
        "predictor_candidates": _predictor_candidates(recommendation),
        "recommendation": recommendation,
        "column_profiles": inline_profiles,
        "column_profile_count": len(bundle.column_profiles),
        "column_profiles_trimmed": len(inline_profiles) < len(bundle.column_profiles),
        "column_profiles_inline_limit": MAX_INLINE_COLUMN_PROFILES,
        "segment_previews": bundle.segment_previews,
        "normalized_segment_definitions": bundle.normalized_segments,
        "saved_recode_definitions": effective_recodes,
        "saved_segment_columns": mapping_state["segment_columns"],
        "saved_display_name_map": mapping_state["display_name_map"],
    }


def _write_preview_charts(job_id: str, data_path: Path, mapping_path: Path) -> list[str]:
    mapping = load_mapping_config(mapping_path)
    bundle = build_prep_bundle(
        data_path,
        recode_definitions=mapping.get("recode_definitions", []),
        segment_definitions=mapping.get("segment_definitions", []),
    )
    df = bundle.working_df
    config = resolve_config(df, Args(), mapping)
    validate_resolved_config(df, config)
    _, X, y, _, _ = prepare_sparse_model_data(df, config.target_column, config.predictor_columns)
    results = run_kda(X, y, target_name=config.target_column)

    previews = {
        "importance_bar.png": chart_importance_bar(results.importance.ranking),
        "priority_matrix.png": chart_quadrant(results.quadrants.quadrant_df),
        "model_fit.png": chart_model_fit(results.meta["r_squared"], results.meta["adj_r_squared"]),
    }
    out = _job_dir(job_id)
    for name, content in previews.items():
        (out / name).write_bytes(content)
    return list(previews.keys())


def _append_log(path: Path, title: str, fields: dict[str, object], trace: str | None = None) -> str:
    error_id = uuid.uuid4().hex[:10]
    lines = [f"[{error_id}] {title}"]
    for key, value in fields.items():
        lines.append(f"{key}={value}")
    if trace:
        lines.append(f"traceback=\n{trace}")
    lines.append("-" * 80)
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return error_id


def _log_inspect_failure(job_id: str, upload_path: Path, exc: Exception) -> str:
    return _append_log(
        INSPECT_ERROR_LOG,
        "inspect failure",
        {
            "job_id": job_id,
            "upload_path": upload_path,
            "error": exc,
        },
        traceback.format_exc().strip(),
    )


@app.before_request
def _trace_inspect_request():
    if request.path not in {"/inspect", "/upload"}:
        return None
    content_length = request.content_length or 0
    _append_log(
        REQUEST_ERROR_LOG,
        "inspect request received",
        {
            "method": request.method,
            "content_length": content_length,
            "content_type": request.content_type,
            "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
            "user_agent": request.headers.get("User-Agent", ""),
        },
    )
    return None


@app.errorhandler(Exception)
def _handle_unexpected_exception(exc: Exception):
    if hasattr(exc, "code") and getattr(exc, "code", None) is not None:
        return exc
    error_id = _append_log(
        REQUEST_ERROR_LOG,
        "unhandled application exception",
        {
            "path": request.path,
            "method": request.method,
            "content_length": request.content_length or 0,
            "content_type": request.content_type,
            "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
            "error": exc,
        },
        traceback.format_exc().strip(),
    )
    return render_template("index.html", error=f"Internal server error ({error_id}). Logged to {REQUEST_ERROR_LOG}."), 500


@app.get("/")
@basic_auth
def index():
    return render_template("index.html")


@app.get("/mapping/<job_id>")
@basic_auth
def mapping_page(job_id: str):
    filename = _lookup_uploaded_filename(job_id)
    if not filename:
        abort(404)
    mapping_state = _load_mapping_state(job_id)
    try:
        context = _mapping_context(filename, job_id=job_id, mapping_state=mapping_state)
    except Exception as exc:
        error_id = _log_inspect_failure(job_id, UPLOAD_DIR / filename, exc)
        message = f"Inspect failed ({error_id}): {exc}. Logged to {INSPECT_ERROR_LOG}."
        return render_template("index.html", error=message), 500
    return render_template("mapping.html", **context)


@app.get("/mapping/<job_id>/profile")
@basic_auth
def mapping_profile(job_id: str):
    filename = _lookup_uploaded_filename(job_id)
    column = request.args.get("column", "").strip()
    if not filename or not column:
        abort(404)
    mapping_state = _load_mapping_state(job_id)
    context = _mapping_context(filename, job_id=job_id, mapping_state=mapping_state)
    bundle = build_prep_bundle(
        UPLOAD_DIR / filename,
        recode_definitions=mapping_state["recode_definitions"],
        segment_definitions=mapping_state["segment_definitions"],
    )
    profile = bundle.column_profiles.get(column)
    if not profile:
        abort(404)
    return jsonify({"profile": profile})


@app.post("/upload")
@basic_auth
def upload_file():
    f = request.files.get("survey_file")
    wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accept_mimetypes.best == "application/json"
    if not f or not f.filename:
        if wants_json:
            return jsonify({"error": "Upload a CSV first."}), 400
        return render_template("index.html", error="Upload a CSV first."), 400

    job_id = uuid.uuid4().hex[:12]
    upload_path = UPLOAD_DIR / f"{job_id}_{Path(f.filename).name}"
    f.save(upload_path)

    redirect_url = url_for("mapping_page", job_id=job_id)
    if wants_json:
        return jsonify({"job_id": job_id, "redirect_url": redirect_url, "filename": upload_path.name})
    return render_template("upload-complete.html", job_id=job_id, redirect_url=redirect_url, display_filename=_display_filename(upload_path.name))


@app.post("/inspect")
@basic_auth
def inspect_file():
    f = request.files.get("survey_file")
    wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accept_mimetypes.best == "application/json"
    if not f or not f.filename:
        if wants_json:
            return jsonify({"error": "Upload a CSV first."}), 400
        return render_template("index.html", error="Upload a CSV first."), 400

    job_id = uuid.uuid4().hex[:12]
    upload_path = UPLOAD_DIR / f"{job_id}_{Path(f.filename).name}"
    f.save(upload_path)

    try:
        context = _mapping_context(upload_path.name, job_id=job_id)
    except Exception as exc:
        error_id = _log_inspect_failure(job_id, upload_path, exc)
        message = f"Inspect failed ({error_id}): {exc}. Logged to {INSPECT_ERROR_LOG}."
        if wants_json:
            return jsonify({"error": message, "error_id": error_id, "log_path": str(INSPECT_ERROR_LOG)}), 500
        return render_template("index.html", error=message), 500

    redirect_url = url_for("mapping_page", job_id=job_id)
    if wants_json:
        return jsonify({"job_id": job_id, "redirect_url": redirect_url, "filename": upload_path.name})
    return render_template("mapping.html", **context)


@app.post("/preview")
@basic_auth
def preview_mapping():
    payload = request.get_json(silent=True) or {}
    filename = payload.get("filename")
    job_id = payload.get("job_id") or uuid.uuid4().hex[:12]
    if not filename:
        abort(400)
    mapping_state = _normalize_mapping_state(
        {
            "target_column": payload.get("target_column"),
            "predictor_columns": payload.get("predictor_columns", []),
            "segment_columns": payload.get("segment_columns", []),
            "segment_definitions": payload.get("segment_definitions", []),
            "recode_definitions": payload.get("recode_definitions", []),
            "display_name_map": payload.get("display_name_map", {}),
        }
    )
    try:
        context = _mapping_context(
            filename,
            job_id=job_id,
            mapping_state=mapping_state,
            recode_definitions=mapping_state["recode_definitions"],
            segment_definitions=mapping_state["segment_definitions"],
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    _persist_mapping_state(job_id, mapping_state)
    bundle = build_prep_bundle(
        UPLOAD_DIR / filename,
        recode_definitions=mapping_state["recode_definitions"],
        segment_definitions=mapping_state["segment_definitions"],
    )
    return jsonify(
        {
            "columns": context["columns"],
            "numeric_columns": context["numeric_columns"],
            "column_profiles": bundle.column_profiles,
            "segment_previews": context["segment_previews"],
            "normalized_segment_definitions": context["normalized_segment_definitions"],
            "recommendation": context["recommendation"],
        }
    )


@app.post("/mapping/<job_id>/codebook")
@basic_auth
def upload_codebook(job_id: str):
    filename = _lookup_uploaded_filename(job_id)
    if not filename:
        abort(404)
    mapping_state = _load_mapping_state(job_id)
    parsed = _parse_codebook_file(request.files.get("codebook_file"))
    mapping_state["display_name_map"] = {**mapping_state.get("display_name_map", {}), **parsed}
    _persist_mapping_state(job_id, mapping_state)
    context = _mapping_context(filename, job_id=job_id, mapping_state=mapping_state)
    return jsonify({"display_name_map": context["saved_display_name_map"], "recommendation": context["recommendation"]})


@app.post("/run")
@basic_auth
def run_job():
    job_id = request.form.get("job_id") or uuid.uuid4().hex[:12]
    filename = request.form.get("filename")
    if not filename:
        abort(400)

    data_path = UPLOAD_DIR / filename
    predictors = request.form.getlist("predictor_columns")
    target_column = request.form.get("target_column")
    segment_columns = request.form.getlist("segment_columns")

    display_name_map = {}
    for key, value in request.form.items():
        if key.startswith("display_name__") and value.strip():
            display_name_map[key.split("display_name__", 1)[1]] = value.strip()

    segment_definitions = _parse_json_field(request.form.get("segment_definitions"))
    recode_definitions = _parse_json_field(request.form.get("recode_definitions"))
    mapping_state = {
        "target_column": target_column,
        "segment_columns": segment_columns,
        "segment_definitions": segment_definitions,
        "recode_definitions": recode_definitions,
        "predictor_columns": predictors,
        "display_name_map": display_name_map,
    }

    try:
        context = _mapping_context(
            filename,
            job_id=job_id,
            mapping_state=mapping_state,
            recode_definitions=recode_definitions,
            segment_definitions=segment_definitions,
        )
        normalized_segments = context["normalized_segment_definitions"]
    except ValueError as exc:
        context = _mapping_context(filename, job_id=job_id, mapping_state=mapping_state)
        return render_template("mapping.html", error=str(exc), **context), 400

    mapping = {
        "target_column": target_column,
        "segment_columns": segment_columns,
        "segment_definitions": normalized_segments,
        "recode_definitions": recode_definitions,
        "predictor_columns": predictors,
        "display_name_map": display_name_map,
    }
    mapping_path = _persist_mapping_state(job_id, mapping)

    job_dir = _job_dir(job_id)
    json_path = job_dir / "analysis_run.json"
    pptx_path = job_dir / "report.pptx"

    cmd = [
        str(ROOT / ".venv" / "bin" / "python"),
        str(ROOT / "tundralis_kda.py"),
        "--data", str(data_path),
        "--mapping-config", str(mapping_path),
        "--no-ai",
        "--json-output", str(json_path),
        "--output", str(pptx_path),
    ]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)

    if result.returncode != 0:
        return render_template(
            "mapping.html",
            error=result.stderr or result.stdout or "Run failed.",
            **context,
        ), 500

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    payload.setdefault("input_summary", {})["segment_definitions"] = normalized_segments
    payload.setdefault("input_summary", {})["segment_previews"] = context["segment_previews"]
    payload.setdefault("input_summary", {})["recode_definitions"] = recode_definitions
    payload.setdefault("segment_summaries", payload.get("segment_summaries", []))
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    preview_images = _write_preview_charts(job_id, data_path, mapping_path)
    return render_template(
        "result.html",
        job_id=job_id,
        filename=filename,
        display_filename=_display_filename(filename),
        payload=payload,
        logs=result.stdout,
        preview_images=preview_images,
    )


@app.get("/artifacts/<job_id>/<path:name>")
@basic_auth
def artifacts(job_id: str, name: str):
    return send_from_directory(_job_dir(job_id), name, as_attachment=False)


if __name__ == "__main__":
    host = os.environ.get("TUNDRALIS_HOST", "127.0.0.1")
    port = int(os.environ.get("TUNDRALIS_PORT", "7860"))
    app.run(host=host, port=port, debug=False)
