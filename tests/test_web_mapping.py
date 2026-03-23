import io
import json
import unittest
from pathlib import Path

from tundralis.app import app

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
        self.assertIn("Column inspector", html)
        self.assertIn("Data shaping", html)
        self.assertIn("Analysis setup", html)
        self.assertIn("Segment builder", html)
        self.assertIn("Review + run", html)
        self.assertIn("Ready to run", html)
        self.assertIn("toggleInspectorButton", html)
        self.assertIn("segmentColumnSearch", html)
        self.assertIn("launchRecodeBuilder", html)
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
