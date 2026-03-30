import unittest
from pathlib import Path

from tundralis.app import _build_recommendation
from tundralis.profiling import profile_dataframe
from tundralis.utils import load_survey_data

ROOT = Path(__file__).resolve().parents[1]
UPLOAD = ROOT / "app_runtime" / "uploads" / "c12f7621c875_[FINAL+DATA+Full+Launch+COPY+version+Oct+6]+Policy+Measurement+Survey+-+Copy_December+31,+2025_11.51_labels.csv"


@unittest.skipUnless(UPLOAD.exists(), "policy measurement upload fixture not present")
class TestPolicyMeasurementRecommendations(unittest.TestCase):
    def test_profile_treats_labeled_attitudes_as_ordinal_not_admin(self):
        df = load_survey_data(UPLOAD)
        profiles = profile_dataframe(df)

        self.assertEqual(profiles["CSAT"]["semantic_class"], "ordinal_labeled")
        self.assertEqual(profiles["Sentiment"]["semantic_class"], "ordinal_labeled")
        self.assertEqual(profiles["NPS_2"]["semantic_class"], "ordinal_labeled")
        self.assertEqual(profiles["Overall_Lik1_1"]["semantic_class"], "ordinal_labeled")
        self.assertEqual(profiles["ResponseId"]["semantic_class"], "identifier_helper")

    def test_recommendation_finds_real_outcome_and_key_driver_batteries(self):
        df = load_survey_data(UPLOAD)
        profiles = profile_dataframe(df)
        numeric_columns = [
            column for column, profile in profiles.items()
            if profile.get("inferred_type") in {"numeric", "numeric_like_text"}
        ]
        recommendation = _build_recommendation(list(df.columns), profiles, numeric_columns)

        self.assertIn(recommendation["target"], {"CSAT", "Sentiment", "NPS_2"})
        self.assertNotEqual(recommendation["target"], "NPS_1_1")
        predictor_names = {item["name"] for item in recommendation["predictors"]}
        self.assertTrue({"Overall_Lik1_1", "Overall_Lik1_2", "Overall_Lik1_3"} & predictor_names)
        self.assertNotIn("ResponseId", predictor_names)
        self.assertNotIn("Progress", predictor_names)

    def test_recommendation_excludes_incentive_and_bookkeeping_predictors(self):
        df = load_survey_data(UPLOAD)
        profiles = profile_dataframe(df)
        numeric_columns = [
            column for column, profile in profiles.items()
            if profile.get("inferred_type") in {"numeric", "numeric_like_text"}
        ]
        recommendation = _build_recommendation(list(df.columns), profiles, numeric_columns)

        predictor_names = {item["name"] for item in recommendation["predictors"]}
        semantic_hits = {
            name for name, profile in profiles.items()
            if any(token in str(profile.get("semantic_text") or "").lower() for token in ["incentive", "gift", "reward", "payment", "spend", "budget"])
        }
        self.assertTrue(semantic_hits)
        self.assertFalse(predictor_names & semantic_hits)


if __name__ == "__main__":
    unittest.main()
