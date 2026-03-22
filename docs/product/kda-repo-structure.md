# Tundralis KDA Repo Structure Recommendation

## Current state

The repo already has the right raw ingredients:
- analysis logic
- chart generation
- narrative generation
- report builder

But the current boundary is wrong for productization.

Right now the renderer is tightly coupled to in-memory analysis objects.
That makes it harder to:
- test
- version outputs
- expose an API later
- support alternate renderers

---

## Recommended boundary

### Rule
The analytics pipeline should emit a stable `analysis-run.json` artifact.

Everything downstream consumes that artifact.

That means:
- PowerPoint renderer reads the JSON
- future web app reads the JSON
- tests snapshot the JSON
- demo artifacts can be versioned cheaply

---

## Structure

```text
tundralis/
  ingestion/
    loaders.py          # csv/xlsx loading
    contract.py         # input validation and contract logic
    mapping.py          # role mapping and exclusions
  kda/
    pipeline.py         # orchestration
    metrics.py          # importance/impact/performance/opportunity
    benchmark.py        # xgboost benchmark
    classify.py         # priority classes
    payload.py          # build analysis-run payload
    narratives.py       # deterministic narrative generation
  rendering/
    charts.py           # chart images from payload
    pptx_renderer.py    # slide rendering from payload
    templates.py        # theme/layout config
  schemas/
    validators.py       # json schema validation
```

---

## Migration path from current code

### Keep
- `analysis.py` logic can seed `kda/metrics.py`
- `charts.py` can move under `rendering/`
- `report.py` can become `pptx_renderer.py`
- `utils.py` can be split across ingestion + shared helpers

### Add
- `payload.py`
- `contract.py`
- JSON schema validation
- fixture tests

### Remove later
- direct renderer dependency on `KDAResults`
- analysis-time formatting logic leaking into presentation

---

## Strong opinion

Do **not** build the UI first.

The correct order is:
1. contract
2. payload
3. renderer
4. tests
5. thin interface

Otherwise you end up polishing a shell around unstable guts, which is a very startup way to waste a week.
