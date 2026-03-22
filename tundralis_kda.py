#!/usr/bin/env python3
"""
tundralis_kda.py — Key Driver Analysis CLI

Usage:
  python tundralis_kda.py --data data/sample_survey.csv --target overall_satisfaction
  python tundralis_kda.py --data data/fixtures/client_style_kda.csv \
      --mapping-config data/fixtures/client_style_kda_mapping.json \
      --no-ai
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
    prepare_sparse_model_data,
    output_path,
    write_json,
)
from tundralis.ingestion import (
    load_mapping_config,
    resolve_config,
    validate_resolved_config,
    build_validation_summary,
)
from tundralis.analysis import run_kda
from tundralis.narratives import NarrativeEngine
from tundralis.payload import build_analysis_run_payload
from tundralis.transforms import apply_recode_transforms
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
    parser.add_argument("--data", required=True, help="Path to input CSV file")
    parser.add_argument("--target", required=False, help="Name of the outcome/target column")
    parser.add_argument(
        "--predictors", nargs="+", default=None,
        help="Predictor column names (default: all numeric columns except target)",
    )
    parser.add_argument(
        "--mapping-config", default=None,
        help="Optional JSON mapping config describing target/predictors/meta columns",
    )
    parser.add_argument(
        "--validate-only", action="store_true",
        help="Validate and summarize the input contract without running the full analysis",
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
    parser.add_argument("--no-ai", action="store_true", help="Disable AI narrative generation entirely")
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging verbosity"
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    logger.info("Loading data from: %s", args.data)
    raw_df = load_survey_data(args.data)

    mapping = load_mapping_config(args.mapping_config)
    recode_definitions = mapping.get("recode_definitions", [])
    df = apply_recode_transforms(raw_df, recode_definitions)
    config = resolve_config(df, args, mapping)
    validate_resolved_config(df, config)
    validation_summary = build_validation_summary(df, config)

    logger.info("Resolved input config:")
    logger.info("  Target     : %s", config.target_column)
    logger.info("  Predictors : %d", len(config.predictor_columns))
    logger.info("  Rows input : %d", validation_summary["rows_input"])
    logger.info("  Rows valid DV + any predictor : %d", validation_summary["rows_with_valid_dv_and_any_predictor"])

    if args.validate_only:
        logger.info("Validation-only mode complete.")
        print(validation_summary)
        return 0

    eligible_df, X, y, missingness_summary, driver_usable_n = prepare_sparse_model_data(
        df,
        config.target_column,
        config.predictor_columns,
    )

    logger.info("Analysis config:")
    logger.info("  Target     : %s", config.target_column)
    logger.info("  Predictors : %s", config.predictor_columns)
    logger.info("  N modeled  : %d", len(y))
    logger.info("  Eligible   : valid DV + at least one predictor")

    results = run_kda(X, y, target_name=config.target_column)

    engine = NarrativeEngine(model=args.openai_model, enabled=not args.no_ai)
    logger.info("Generating narratives...")
    recommendations = engine.recommendations(results)
    logger.info("Generating charts...")

    charts = {}
    charts["importance_bar"] = chart_importance_bar(results.importance.ranking)
    charts["quadrant"] = chart_quadrant(results.quadrants.quadrant_df)
    charts["correlation"] = chart_correlation_heatmap(results.correlations.pearson)
    charts["model_fit"] = chart_model_fit(results.meta["r_squared"], results.meta["adj_r_squared"])
    for pred in config.predictor_columns:
        charts[f"driver_{pred}"] = chart_driver_detail(pred, results)

    payload = build_analysis_run_payload(
        results=results,
        source_file=args.data,
        input_df=df,
        model_df=eligible_df,
        target_column=config.target_column,
        predictor_columns=config.predictor_columns,
        missingness_summary=missingness_summary,
        driver_usable_n=driver_usable_n,
        recommendations=recommendations,
        display_name_map=mapping.get("display_name_map", {}),
    )
    payload["run_info"]["version"] = __version__
    payload["input_summary"]["weight_column"] = config.weight_column
    payload["input_summary"]["segment_columns"] = config.segment_columns or []
    payload["input_summary"]["recode_definitions"] = recode_definitions

    builder = PayloadReportBuilder(payload, charts)
    builder.build()

    safe_target = config.target_column.replace(" ", "_")
    out_file = Path(args.output) if args.output else output_path("output", f"{safe_target}_kda_report.pptx")
    json_file = Path(args.json_output) if args.json_output else output_path("output", f"{safe_target}_analysis_run.json")

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
