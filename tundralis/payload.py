"""Stable payload builder for Tundralis KDA analysis runs."""

from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path

import pandas as pd

from tundralis.utils import human_label, scale_to_range


def _rank_map(df: pd.DataFrame, value_col: str) -> dict[str, int]:
    ordered = df.sort_values(value_col, ascending=False).reset_index(drop=True)
    return {row["predictor"]: int(i + 1) for i, (_, row) in enumerate(ordered.iterrows())}


def _agreement_label(importance_rank: int, impact_rank: int) -> str:
    delta = abs(importance_rank - impact_rank)
    if delta <= 1:
        return "high"
    if delta <= 3:
        return "moderate"
    return "low"


def build_analysis_run_payload(
    *,
    results,
    source_file: str | Path,
    input_df: pd.DataFrame,
    model_df: pd.DataFrame,
    target_column: str,
    predictor_columns: list[str],
    missingness_summary: dict,
    driver_usable_n: dict[str, int],
    recommendations: list[str] | None = None,
    display_name_map: dict[str, str] | None = None,
) -> dict:
    recommendations = recommendations or []
    display_name_map = display_name_map or {}

    rows_input = int(len(input_df))
    rows_with_valid_dv = int(input_df[target_column].notna().sum())
    rows_with_valid_dv_and_any_predictor = int(
        input_df.loc[input_df[target_column].notna(), predictor_columns].notna().any(axis=1).sum()
    )
    rows_modeled = int(len(model_df))
    rows_dropped = int(rows_input - rows_with_valid_dv_and_any_predictor)

    outcome_min = float(input_df[target_column].min())
    outcome_max = float(input_df[target_column].max())
    outcome_mean = float(model_df[target_column].mean())
    outcome_std = float(model_df[target_column].std(ddof=1) or 0.0)
    outcome_norm = float(scale_to_range(pd.Series([outcome_mean]).to_numpy(), 0, 100)[0]) if outcome_max != outcome_min else 50.0
    # Fix the single-value scaling issue by directly normalizing to known scale.
    if outcome_max != outcome_min:
        outcome_norm = ((outcome_mean - outcome_min) / (outcome_max - outcome_min)) * 100.0

    coef_map = results.regression.coefficients.set_index("predictor").to_dict("index")
    imp_map = results.importance.ranking.set_index("predictor").to_dict("index")
    quad_map = results.quadrants.quadrant_df.set_index("predictor").to_dict("index")

    impact_values = []
    for predictor in predictor_columns:
        coef = float(coef_map[predictor]["coef"])
        impact_values.append(max(coef, 0.0))

    impact_scaled = scale_to_range(pd.Series(impact_values).to_numpy(), 0, 1)
    impact_rank = {
        predictor_columns[i]: int(rank)
        for i, rank in enumerate(pd.Series(impact_values, index=predictor_columns).rank(method="first", ascending=False).astype(int).tolist())
    }

    opportunity_scores = {}
    for i, predictor in enumerate(predictor_columns):
        q = quad_map[predictor]
        headroom = max(0.0, 1.0 - float(q["performance"]))
        impact_component = float(impact_scaled[i])
        confidence_component = min(1.0, driver_usable_n.get(predictor, 0) / max(rows_modeled, 1))
        opportunity_scores[predictor] = impact_component * headroom * confidence_component

    opportunity_rank = {
        predictor: int(rank)
        for predictor, rank in pd.Series(opportunity_scores).rank(method="first", ascending=False).astype(int).to_dict().items()
    }

    top_two_importance = set(results.importance.ranking.head(2)["predictor"].tolist())
    top_two_impact = {
        p for p, _ in sorted(opportunity_scores.items(), key=lambda kv: kv[1], reverse=True)[:2]
    }

    drivers = []
    agreement_labels = []
    for i, predictor in enumerate(predictor_columns):
        imp = imp_map[predictor]
        coef = coef_map[predictor]
        q = quad_map[predictor]
        agreement = _agreement_label(int(imp["rank"]), int(impact_rank[predictor]))
        agreement_labels.append(agreement)

        if predictor in top_two_importance and predictor in top_two_impact:
            classification = "Core Priority"
        elif predictor in top_two_importance:
            classification = "Foundational Driver"
        elif predictor in top_two_impact:
            classification = "High-Potential Lever"
        else:
            classification = "Lower Priority"

        perf_mean = float(model_df[predictor].mean())
        perf_std = float(model_df[predictor].std(ddof=1) or 0.0)
        scale_min = float(input_df[predictor].min())
        scale_max = float(input_df[predictor].max())
        if scale_max == scale_min:
            normalized = 50.0
            headroom_raw = 0.0
        else:
            normalized = ((perf_mean - scale_min) / (scale_max - scale_min)) * 100.0
            headroom_raw = max(0.0, scale_max - perf_mean)

        drivers.append({
            "driver_id": predictor,
            "driver_label": display_name_map.get(predictor, human_label(predictor)),
            "performance": {
                "mean": round(perf_mean, 4),
                "std_dev": round(perf_std, 4),
                "headroom": round(headroom_raw, 4),
                "normalized_mean_0_100": round(normalized, 2),
                "usable_n": int(driver_usable_n.get(predictor, 0)),
            },
            "importance": {
                "share_of_explained_variance": round(float(imp["importance_pct"]), 2),
                "rank": int(imp["rank"]),
            },
            "impact": {
                "coefficient": round(float(coef["coef"]), 4),
                "one_point_dv_change": round(float(coef["coef"]), 4),
                "max_gain": round(float(coef["coef"]) * headroom_raw, 4),
                "rank": int(impact_rank[predictor]),
            },
            "opportunity": {
                "score": round(float(opportunity_scores[predictor]), 4),
                "rank": int(opportunity_rank[predictor]),
                "components": {
                    "impact_component": round(float(impact_scaled[i]), 4),
                    "headroom_component": round(max(0.0, 1.0 - float(q["performance"])), 4),
                    "confidence_component": round(min(1.0, driver_usable_n.get(predictor, 0) / max(rows_modeled, 1)), 4),
                },
            },
            "classification": classification,
            "narrative": {
                "headline": None,
                "summary": None,
            },
        })

    if "low" in agreement_labels:
        method_agreement = "low"
    elif "moderate" in agreement_labels:
        method_agreement = "moderate"
    else:
        method_agreement = "high"

    recs = []
    for i, rec in enumerate(recommendations[:5], start=1):
        top_drivers = [d["driver_id"] for d in sorted(drivers, key=lambda d: d["opportunity"]["rank"])[:2]]
        recs.append({
            "title": f"Recommendation {i}",
            "priority": "high" if i <= 2 else "medium",
            "rationale": rec,
            "drivers": top_drivers,
        })

    return {
        "run_info": {
            "analysis_type": "kda",
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "ok",
            "project_id": None,
            "version": "0.1.0",
            "warnings": [],
        },
        "input_summary": {
            "source_file": str(Path(source_file)),
            "rows_input": rows_input,
            "rows_modeled": rows_modeled,
            "rows_dropped": rows_dropped,
            "rows_with_valid_dv": rows_with_valid_dv,
            "rows_with_valid_dv_and_any_predictor": rows_with_valid_dv_and_any_predictor,
            "target_column": target_column,
            "predictor_columns": predictor_columns,
            "weight_column": None,
            "segment_columns": [],
            "missingness": missingness_summary,
        },
        "outcome": {
            "name": target_column,
            "label": display_name_map.get(target_column, human_label(target_column)),
            "scale": {"min": outcome_min, "max": outcome_max},
            "summary": {
                "mean": round(outcome_mean, 4),
                "std_dev": round(outcome_std, 4),
                "normalized_mean_0_100": round(outcome_norm, 2),
            },
        },
        "model_diagnostics": {
            "importance_method": "shapley_r_squared",
            "impact_method": "ols_coefficient",
            "nonlinear_benchmark_method": None,
            "r_squared": float(results.regression.r_squared),
            "adj_r_squared": float(results.regression.adj_r_squared),
            "f_statistic": float(results.regression.f_statistic),
            "f_p_value": float(results.regression.f_p_value),
            "method_agreement": method_agreement,
            "nonlinear_signal": "unknown",
        },
        "drivers": drivers,
        "chart_payloads": {
            "importance_ranking": {
                "drivers": [
                    {"driver": d["driver_label"], "importance": d["importance"]["share_of_explained_variance"]}
                    for d in sorted(drivers, key=lambda x: x["importance"]["rank"])
                ]
            },
            "impact_ranking": {
                "drivers": [
                    {"driver": d["driver_label"], "impact": d["impact"]["one_point_dv_change"]}
                    for d in sorted(drivers, key=lambda x: x["impact"]["rank"])
                ]
            },
            "classic_priority_matrix": {
                "drivers": [
                    {
                        "driver": d["driver_label"],
                        "performance": d["performance"]["normalized_mean_0_100"],
                        "importance": d["importance"]["share_of_explained_variance"],
                    }
                    for d in drivers
                ]
            },
            "action_matrix": {
                "drivers": [
                    {
                        "driver": d["driver_label"],
                        "performance": d["performance"]["normalized_mean_0_100"],
                        "impact": d["impact"]["one_point_dv_change"],
                        "importance": d["importance"]["share_of_explained_variance"],
                    }
                    for d in drivers
                ]
            },
            "opportunity_ranking": {
                "drivers": [
                    {"driver": d["driver_label"], "opportunity": d["opportunity"]["score"]}
                    for d in sorted(drivers, key=lambda x: x["opportunity"]["rank"])
                ]
            },
        },
        "recommendations": recs,
    }
