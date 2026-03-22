# Tundralis KDA Input Contract v1

## Supported input modes

### v1 supported
- CSV (`.csv`)

### v1.1 candidate
- Excel (`.xlsx`)

Ship CSV first. Keep the parser boring.

---

## One-file contract

Each run accepts one rectangular respondent-level dataset with:
- one row per respondent
- one target column
- zero or one respondent id column
- zero or one weight column
- zero or more segment columns
- one or more predictor columns

---

## Required run configuration

The run must specify:
- `target_column`
- optional `predictor_columns`
- optional `respondent_id_column`
- optional `weight_column`
- optional `segment_columns`
- optional `excluded_columns`
- optional scale metadata

### Why require explicit target selection
Because guessing the business outcome is how you get a demo that lies with confidence.

---

## Column classes

### 1. Target column
Required.

Rules:
- numeric
- one column only
- not constant
- at least 2 distinct non-null values
- recommended scale: Likert-style 1-5, 1-7, 0-10, or normalized 0-100

### 2. Predictor columns
At least one required.

Rules:
- numeric in v1
- non-constant
- enough variance to model
- same conceptual direction preferred (higher = better) for clean recommendation logic

### 3. Respondent id column
Optional.

Rules:
- unique preferred, not required
- excluded from modeling

### 4. Weight column
Optional but **not supported in scoring unless explicitly enabled across the full pipeline**.

v1 decision:
- parse allowed
- include in metadata
- reject weighted execution unless weighting is fully wired through analysis methods

### 5. Segment columns
Optional.

Rules:
- retained for metadata/future cuts
- excluded from v1 modeling unless explicitly encoded later

---

## Scale rules

### Preferred scales
- 1-5
- 1-7
- 0-10
- 0-100

### v1 handling
- infer min/max from provided metadata when available
- otherwise infer from observed data
- store inferred scale in output metadata

### Mixed scales
Allowed only if they are declared or reliably inferable.
If mixed scales exist, normalize for reporting and opportunity calculations.

---

## Missing data policy

### Default
A respondent is eligible for inclusion when they have:
- a non-missing target value
- at least one non-missing predictor value

### v1 handling
- do **not** require complete rows across all predictors
- preserve respondents with partial predictor coverage
- compute driver-level metrics using all respondents with valid data for that driver and the target where methodologically appropriate
- use pairwise-available data for bivariate summaries where safe
- for multivariate modeling, use a defined incomplete-data strategy rather than blanket complete-case deletion

### Recommended v1 implementation
Use a two-layer policy:
- **descriptive / bivariate metrics**: pairwise available observations
- **multivariate model**: impute predictors with a transparent baseline strategy plus missingness flags where needed, or use a modeling approach that tolerates sparsity

### Non-negotiables
- never keep respondents with missing DV
- never silently pretend missingness did not happen
- emit per-driver usable N and model-level usable N
- surface missingness rates in metadata / confidence commentary

### Emit in metadata
- input row count
- respondent count with valid DV
- respondent count with valid DV + at least one predictor
- model-level usable N
- per-driver usable N
- missingness rate by variable
- rows excluded for missing DV

### v1 exclusions
- no black-box imputation
- no hidden analyst-only cleaning rules

### Strong recommendation
Do **not** use strict listwise deletion as the default. In real survey data it throws away too much information and makes the product feel brittle.

---

## Automatic predictor inclusion

If `predictor_columns` is not provided:
- include all numeric columns
- exclude target
- exclude respondent id
- exclude weight
- exclude explicitly excluded columns
- exclude columns with all nulls or zero variance

---

## Validation failures

Reject the run when:
- file type unsupported
- target missing
- target non-numeric
- fewer than 1 valid predictor
- too few usable rows after NA filtering
- target has zero variance
- all predictors have zero variance or are invalid

### Recommended minimums
- at least 100 usable rows for stable v1 reporting
- at least 3 valid predictors for a meaningful KDA story

Below that threshold:
- either fail hard
- or return `status = warning` with confidence downgrade

My recommendation: warn below threshold, fail only when modeling is mathematically broken.

---

## Example run config

```json
{
  "input_path": "data/fixtures/kda_demo.csv",
  "target_column": "overall_satisfaction",
  "predictor_columns": [
    "ease_of_use",
    "customer_support",
    "price_value",
    "reliability",
    "trust"
  ],
  "respondent_id_column": "respondent_id",
  "excluded_columns": ["country", "wave"],
  "segment_columns": ["segment"],
  "scale_metadata": {
    "overall_satisfaction": {"min": 1, "max": 7},
    "ease_of_use": {"min": 1, "max": 7},
    "customer_support": {"min": 1, "max": 7}
  }
}
```

---

## Recommended UX copy for errors

Bad:
- `ValueError: column invalid`

Good:
- `Target column 'overall_satisfaction' was not found in the uploaded file.`
- `Only 42 usable rows remained after removing missing values. Minimum recommended for v1 is 100.`
- `Predictor column 'customer_support' is non-numeric. v1 supports numeric predictors only.`
