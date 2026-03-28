import io
import unittest
from pathlib import Path

from tundralis.app import (
    app,
    _interpretability_score,
    _is_low_signal_code_name,
    _looks_like_battery_artifact,
    _looks_like_brand_tracker_debris,
    _looks_like_geo_artifact,
    _looks_like_text_artifact,
)

ROOT = Path(__file__).resolve().parents[1]


class TestRecommendationQuality(unittest.TestCase):
    def test_shortlist_limits_similar_field_families(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()
        response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('"family_limit": 3', html)
        self.assertIn('"ranked_families": [', html)

    def test_low_signal_code_names_are_penalized(self):
        self.assertTrue(_is_low_signal_code_name('V10'))
        self.assertTrue(_is_low_signal_code_name('Q125_4'))
        self.assertFalse(_is_low_signal_code_name('overall_sat'))

    def test_brand_tracker_debris_detection(self):
        self.assertTrue(_looks_like_brand_tracker_debris('Alaska'))
        self.assertTrue(_looks_like_brand_tracker_debris('Seg_N'))
        self.assertTrue(_looks_like_brand_tracker_debris('Q12.3Unfav'))
        self.assertFalse(_looks_like_brand_tracker_debris('overall_sat'))

    def test_text_geo_and_battery_artifact_detection(self):
        self.assertTrue(_looks_like_text_artifact('Q10.10_16_TEXT'))
        self.assertTrue(_looks_like_geo_artifact('zip10'))
        self.assertTrue(_looks_like_battery_artifact('Q10.10_16_TEXT'))
        self.assertFalse(_looks_like_geo_artifact('overall_sat'))

    def test_interpretability_prefers_named_constructs(self):
        self.assertLess(_interpretability_score('V10'), 0)
        self.assertLess(_interpretability_score('Q125_4'), 0)
        self.assertGreater(_interpretability_score('overall_satisfaction'), 0)
        self.assertGreater(_interpretability_score('sentiment_score'), 0)


if __name__ == "__main__":
    unittest.main()
