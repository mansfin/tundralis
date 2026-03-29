# Tundralis KDA — Key Driver Analysis Pipeline

> **tundralis.com** · Professional survey analytics, automated.

A production-grade Python pipeline that takes survey data and produces a polished consulting-style PowerPoint report — complete with statistical analysis, priority matrices, and (optionally) AI-generated narratives.

Methodology direction is documented in `docs/methodology/`, including:
- `tundralis-methodology-spec.md`
- `driver-metrics-schema.json`
- `deck-blueprint.md`

---

## Features

- **Correlation Analysis** — Pearson & Spearman correlations with significance testing
- **OLS Regression** — Standardized coefficients (β) identifying each driver's unique contribution
- **Relative Importance** — Shapley value decomposition: the gold standard for driver importance
- **Priority Matrix** — Importance × Performance quadrant mapping (Priority Fixes, Strengths, Nice-to-Haves, Low Priority)
- **AI Narratives** — Executive summary, per-driver insights, and recommendations via OpenAI (optional)
- **PowerPoint Report** — Professional, branded slides ready for client delivery

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### Local secrets for browser/basic-auth work

Use a local-only secret file for credentials that should never enter git:

```bash
mkdir -p secrets
cp secrets/.env.example secrets/.env.local
```

Then set values in `secrets/.env.local`.

Current intended variables:
- `TUNDRALIS_BASIC_AUTH_USER`
- `TUNDRALIS_BASIC_AUTH_PASS`

Helper:

```bash
./scripts/load-local-secrets.sh <command>
```

Example:

```bash
./scripts/load-local-secrets.sh env | grep TUNDRALIS_BASIC_AUTH
```

Do not store these in `MEMORY.md`, Slack notes, or committed files.

### 2. Generate sample data (optional)

```bash
python generate_sample_data.py
```

This creates `data/sample_survey.csv` — 500 synthetic customer satisfaction responses with 10 predictor dimensions.

### 3. Run the pipeline

```bash
python tundralis_kda.py --data data/sample_survey.csv --target overall_satisfaction
```

Output: `output/overall_satisfaction_kda_report.pptx`

### 4. Run the messy client-style golden path

```bash
python tundralis_kda.py \
  --data data/fixtures/client_style_kda.csv \
  --mapping-config data/fixtures/client_style_kda_mapping.json \
  --no-ai
```

This exercises the first real ingestion path:
- explicit mapping config
- sparse missing data
- extra non-model columns
- segment metadata retained in payload

### 4. With AI narratives (requires OpenAI key)

```bash
export OPENAI_API_KEY=sk-...
python tundralis_kda.py --data data/sample_survey.csv --target overall_satisfaction
```

---

## CLI Options

```
usage: tundralis_kda.py [--data DATA] [--target TARGET]
                        [--predictors PREDICTOR [PREDICTOR ...]]
                        [--output OUTPUT]
                        [--openai-model MODEL]
                        [--no-ai]
                        [--log-level {DEBUG,INFO,WARNING,ERROR}]

Options:
  --data PATH           Input CSV file (required)
  --target COLUMN       Outcome/dependent variable column (required)
  --predictors ...      Predictor columns (default: all numeric except target)
  --output PATH         Output .pptx path (default: output/<target>_kda_report.pptx)
  --openai-model MODEL  OpenAI model to use (default: gpt-4o)
  --no-ai               Skip AI narrative generation
  --log-level LEVEL     Verbosity: DEBUG / INFO / WARNING / ERROR
```

**Examples:**

```bash
# Specify predictors manually
python tundralis_kda.py \
  --data data/sample_survey.csv \
  --target overall_satisfaction \
  --predictors ease_of_use customer_support price_value reliability

# Custom output path
python tundralis_kda.py \
  --data data/sample_survey.csv \
  --target overall_satisfaction \
  --output output/q1_report.pptx

# No AI (works without OpenAI key)
python tundralis_kda.py \
  --data data/sample_survey.csv \
  --target overall_satisfaction \
  --no-ai
```

---

## Input Format

Standard CSV with:
- One **outcome column** (numeric, e.g., 1–7 Likert scale or NPS score)
- Multiple **predictor columns** (numeric)

```csv
respondent_id,overall_satisfaction,ease_of_use,customer_support,price_value,...
1,6,5,3,4,...
2,4,4,2,5,...
```

Non-numeric columns (IDs, text) are ignored if not specified as predictors.

---

## Report Structure

| Slide | Content |
|-------|---------|
| 1 | Title & branding |
| 2 | Executive Summary (AI-generated or template) |
| 3 | Methodology overview |
| 4 | Key Drivers ranked by importance (bar chart) |
| 5 | Priority Matrix / quadrant chart |
| 6–N | Per-driver detail slides (importance, β, quadrant, insight) |
| N+1 | Recommendations (AI-generated or template) |
| N+2 | Appendix: Regression coefficients table |
| N+3 | Appendix: Correlation chart |
| N+4 | Appendix: Model fit summary |

---

## Color Scheme

| Token | Hex | Usage |
|-------|-----|-------|
| Dark Blue | `#1B2A4A` | Headers, backgrounds, primary text |
| Teal | `#2EC4B6` | Accents, highlights, top drivers |
| White | `#FFFFFF` | Slide backgrounds, text on dark |
| Mid Gray | `#8C9BB2` | Secondary text, low-priority |
| Orange | `#FF6B35` | Priority Fix quadrant |

---

## Project Structure

```
tundralis/
├── README.md
├── requirements.txt
├── tundralis_kda.py          # CLI entry point
├── generate_sample_data.py  # Synthetic data generator
├── tundralis/
│   ├── __init__.py
│   ├── analysis.py          # Correlation, OLS, Shapley importance
│   ├── narratives.py        # AI narrative generation (OpenAI)
│   ├── report.py            # PowerPoint report builder
│   ├── charts.py            # Matplotlib chart generation
│   └── utils.py             # Data loading, validation, helpers
├── data/
│   └── sample_survey.csv    # Synthetic dataset (500 rows)
└── output/                  # Generated reports
```

---

## Relative Importance Method

We use **Shapley value decomposition** (Johnson's epsilon / LMG method):

- Computes each predictor's marginal R² contribution across all possible orderings
- Correctly handles correlated predictors (unlike sequential R² methods)
- Values sum to the model's total R²
- Reported as % of explained variance for intuitive interpretation

For models with ≤8 predictors: exact Shapley (all permutations).  
For 9+ predictors: Monte Carlo approximation (500 random orderings).

---

## AI Narratives

When `OPENAI_API_KEY` is set, the pipeline generates:

1. **Executive Summary** — 3–5 sentence C-suite brief
2. **Driver Insights** — 2–3 sentence interpretation per driver
3. **Recommendations** — 4–6 actionable, prioritized recommendations

Without an API key, all narratives fall back to clean template-based text. The report is fully usable without AI.

---

## License

Proprietary — Tundralis LLC · tundralis.com
