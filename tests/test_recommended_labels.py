import unittest
from tundralis.app import _recommended_display_label, _build_recommendation
from tundralis.prep import build_prep_bundle
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestRecommendedLabels(unittest.TestCase):
    def test_recommended_display_label_prefers_question_text_when_available(self):
        profile = {
            "question_text": "Overall satisfaction with the product",
            "semantic_text": "Q1 | Overall satisfaction with the product | {\"ImportId\":\"QID1\"}",
            "inferred_type": "numeric",
        }
        self.assertEqual(_recommended_display_label("Q1", profile), "Overall satisfaction with the product")

    def test_recommendation_surfaces_recommended_labels_for_raw_export(self):
        bundle = build_prep_bundle(ROOT / "data" / "fixtures" / "ironclad_brand_perceptions_raw.csv")
        df = bundle.working_df
        recommendation = _build_recommendation(
            list(df.columns),
            bundle.column_profiles,
            df.select_dtypes(include="number").columns.tolist(),
        )
        recommended_labels = recommendation.get("recommended_labels", {})
        self.assertTrue(recommended_labels)
        self.assertTrue(any(len(label) > 8 for label in recommended_labels.values()))

    def test_recommendation_surfaces_semantic_buckets_for_ambiguous_raw_export(self):
        bundle = build_prep_bundle(ROOT / "data" / "fixtures" / "ironclad_brand_perceptions_raw.csv")
        df = bundle.working_df
        recommendation = _build_recommendation(
            list(df.columns),
            bundle.column_profiles,
            df.select_dtypes(include="number").columns.tolist(),
        )
        self.assertIn("candidate_segments", recommendation)
        self.assertIn("helper_fields", recommendation)
        self.assertIn("ambiguous_fields", recommendation)
        self.assertIn("ambiguity_summary", recommendation)
        surfaced_count = sum(bool(recommendation[key]) for key in ["candidate_segments", "helper_fields", "ambiguous_fields", "meta_candidates"])
        self.assertGreaterEqual(surfaced_count, 1)
        self.assertTrue(recommendation["helper_fields"] or recommendation["meta_candidates"])


if __name__ == "__main__":
    unittest.main()
