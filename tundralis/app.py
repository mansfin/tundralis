from __future__ import annotations

import base64
import json
import os
import subprocess
import uuid
from functools import wraps
from pathlib import Path

from flask import Flask, Response, abort, render_template, request, send_from_directory

from tundralis.analysis import run_kda
from tundralis.charts import chart_importance_bar, chart_model_fit, chart_quadrant
from tundralis.ingestion import infer_predictors, load_mapping_config, resolve_config, validate_resolved_config
from tundralis.utils import load_survey_data, prepare_sparse_model_data

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "app_runtime"
UPLOAD_DIR = RUNTIME_DIR / "uploads"
MAPPING_DIR = RUNTIME_DIR / "mappings"
ARTIFACT_DIR = RUNTIME_DIR / "artifacts"
for p in [UPLOAD_DIR, MAPPING_DIR, ARTIFACT_DIR]:
    p.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, template_folder=str(ROOT / "web" / "templates"), static_folder=str(ROOT / "web" / "static"))


def _auth_ok() -> bool:
    required_user = os.environ.get("TUNDRALIS_BASIC_AUTH_USER")
    required_pass = os.environ.get("TUNDRALIS_BASIC_AUTH_PASS")
    if not required_user or not required_pass:
        return True
    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
        user, pw = decoded.split(":", 1)
    except Exception:
        return False
    return user == required_user and pw == required_pass


def _require_auth():
    return Response("Authentication required", 401, {"WWW-Authenticate": 'Basic realm="tundralis"'})


def basic_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not _auth_ok():
            return _require_auth()
        return view(*args, **kwargs)
    return wrapped


def _job_dir(job_id: str) -> Path:
    p = ARTIFACT_DIR / job_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write_preview_charts(job_id: str, data_path: Path, mapping_path: Path) -> list[str]:
    df = load_survey_data(data_path)

    class Args:
        target = None
        predictors = None

    mapping = load_mapping_config(mapping_path)
    config = resolve_config(df, Args(), mapping)
    validate_resolved_config(df, config)
    _, X, y, _, _ = prepare_sparse_model_data(df, config.target_column, config.predictor_columns)
    results = run_kda(X, y, target_name=config.target_column)

    previews = {
        "importance_bar.png": chart_importance_bar(results.importance.ranking),
        "priority_matrix.png": chart_quadrant(results.quadrants.quadrant_df),
        "model_fit.png": chart_model_fit(results.meta["r_squared"], results.meta["adj_r_squared"]),
    }
    out = _job_dir(job_id)
    for name, content in previews.items():
        (out / name).write_bytes(content)
    return list(previews.keys())


def _detect_target(columns: list[str], numeric_columns: list[str]) -> str | None:
    target_candidates = ["overall_satisfaction", "overall_sat", "overall", "nps", "likelihood_to_recommend"]
    inferred_target = next((c for c in target_candidates if c in columns), None)
    if inferred_target is None and numeric_columns:
        inferred_target = next((c for c in numeric_columns if "overall" in c.lower() or "satisfaction" in c.lower()), numeric_columns[0])
    return inferred_target


def _suggested_predictors(df, inferred_target: str | None) -> list[str]:
    if not inferred_target:
        return []
    preds = infer_predictors(df, inferred_target)
    return [c for c in preds if c != inferred_target and not c.lower().endswith("_id")]


@app.get("/")
@basic_auth
def index():
    return render_template("index.html")


@app.post("/inspect")
@basic_auth
def inspect_file():
    f = request.files.get("survey_file")
    if not f or not f.filename:
        return render_template("index.html", error="Upload a CSV first."), 400

    job_id = uuid.uuid4().hex[:12]
    upload_path = UPLOAD_DIR / f"{job_id}_{Path(f.filename).name}"
    f.save(upload_path)

    df = load_survey_data(upload_path)
    columns = list(df.columns)
    numeric_columns = df.select_dtypes(include="number").columns.tolist()
    inferred_target = _detect_target(columns, numeric_columns)
    inferred_predictors = _suggested_predictors(df, inferred_target)

    return render_template(
        "mapping.html",
        job_id=job_id,
        filename=upload_path.name,
        columns=columns,
        numeric_columns=numeric_columns,
        inferred_target=inferred_target,
        inferred_predictors=inferred_predictors,
    )


@app.post("/run")
@basic_auth
def run_job():
    job_id = request.form.get("job_id") or uuid.uuid4().hex[:12]
    filename = request.form.get("filename")
    if not filename:
        abort(400)

    data_path = UPLOAD_DIR / filename
    predictors = request.form.getlist("predictor_columns")
    target_column = request.form.get("target_column")
    segment_columns = request.form.getlist("segment_columns")

    display_name_map = {}
    for key, value in request.form.items():
        if key.startswith("display_name__") and value.strip():
            display_name_map[key.split("display_name__", 1)[1]] = value.strip()

    mapping = {
        "target_column": target_column,
        "segment_columns": segment_columns,
        "predictor_columns": predictors,
        "display_name_map": display_name_map,
    }
    mapping_path = MAPPING_DIR / f"{job_id}.json"
    mapping_path.write_text(json.dumps(mapping, indent=2), encoding="utf-8")

    job_dir = _job_dir(job_id)
    json_path = job_dir / "analysis_run.json"
    pptx_path = job_dir / "report.pptx"

    cmd = [
        str(ROOT / ".venv" / "bin" / "python"),
        str(ROOT / "tundralis_kda.py"),
        "--data", str(data_path),
        "--mapping-config", str(mapping_path),
        "--no-ai",
        "--json-output", str(json_path),
        "--output", str(pptx_path),
    ]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)

    if result.returncode != 0:
        df = load_survey_data(data_path)
        columns = list(df.columns)
        numeric_columns = df.select_dtypes(include="number").columns.tolist()
        inferred_target = _detect_target(columns, numeric_columns)
        inferred_predictors = _suggested_predictors(df, inferred_target)
        return render_template(
            "mapping.html",
            error=result.stderr or result.stdout or "Run failed.",
            job_id=job_id,
            filename=filename,
            columns=columns,
            numeric_columns=numeric_columns,
            inferred_target=inferred_target,
            inferred_predictors=inferred_predictors,
        ), 500

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    preview_images = _write_preview_charts(job_id, data_path, mapping_path)
    return render_template(
        "result.html",
        job_id=job_id,
        filename=filename,
        payload=payload,
        logs=result.stdout,
        preview_images=preview_images,
    )


@app.get("/artifacts/<job_id>/<path:name>")
@basic_auth
def artifacts(job_id: str, name: str):
    return send_from_directory(_job_dir(job_id), name, as_attachment=False)


if __name__ == "__main__":
    host = os.environ.get("TUNDRALIS_HOST", "127.0.0.1")
    port = int(os.environ.get("TUNDRALIS_PORT", "7860"))
    app.run(host=host, port=port, debug=False)
