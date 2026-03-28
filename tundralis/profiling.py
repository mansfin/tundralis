from __future__ import annotations

from collections import Counter
from math import isfinite

import pandas as pd


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


def profile_column(df: pd.DataFrame, column: str) -> dict:
    series = df[column]
    non_null = series.dropna()
    inferred_type = _inferred_type(series)
    profile = {
        "column": column,
        "inferred_type": inferred_type,
        "non_null_count": int(series.notna().sum()),
        "missing_count": int(series.isna().sum()),
        "missing_pct": _missing_pct(series),
        "distinct_count": int(non_null.nunique(dropna=True)),
        "top_values": _top_values(series),
        "warnings": _warnings(series, inferred_type),
        "sample_values": [str(v) for v in non_null.astype(str).head(5).tolist()],
    }

    numeric_summary = _numeric_summary(series)
    if numeric_summary:
        profile["numeric_summary"] = numeric_summary

    return profile


def profile_dataframe(df: pd.DataFrame, sample_rows: int = PROFILE_SAMPLE_ROWS) -> dict[str, dict]:
    profile_df = df.head(sample_rows) if sample_rows and len(df) > sample_rows else df
    return {column: profile_column(profile_df, column) for column in profile_df.columns}
