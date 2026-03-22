# Tundralis KDA Golden Path Plan

## Goal

Ship the first end-to-end KDA product slice:

1. ingest one survey file
2. validate against a canonical contract
3. run the KDA pipeline
4. emit a stable presentation-ready JSON payload
5. render a polished `.pptx`
6. return both artifacts reliably

This is the shortest path from "analytics prototype" to "real product skeleton".

---

## Product boundary for v1

### In scope
- One analysis type: KDA
- One primary input type: CSV first, XLSX second
- One target variable at a time
- Numeric/Likert-style predictors only
- One default deck template
- One recommendation style
- One canonical demo dataset + regression harness

### Explicitly out of scope
- Billing
- Auth complexity
- Multi-study orchestration
- Segmentation builder UI
- Open-ended text analysis
- Weights unless implemented as a clearly supported optional field
- Full analyst-workbench flexibility

---

## Golden path deliverables

### 1. Canonical input contract
Define exactly:
- required file types
- required column metadata
- allowed scale ranges
- target variable selection rules
- missing-data handling rules
- optional respondent id / segment / weight columns
- predictor inclusion / exclusion behavior

### 2. Stable analysis-output contract
The analysis layer must emit a single JSON object that is sufficient to:
- populate the deck
- generate tables and charts
- drive recommendation logic
- support future API/UI delivery

This object becomes the boundary between analytics and presentation.

### 3. Deck renderer contract
The renderer should consume only:
- `analysis-run.json`
- optional branding/template config

The renderer should not recompute business logic.

### 4. Regression fixture
Maintain one fixed dataset and one expected-output harness that verifies:
- analysis completes
- schema validates
- deck renders
- top-driver ordering is stable enough to catch breakage

---

## Recommended repo shape

```text
Tundralis/
├── data/
│   ├── fixtures/
│   │   ├── kda_demo.csv
│   │   └── kda_demo.expected.json
│   └── samples/
├── docs/
│   ├── methodology/
│   └── product/
│       ├── kda-golden-path-plan.md
│       ├── kda-input-contract.md
│       ├── kda-build-checklist.md
│       └── kda-repo-structure.md
├── schemas/
│   ├── kda-input.schema.json
│   └── kda-analysis-run.schema.json
├── tests/
│   ├── test_analysis_schema.py
│   ├── test_fixture_regression.py
│   └── test_report_generation.py
├── tundralis/
│   ├── ingestion/
│   │   ├── loaders.py
│   │   ├── contract.py
│   │   └── mapping.py
│   ├── kda/
│   │   ├── pipeline.py
│   │   ├── metrics.py
│   │   ├── opportunity.py
│   │   └── narratives.py
│   ├── rendering/
│   │   ├── charts.py
│   │   ├── pptx_renderer.py
│   │   └── template.py
│   ├── schemas/
│   │   └── validators.py
│   └── cli.py
└── output/
```

---

## Execution order

### Phase 1 — Contract first
1. lock input contract
2. lock output schema
3. map current code to the new schema
4. identify gaps between current analysis objects and required report payload

### Phase 2 — Stable pipeline payload
1. create `analysis-run.json` emitter
2. derive classifications, opportunity, and chart payloads inside the pipeline
3. validate emitted JSON against schema
4. save artifacts for fixture dataset

### Phase 3 — Renderer rewrite around the contract
1. make renderer read schema payload instead of internal Python objects
2. map slide blueprint directly to payload sections
3. generate `.pptx`
4. compare output against the blueprint until it feels sellable

### Phase 4 — Harness + demo
1. add fixture test
2. add schema validation test
3. add report-generation smoke test
4. store one demo-grade report in `output/demo/`

---

## Hard product decisions for v1

### File format
- **Ship CSV first.**
- Add XLSX only after the contract is stable.

Reason: fewer parsing edge cases, faster iteration, easier test fixtures.

### Target variable handling
- Require one explicit target column.
- Do not infer target automatically in v1.

Reason: removes ambiguity and makes failure states clean.

### Predictor handling
- Auto-include numeric predictors except excluded meta columns.
- Allow manual override list.
- Skip non-numeric fields by default.

### Missing data
- Require a valid target value.
- Require at least one valid predictor value.
- Allow partial predictor missingness.
- For descriptive metrics, use pairwise-available observations where appropriate.
- For multivariate modeling, use an explicit sparse-data strategy instead of blanket listwise deletion.
- Emit missingness and usable-N metadata clearly.

### Weights
- Support only if fully wired through all metrics.
- Otherwise declare **not supported in v1**.

### Recommendations
- Deterministic template logic first.
- Optional LLM copy-polish later.

Reason: the core product must work without an LLM dependency.

---

## Success criteria

The golden path is working when Nick can do this:

> run one command with a clean CSV and get back a valid JSON payload plus a client-ready deck without manual cleanup.

Minimum acceptance bar:
- input validation errors are clear
- schema output is stable
- deck contains executive summary, importance, impact, classic matrix, action matrix, opportunity ranking, and recommendations
- fixture test passes consistently

---

## Immediate next build tasks

1. create `schemas/kda-analysis-run.schema.json`
2. write `docs/product/kda-input-contract.md`
3. refactor current `KDAResults` into a presentation-ready payload builder
4. write a fixture regression test around `data/sample_survey.csv`
5. decouple renderer from ad hoc internal objects
