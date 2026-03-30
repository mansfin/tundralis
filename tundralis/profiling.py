from __future__ import annotations

from collections import Counter
from math import isfinite
import re

import pandas as pd

from tundralis.utils import get_qualtrics_column_metadata


LIKERT_MAX_UNIQUE = 11
HIGH_CARDINALITY_RATIO = 0.5
IDENTIFIER_UNIQUENESS_RATIO = 0.98
TOP_VALUE_LIMIT = 8
PROFILE_SAMPLE_ROWS = 1000


def _missing_pct(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    return round(float(series.isna().mean() * 100), 1)


def _top_values(series: pd.Series, limit: int = TOP_VALUE_LIMIT) -> list[dict]:
    non_null = series.dropna()
    if non_null.empty:
        return []
    counts = Counter(non_null.astype(str).tolist()).most_common(limit)
    total = len(non_null)
    return [
        {
            "value": value,
            "count": int(count),
            "pct": round((count / total) * 100, 1),
        }
        for value, count in counts
    ]


def _numeric_summary(series: pd.Series) -> dict | None:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None
    return {
        "min": float(numeric.min()),
        "max": float(numeric.max()),
        "mean": round(float(numeric.mean()), 3),
        "median": round(float(numeric.median()), 3),
    }


def _looks_like_likert(series: pd.Series) -> bool:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return False
    uniques = sorted({float(v) for v in numeric.unique() if isfinite(float(v))})
    if not uniques or len(uniques) > LIKERT_MAX_UNIQUE:
        return False
    return all(float(v).is_integer() for v in uniques) and max(uniques) - min(uniques) <= 10


def _inferred_type(series: pd.Series) -> str:
    non_null = series.dropna()
    if non_null.empty:
        return "empty"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"

    coerced = pd.to_numeric(non_null, errors="coerce")
    numeric_share = float(coerced.notna().mean())
    if numeric_share >= 0.95:
        return "numeric_like_text"
    if numeric_share >= 0.2:
        return "mixed"

    distinct = int(non_null.nunique(dropna=True))
    if distinct <= LIKERT_MAX_UNIQUE:
        return "categorical"
    return "text"


def _warnings(series: pd.Series, inferred_type: str) -> list[str]:
    warnings: list[str] = []
    total = len(series)
    non_null = series.dropna()
    distinct = int(non_null.nunique(dropna=True))

    if total and distinct / max(total, 1) >= HIGH_CARDINALITY_RATIO and distinct > 20:
        warnings.append("high_cardinality")

    if total and distinct / max(len(non_null), 1) >= IDENTIFIER_UNIQUENESS_RATIO and distinct > 20:
        warnings.append("likely_identifier")

    if inferred_type == "mixed":
        warnings.append("mixed_numeric_text")

    if inferred_type in {"numeric", "numeric_like_text", "categorical"} and _looks_like_likert(series):
        warnings.append("likely_likert_or_coded_categorical")

    if _missing_pct(series) >= 25:
        warnings.append("high_missingness")

    return warnings


def _semantic_lower(column: str, column_context: dict | None) -> str:
    column_context = column_context or {}
    semantic_text = column_context.get("semantic_text") or column
    return str(semantic_text).lower()


def _looks_admin_like(column: str, semantic_lower: str, warnings: list[str]) -> bool:
    lower = column.lower()
    admin_column_tokens = [
        "startdate", "enddate", "recordeddate", "status", "ipaddress", "recipient", "email", "phone",
        "externalreference", "latitude", "longitude", "distributionchannel", "userlanguage", "duration",
        "progress", "finished", "location", "fraud", "duplicate", "responseid", "respondentid",
        "transaction_id", "session_id", "redirecturl", "redirect_url", "panelist", "panel_id", "supplier", "sample_source",
    ]
    admin_semantic_tokens = ["display order"]
    if "likely_identifier" in warnings:
        return True
    if any(token in lower for token in admin_column_tokens):
        return True
    return any(token in semantic_lower for token in admin_semantic_tokens)


def _looks_segment_like(column: str, semantic_lower: str) -> bool:
    lower = column.lower()
    if any(token in lower or token in semantic_lower for token in ["score", "index", "rating", "satisfaction", "recommend", "likelihood", "agree", "agreement", "importance"]):
        return False
    segment_tokens = [
        "segment", "region", "country", "state", "dma", "msa", "postal", "zip", "department",
        "team", "role", "title", "tenure", "company size", "company_size", "industry", "market",
        "gender", "age", "generation", "income", "persona", "cohort",
    ]
    return any(token in lower or token in semantic_lower for token in segment_tokens)


def _is_low_signal_code_name(column: str) -> bool:
    lower = column.lower()
    return bool(
        re.fullmatch(r"v\d+", lower)
        or re.fullmatch(r"q\d+(?:_\d+)+", lower)
        or re.fullmatch(r"q\d+", lower)
        or re.fullmatch(r"s\d+(?:_\d+)?", lower)
        or re.fullmatch(r"[a-z]{1,3}", lower)
    )


def _semantic_class(series: pd.Series, column: str, inferred_type: str, warnings: list[str], column_context: dict | None = None) -> tuple[str, str]:
    column_context = column_context or {}
    semantic_lower = _semantic_lower(column, column_context)
    lower = column.lower()
    non_null = series.dropna()
    distinct = int(non_null.nunique(dropna=True))

    if inferred_type == "empty":
        return "empty", "low"

    if _looks_admin_like(column, semantic_lower, warnings):
        return "identifier_helper", "high"

    if inferred_type == "categorical":
        if distinct <= LIKERT_MAX_UNIQUE and any(token in semantic_lower for token in ["agree", "satisf", "recommend", "likely", "ease", "quality", "support", "trust", "rate", "positive", "frequency", "reasonable", "fair", "clear", "helpful"]):
            return "ordinal_labeled", "high"
        if _looks_segment_like(column, semantic_lower):
            return "labeled_categorical", "high"
        return "labeled_categorical", "medium"

    if inferred_type == "text":
        if any(token in lower or token in semantic_lower for token in ["comment", "verbatim", "open end", "open_end", "specify", "free text"]):
            return "free_text", "high"
        return "labeled_categorical", "medium"

    if inferred_type == "mixed":
        return "ambiguous_numeric", "low"

    if inferred_type in {"numeric", "numeric_like_text"}:
        if "likely_likert_or_coded_categorical" in warnings:
            if any(token in semantic_lower for token in ["nps", "recommend", "likelihood to recommend", "satisfaction", "sat", "agreement", "agree", "importance", "frequency", "ease", "quality", "trust", "support", "rating", "score"]):
                return "ordinal_numeric", "high"
            if _looks_segment_like(column, semantic_lower):
                return "nominal_coded_numeric", "high"
            if _is_low_signal_code_name(column):
                return "ordinal_numeric", "low"
            return "ordinal_numeric", "medium"
        if distinct <= 12:
            if any(token in semantic_lower for token in ["index", "score", "rating", "satisfaction", "recommend", "likelihood", "agree", "agreement", "importance", "support", "trust", "quality", "ease"]):
                return "ordinal_numeric", "medium"
            if _looks_segment_like(column, semantic_lower):
                return "nominal_coded_numeric", "high"
            return "nominal_coded_numeric", "low"
        return "continuous_numeric", "high"

    return "ambiguous_numeric", "low"


def profile_column(df: pd.DataFrame, column: str, column_context: dict | None = None) -> dict:
    series = df[column]
    non_null = series.dropna()
    inferred_type = _inferred_type(series)
    column_context = column_context or {}
    warnings = _warnings(series, inferred_type)
    semantic_class, semantic_confidence = _semantic_class(series, column, inferred_type, warnings, column_context)
    profile = {
        "column": column,
        "inferred_type": inferred_type,
        "semantic_class": semantic_class,
        "semantic_confidence": semantic_confidence,
        "non_null_count": int(series.notna().sum()),
        "missing_count": int(series.isna().sum()),
        "missing_pct": _missing_pct(series),
        "distinct_count": int(non_null.nunique(dropna=True)),
        "top_values": _top_values(series),
        "warnings": warnings,
        "sample_values": [str(v) for v in non_null.astype(str).head(5).tolist()],
        "question_text": column_context.get("question_text"),
        "import_id": column_context.get("import_id"),
        "semantic_text": column_context.get("semantic_text") or column,
    }

    numeric_summary = _numeric_summary(series)
    if numeric_summary:
        profile["numeric_summary"] = numeric_summary

    return profile


def profile_dataframe(df: pd.DataFrame, sample_rows: int = PROFILE_SAMPLE_ROWS) -> dict[str, dict]:
    profile_df = df.head(sample_rows) if sample_rows and len(df) > sample_rows else df
    qualtrics_metadata = get_qualtrics_column_metadata(df)
    return {
        column: profile_column(profile_df, column, qualtrics_metadata.get(column))
        for column in profile_df.columns
    }
