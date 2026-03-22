from __future__ import annotations

import pandas as pd


ALLOWED_RECODE_TYPES = {"map_values", "bucket_numeric", "boolean_flag"}


def _coerce_scalar(value: str):
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value
    text = str(value).strip()
    if text == "":
        return ""
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def validate_recode_definitions(recode_definitions: list[dict]) -> None:
    for idx, recode in enumerate(recode_definitions):
        recode_type = recode.get("type")
        source_column = recode.get("source_column")
        output_column = recode.get("output_column")
        if recode_type not in ALLOWED_RECODE_TYPES:
            raise ValueError(f"Recode #{idx + 1} has invalid type: {recode_type}")
        if not source_column:
            raise ValueError(f"Recode #{idx + 1} is missing source_column")
        if not output_column:
            raise ValueError(f"Recode #{idx + 1} is missing output_column")
        if source_column == output_column:
            raise ValueError(f"Recode #{idx + 1} output_column must differ from source_column")

        if recode_type == "map_values" and not recode.get("mapping"):
            raise ValueError(f"Recode #{idx + 1} map_values requires mapping")
        if recode_type == "bucket_numeric" and not recode.get("bins"):
            raise ValueError(f"Recode #{idx + 1} bucket_numeric requires bins")
        if recode_type == "boolean_flag" and not recode.get("operator"):
            raise ValueError(f"Recode #{idx + 1} boolean_flag requires operator")


def _apply_map_values(series: pd.Series, recode: dict) -> pd.Series:
    mapping = {_coerce_scalar(k): v for k, v in recode.get("mapping", {}).items()}
    mapped = series.map(lambda value: mapping.get(value, mapping.get(str(value), value)) if pd.notna(value) else value)
    default_value = recode.get("default_value")
    if default_value not in (None, ""):
        mapped = mapped.fillna(default_value)
    return mapped


def _apply_bucket_numeric(series: pd.Series, recode: dict) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    bins = recode.get("bins", [])
    output = pd.Series(pd.NA, index=series.index, dtype="object")
    for bucket in bins:
        label = bucket.get("label")
        min_value = bucket.get("min")
        max_value = bucket.get("max")
        include_min = bucket.get("include_min", True)
        include_max = bucket.get("include_max", True)

        mask = numeric.notna()
        if min_value is not None:
            mask &= numeric.ge(min_value) if include_min else numeric.gt(min_value)
        if max_value is not None:
            mask &= numeric.le(max_value) if include_max else numeric.lt(max_value)
        output.loc[mask] = label
    if recode.get("else_label") not in (None, ""):
        output = output.fillna(recode.get("else_label"))
    return output


def _apply_boolean_flag(series: pd.Series, recode: dict) -> pd.Series:
    operator = recode.get("operator")
    value = _coerce_scalar(recode.get("value"))
    output_true = recode.get("true_value", True)
    output_false = recode.get("false_value", False)

    if operator in {"gt", "gte", "lt", "lte"}:
        left = pd.to_numeric(series, errors="coerce")
    else:
        left = series

    if operator == "equals":
        mask = left == value
    elif operator == "not_equals":
        mask = left != value
    elif operator == "contains":
        mask = left.astype("string").str.contains(str(value), case=False, na=False)
    elif operator == "in":
        values = [_coerce_scalar(v) for v in str(recode.get("value", "")).split("|") if str(v).strip()]
        mask = left.isin(values)
    elif operator == "gt":
        mask = left > value
    elif operator == "gte":
        mask = left >= value
    elif operator == "lt":
        mask = left < value
    elif operator == "lte":
        mask = left <= value
    else:
        raise ValueError(f"Unsupported boolean_flag operator: {operator}")
    return pd.Series(output_false, index=series.index).where(~mask, output_true)


def apply_recode_transforms(df: pd.DataFrame, recode_definitions: list[dict] | None) -> pd.DataFrame:
    recode_definitions = recode_definitions or []
    validate_recode_definitions(recode_definitions)

    transformed = df.copy()
    for recode in recode_definitions:
        source_column = recode["source_column"]
        output_column = recode["output_column"]
        if source_column not in transformed.columns:
            raise ValueError(f"Recode source column not found: {source_column}")
        if output_column in transformed.columns:
            raise ValueError(f"Recode output column already exists: {output_column}")

        source = transformed[source_column]
        if recode["type"] == "map_values":
            transformed[output_column] = _apply_map_values(source, recode)
        elif recode["type"] == "bucket_numeric":
            transformed[output_column] = _apply_bucket_numeric(source, recode)
        elif recode["type"] == "boolean_flag":
            transformed[output_column] = _apply_boolean_flag(source, recode)
        else:
            raise ValueError(f"Unsupported recode type: {recode['type']}")

    return transformed
