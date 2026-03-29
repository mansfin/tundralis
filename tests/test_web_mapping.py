import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tundralis.app import INSPECT_ERROR_LOG, app

ROOT = Path(__file__).resolve().parents[1]


class TestWebMapping(unittest.TestCase):
    def test_inspect_renders_original_filename_without_job_prefix(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()

        response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "Google Policy Measurement Weighted Data (Numeric) Ver 1.0.csv")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("File: <strong>Google Policy Measurement Weighted Data (Numeric) Ver 1.0.csv</strong>", html)
        marker = 'name="filename" value="'
        start = html.index(marker) + len(marker)
        stored_filename = html[start: html.index('"', start)]
        self.assertNotEqual(stored_filename, "Google Policy Measurement Weighted Data (Numeric) Ver 1.0.csv")
        self.assertTrue(stored_filename.endswith("_Google Policy Measurement Weighted Data (Numeric) Ver 1.0.csv"))

    def test_upload_xhr_returns_redirect_url(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()

        response = client.post(
            "/upload",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("job_id", payload)
        self.assertIn("redirect_url", payload)
        self.assertTrue(payload["redirect_url"].endswith(f"/mapping/{payload['job_id']}"))
        follow = client.get(payload["redirect_url"])
        self.assertEqual(follow.status_code, 200)
        self.assertIn("Run + download", follow.get_data(as_text=True))

    def test_inspect_renders_column_inspector(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()

        response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Field inspector", html)
        self.assertIn("Adjust data setup", html)
        self.assertIn("Analysis setup", html)
        self.assertIn("Segments", html)
        self.assertIn("Run + download", html)
        self.assertIn("Ready to run", html)
        self.assertIn("toggleInspectorButton", html)
        self.assertIn("segmentColumnSearch", html)
        self.assertIn("launchRecodeBuilder", html)
        self.assertIn("semanticOverridesInput", html)
        self.assertIn("Clarify numeric meaning", html)
        self.assertIn("recodeSourceColumnSelector", html)
        self.assertIn("column-selector-search", html)
        self.assertIn("inspectOutcomeButton", html)
        self.assertIn("Nested condition tree", html)
        self.assertIn("segmentTreeCanvas", html)
        self.assertIn("overall_sat", html)
        self.assertIn("high_cardinality", html)
        self.assertIn("client_style_kda.csv", html)

    def test_preview_applies_recode_and_returns_segment_counts(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()
        inspect_response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
        )
        html = inspect_response.get_data(as_text=True)
        marker = 'name="filename" value="'
        start = html.index(marker) + len(marker)
        filename = html[start: html.index('"', start)]

        response = client.post(
            "/preview",
            json={
                "filename": filename,
                "recode_definitions": [
                    {
                        "type": "map_values",
                        "source_column": "segment",
                        "output_column": "segment_group",
                        "mapping": {
                            "SMB": "Commercial",
                            "Mid-Market": "Commercial",
                            "Enterprise": "Enterprise",
                        },
                    }
                ],
                "segment_definitions": [
                    {
                        "name": "Enterprise only",
                        "tree": {
                            "all": [
                                {"column": "segment_group", "operator": "equals", "value": "Enterprise"}
                            ]
                        },
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("segment_group", payload["columns"])
        self.assertEqual(payload["segment_previews"][0]["name"], "Enterprise only")
        self.assertGreater(payload["segment_previews"][0]["matched_count"], 0)

    def test_mapping_page_reloads_saved_draft_state(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()

        inspect_response = client.post(
            "/upload",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        )
        payload = inspect_response.get_json()
        job_id = payload["job_id"]
        filename = payload["filename"]

        preview_response = client.post(
            "/preview",
            json={
                "job_id": job_id,
                "filename": filename,
                "target_column": "overall_sat",
                "predictor_columns": ["product_quality_score", "ease_use_score"],
                "display_name_map": {"overall_sat": "Overall satisfaction"},
                "semantic_overrides": {"overall_sat": "ordinal_numeric", "segment": "labeled_categorical"},
                "recode_definitions": [
                    {
                        "type": "boolean_flag",
                        "source_column": "region",
                        "output_column": "is_apac",
                        "operator": "equals",
                        "value": "APAC",
                    }
                ],
                "segment_definitions": [
                    {
                        "name": "Enterprise only",
                        "tree": {"all": [{"column": "segment", "operator": "equals", "value": "Enterprise"}]},
                    }
                ],
            },
        )
        self.assertEqual(preview_response.status_code, 200)

        mapping_response = client.get(f"/mapping/{job_id}")
        self.assertEqual(mapping_response.status_code, 200)
        html = mapping_response.get_data(as_text=True)
        self.assertIn('let savedRecodesState = [{', html)
        self.assertIn('"output_column": "is_apac"', html)
        self.assertIn('let savedPredictorSelections = ["product_quality_score", "ease_use_score"]', html)
        self.assertIn('let savedSemanticOverrides = {"overall_sat": "ordinal_numeric", "segment": "labeled_categorical"}', html)
        self.assertIn('Overall satisfaction', html)

    def test_inspect_failure_returns_error_id_and_logs_traceback(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()
        if INSPECT_ERROR_LOG.exists():
            INSPECT_ERROR_LOG.unlink()

        response = client.post(
            "/upload",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()

        with patch("tundralis.app.build_prep_bundle", side_effect=ValueError("broken inspect step")):
            mapping_response = client.get(payload["redirect_url"])

        self.assertEqual(mapping_response.status_code, 500)
        html = mapping_response.get_data(as_text=True)
        self.assertIn("Inspect failed", html)
        self.assertTrue(INSPECT_ERROR_LOG.exists())
        log_text = INSPECT_ERROR_LOG.read_text(encoding="utf-8")
        self.assertIn("broken inspect step", log_text)

    def test_mapping_page_includes_recode_create_handler(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()

        inspect_response = client.post(
            "/upload",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        )
        payload = inspect_response.get_json()
        mapping_response = client.get(payload["redirect_url"])
        self.assertEqual(mapping_response.status_code, 200)
        html = mapping_response.get_data(as_text=True)
        self.assertIn("launchRecodeBuilder?.addEventListener('click'", html)
        self.assertIn("priorIndex !== null ? 'Updated' : 'Created'", html)

    def test_mapping_page_includes_recode_edit_and_remove_handlers(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()

        inspect_response = client.post(
            "/upload",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        )
        payload = inspect_response.get_json()
        mapping_response = client.get(payload["redirect_url"])
        self.assertEqual(mapping_response.status_code, 200)
        html = mapping_response.get_data(as_text=True)
        self.assertIn("let editingRecodeIndex = null;", html)
        self.assertIn("data-edit-recode", html)
        self.assertIn("data-remove-recode", html)
        self.assertIn("editingRecodeIndex === idx", html)
        self.assertIn("Removed transform", html)

    def test_preview_rejects_invalid_numeric_operator_on_text_column(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()
        inspect_response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
        )
        html = inspect_response.get_data(as_text=True)
        marker = 'name="filename" value="'
        start = html.index(marker) + len(marker)
        filename = html[start: html.index('"', start)]

        response = client.post(
            "/preview",
            json={
                "filename": filename,
                "segment_definitions": [
                    {
                        "name": "Bad segment",
                        "tree": {
                            "all": [
                                {"column": "segment", "operator": "gt", "value": 5}
                            ]
                        },
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertIn("requires a numeric column", payload["error"])

    def test_run_persists_segment_summaries(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()
        inspect_response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
        )
        html = inspect_response.get_data(as_text=True)
        marker = 'name="filename" value="'
        start = html.index(marker) + len(marker)
        filename = html[start: html.index('"', start)]
        job_marker = 'name="job_id" value="'
        job_start = html.index(job_marker) + len(job_marker)
        job_id = html[job_start: html.index('"', job_start)]

        response = client.post(
            "/run",
            data={
                "job_id": job_id,
                "filename": filename,
                "target_column": "overall_sat",
                "predictor_columns": [
                    "product_quality_score",
                    "ease_use_score",
                    "support_experience",
                    "value_for_money",
                ],
                "segment_columns": ["segment", "region"],
                "segment_definitions": json.dumps([
                    {
                        "name": "Enterprise only",
                        "tree": {
                            "all": [
                                {"column": "segment", "operator": "equals", "value": "Enterprise"}
                            ]
                        },
                    }
                ]),
                "recode_definitions": "[]",
            },
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Enterprise only", html)
        self.assertIn("Segment summaries", html)


if __name__ == "__main__":
    unittest.main()
