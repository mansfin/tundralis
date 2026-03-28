import io
import re
import unittest
from pathlib import Path

from tundralis.app import app

ROOT = Path(__file__).resolve().parents[1]


class TestRecommendationInference(unittest.TestCase):
    def test_mapping_prefers_business_outcome_and_filters_identifier_fields(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()

        response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('let recommendationState = {', html)
        self.assertIn('"target": "overall_sat"', html)
        self.assertIn('"name": "product_quality_score"', html)
        self.assertIn('"name": "response_id"', html)
        self.assertIn('"reason_labels": ["Likely ID"', html)

    def test_recommendation_shortlists_default_driver_count(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "qualtrics_raw_export.csv").read_bytes()

        response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "qualtrics_raw_export.csv")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('"driver_shortlist_limit": 24', html)

    def test_recommendation_exposes_outcome_candidates(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()

        response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertRegex(html, r'"outcome_candidates": \[')


if __name__ == "__main__":
    unittest.main()
