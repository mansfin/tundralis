#!/usr/bin/env python3
"""
tundralis_kda.py — Key Driver Analysis CLI

Usage:
  python tundralis_kda.py --data data/sample_survey.csv --target overall_satisfaction
  python tundralis_kda.py --data data/sample_survey.csv --target overall_satisfaction \\
      --predictors ease_of_use customer_support price_value \\
      --output output/my_report.pptx \\
      --openai-model gpt-4o
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from tundralis import __version__
from tundralis.utils import (
    setup_logging,
    load_survey_data,
    validate_columns,
    prepare_sparse_model_data,
    output_path,
    write_json,
)
from tundralis.analysis import run_kda
from tundralis.narratives import NarrativeEngine
from tundralis.payload import build_analysis_run_payload
from tundralis.charts import (
    chart_importance_bar,
    chart_quadrant,
    chart_correlation_heatmap,
    chart_model_fit,
    chart_driver_detail,
)
from tundralis.payload_report import PayloadReportBuilder


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tundralis — Key Driver Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--data", required=True,
        help="Path to input CSV file",
    )
    parser.add_argument(
        "--target", required=True,
        help="Name of the outcome/target column",
    )
    parser.add_argument(
        "--predictors", nargs="+", default=None,
        help="Predictor column names (default: all numeric columns except target)",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output .pptx file path (default: output/<target>_kda_report.pptx)",
    )
    parser.add_argument(
        "--json-output", default=None,
        help="Optional output path for analysis-run JSON (default: output/<target>_analysis_run.json)",
    )
    parser.add_argument(
        "--openai-model", default="gpt-4o",
        help="OpenAI model for narrative generation (default: gpt-4o)",
    )
    parser.add_argument(
        "--no-ai", action="store_true",
        help="Disable AI narrative generation entirely",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity",
    )
    return parser.parse_args(argv)


def infer_predictors(df, target: str) -> list[str]:
    """Auto-detect numeric columns excluding the target and common ID columns."""
    import pandas as pd
    numerics = df.select_dtypes(include="number").columns.tolist()
    # Exclude target and obvious ID/index columns
    exclude_patterns = {target, "id", "respondent_id", "record_id", "row_id", "index"}
    return [
        c for c in numerics
        if c != target and c.lower() not in exclude_patterns and not c.lower().endswith("_id")
    ]


def main(argv=None):
    args = parse_args(argv)
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    # ── Load data ─────────────────────────────────────────────────────────────
    logger.info("Loading data from: %s", args.data)
    df = load_survey_data(args.data)

    # ── Determine predictors ──────────────────────────────────────────────────
    if args.predictors:
        predictors = args.predictors
    else:
        predictors = infer_predictors(df, args.target)
        logger.info("Auto-detected %d predictors: %s", len(predictors), predictors)

    # ── Validate ──────────────────────────────────────────────────────────────
    validate_columns(df, args.target, predictors)
    eligible_df, X, y, missingness_summary, driver_usable_n = prepare_sparse_model_data(df, args.target, predictors)

    logger.info("Analysis config:")
    logger.info("  Target     : %s", args.target)
    logger.info("  Predictors : %s", predictors)
    logger.info("  N modeled  : %d", len(y))
    logger.info("  Eligible   : valid DV + at least one predictor")

    # ── Statistical analysis ──────────────────────────────────────────────────
    results = run_kda(X, y, target_name=args.target)

    # ── Narrative engine ──────────────────────────────────────────────────────
    engine = NarrativeEngine(
        model=args.openai_model,
        enabled=not args.no_ai,
    )
    logger.info("Generating narratives...")
    exec_summary = engine.executive_summary(results)
    recommendations = engine.recommendations(results)
    driver_insights = {
        pred: engine.driver_insight(pred, results)
        for pred in predictors
    }
    logger.info("Generating charts...")

    # ── Charts ────────────────────────────────────────────────────────────────
    charts = {}
    charts["importance_bar"] = chart_importance_bar(results.importance.ranking)
    charts["quadrant"] = chart_quadrant(results.quadrants.quadrant_df)
    charts["correlation"] = chart_correlation_heatmap(results.correlations.pearson)
    charts["model_fit"] = chart_model_fit(results.meta["r_squared"], results.meta["adj_r_squared"])
    for pred in predictors:
        charts[f"driver_{pred}"] = chart_driver_detail(pred, results)

    payload = build_analysis_run_payload(
        results=results,
        source_file=args.data,
        input_df=df,
        model_df=eligible_df,
        target_column=args.target,
        predictor_columns=predictors,
        missingness_summary=missingness_summary,
        driver_usable_n=driver_usable_n,
        recommendations=recommendations,
    )
    payload["run_info"]["version"] = __version__

    # ── Build report ──────────────────────────────────────────────────────────
    builder = PayloadReportBuilder(payload, charts)
    builder.build()

    # ── Save ──────────────────────────────────────────────────────────────────
    safe_target = args.target.replace(" ", "_")
    if args.output:
        out_file = Path(args.output)
    else:
        out_file = output_path("output", f"{safe_target}_kda_report.pptx")

    if args.json_output:
        json_file = Path(args.json_output)
    else:
        json_file = output_path("output", f"{safe_target}_analysis_run.json")

    saved = builder.save(out_file)
    json_saved = write_json(json_file, payload)
    logger.info("")
    logger.info("━" * 60)
    logger.info("  ✓  Report saved: %s", saved.resolve())
    logger.info("  ✓  JSON saved  : %s", json_saved.resolve())
    logger.info("  ✓  Slides: %d", len(builder.prs.slides))
    logger.info("  ✓  Model R²: %.3f", results.meta["r_squared"])
    logger.info("━" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
