"""Data loading, validation, and helper utilities."""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─── Brand colors ────────────────────────────────────────────────────────────
BRAND_DARK_BLUE = "#1B2A4A"
BRAND_TEAL = "#2EC4B6"
BRAND_WHITE = "#FFFFFF"
BRAND_LIGHT_GRAY = "#F4F6F8"
BRAND_MID_GRAY = "#8C9BB2"
BRAND_ACCENT_ORANGE = "#FF6B35"
BRAND_ACCENT_YELLOW = "#FFD166"


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def _looks_like_qualtrics_raw_export(path: Path) -> bool:
    try:
        preview = pd.read_csv(path, header=None, nrows=3, dtype=str, keep_default_na=False)
    except Exception:
        return False
    if preview.shape[0] < 3:
        return False
    row2 = [str(value).strip() for value in preview.iloc[1].tolist()]
    row3 = [str(value).strip() for value in preview.iloc[2].tolist()]
    has_import_ids = any(value.upper().startswith("QID") or value == "ResponseID" for value in row3 if value)
    has_question_text = any(value and " " in value for value in row2)
    return has_import_ids and has_question_text


def load_survey_data(path: str | Path) -> pd.DataFrame:
    """Load CSV survey data and return a cleaned DataFrame."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    read_kwargs = {}
    if _looks_like_qualtrics_raw_export(path):
        read_kwargs["skiprows"] = [1, 2]
        logger.info("Detected raw Qualtrics export format in %s; skipping question text and import ID rows.", path.name)

    read_kwargs.setdefault("low_memory", False)
    df = pd.read_csv(path, **read_kwargs)
    logger.info("Loaded %d rows × %d columns from %s", *df.shape, path.name)
    return df


def validate_columns(
    df: pd.DataFrame,
    target: str,
    predictors: list[str],
) -> None:
    """Raise ValueError if required columns are missing or invalid."""
    missing = [c for c in [target] + predictors if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in dataset: {missing}")

    # Check for numeric types
    for col in [target] + predictors:
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise ValueError(f"Column '{col}' must be numeric.")

    # Warn about missing values
    nulls = df[[target] + predictors].isnull().sum()
    if nulls.any():
        logger.warning("Null values detected:\n%s", nulls[nulls > 0])


def prepare_data(
    df: pd.DataFrame,
    target: str,
    predictors: list[str],
    dropna: bool = True,
) -> tuple[pd.DataFrame, pd.Series]:
    """Return (X, y) with optional NA drop."""
    cols = [target] + predictors
    subset = df[cols]
    if dropna:
        before = len(subset)
        subset = subset.dropna()
        dropped = before - len(subset)
        if dropped:
            logger.info("Dropped %d rows with NAs.", dropped)

    X = subset[predictors]
    y = subset[target]
    return X, y


def prepare_sparse_model_data(
    df: pd.DataFrame,
    target: str,
    predictors: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, dict, dict[str, int]]:
    """
    Prepare sparse survey data for modeling.

    Eligibility:
    - target must be non-null
    - at least one predictor must be non-null

    Modeling strategy in v1:
    - retain eligible respondents
    - median-impute predictor values for model compatibility
    - do not impute the target
    - emit missingness metadata and driver-level usable N
    """
    cols = [target] + predictors
    subset = df[cols].copy()

    valid_dv = subset[target].notna()
    any_predictor = subset[predictors].notna().any(axis=1)
    eligible = subset.loc[valid_dv & any_predictor].copy()

    if eligible.empty:
        raise ValueError("No eligible respondents remain after requiring valid DV and at least one predictor.")

    driver_usable_n = {col: int(eligible[[target, col]].dropna().shape[0]) for col in predictors}

    missingness_summary = {
        "by_variable": {
            col: {
                "missing_count": int(subset[col].isna().sum()),
                "missing_rate": round(float(subset[col].isna().mean()), 4),
            }
            for col in cols
        }
    }

    X_raw = eligible[predictors].copy()
    X_model = X_raw.copy()
    for col in predictors:
        median = X_model[col].median()
        if pd.isna(median):
            raise ValueError(f"Predictor '{col}' has no usable values after eligibility filtering.")
        X_model[col] = X_model[col].fillna(median)

    y = eligible[target].copy()
    return eligible, X_model, y, missingness_summary, driver_usable_n


def write_json(path: str | Path, payload: dict) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


def standardize(df: pd.DataFrame) -> pd.DataFrame:
    """Z-score standardize all columns."""
    return (df - df.mean()) / df.std(ddof=1)


def scale_to_range(arr: np.ndarray, lo: float = 0, hi: float = 1) -> np.ndarray:
    """Min-max scale array to [lo, hi]."""
    mn, mx = arr.min(), arr.max()
    if mx == mn:
        return np.full_like(arr, (lo + hi) / 2, dtype=float)
    return lo + (arr - mn) / (mx - mn) * (hi - lo)


def human_label(col: str) -> str:
    """Convert snake_case column names to 'Title Case' labels."""
    return col.replace("_", " ").title()


def output_path(output_dir: str | Path, filename: str) -> Path:
    """Return full path inside output_dir, creating it if needed."""
    p = Path(output_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p / filename
