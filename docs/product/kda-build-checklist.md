# Tundralis KDA Build Checklist

## Phase 1 — Contract lock
- [ ] Finalize CSV-first input contract
- [ ] Decide explicit v1 position on weighting (`unsupported` vs fully implemented)
- [ ] Create `schemas/kda-analysis-run.schema.json`
- [ ] Create `schemas/kda-input.schema.json` if we want machine-validated run configs
- [ ] Add payload sections required by the deck blueprint

## Phase 2 — Pipeline payload
- [ ] Build a payload assembler from current analysis outputs
- [ ] Add performance normalization and headroom calculation
- [ ] Add opportunity calculation
- [ ] Add classification logic
- [ ] Add missing-data strategy for sparse respondent rows
- [ ] Emit driver-level usable N and variable missingness metadata
- [ ] Add nonlinear benchmark placeholders or first-pass XGBoost output
- [ ] Emit `analysis-run.json`
- [ ] Validate emitted JSON against schema

## Phase 3 — Renderer alignment
- [ ] Refactor PPTX generator to consume payload JSON
- [ ] Map slide blueprint to payload sections
- [ ] Generate classic importance × performance matrix
- [ ] Generate modern performance × impact bubble chart
- [ ] Generate opportunity ranking table
- [ ] Add confidence / method-agreement slide

## Phase 4 — Fixture harness
- [ ] Promote sample data into a stable fixture
- [ ] Save expected-output snapshot
- [ ] Add schema validation test
- [ ] Add report smoke test
- [ ] Add top-priority regression test

## Phase 5 — Thin operator flow
- [ ] One clean CLI command for end-to-end generation
- [ ] Save artifacts to predictable output directory
- [ ] Return clear validation errors
- [ ] Add README section for the golden path demo

## Definition of done
- [ ] One command produces valid JSON + polished PPTX from the fixture dataset
- [ ] Tests pass locally
- [ ] Output is good enough to show a prospect without apology
