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

    def test_recommended_display_label_falls_back_to_humanized_column_name(self):
        profile = {
            "question_text": "56_PCSRecommend",
            "semantic_text": "56_PCSRecommend | {\"ImportId\":\"QID56\"}",
            "inferred_type": "numeric",
        }
        self.assertEqual(_recommended_display_label("56_PCSRecommend", profile), "PCS Recommend")

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

    def test_non_qualtrics_vendor_fixture_surfaces_numeric_fields_with_value_profiles(self):
        bundle = build_prep_bundle(ROOT / "data" / "fixtures" / "ironclad_brand_perceptions_raw.csv")
        profiles = bundle.column_profiles
        numeric_with_top_values = [
            column
            for column, profile in profiles.items()
            if profile.get("inferred_type") == "numeric" and profile.get("top_values")
        ]
        self.assertTrue(numeric_with_top_values)
        self.assertTrue(any("qualtrics" not in column.lower() for column in numeric_with_top_values))
        semantic_classes = {profiles[column].get("semantic_class") for column in numeric_with_top_values}
        self.assertTrue(any(value in semantic_classes for value in {"ordinal_numeric", "continuous_numeric", "identifier_helper", "ambiguous_numeric", "nominal_coded_numeric"}))

    def test_non_qualtrics_vendor_fixture_contains_multi_category_company_size_signal(self):
        bundle = build_prep_bundle(ROOT / "data" / "fixtures" / "ironclad_brand_perceptions_raw.csv")
        profiles = bundle.column_profiles
        company_size = profiles["company_size"]
        top_values = [str(row.get("value", "")) for row in company_size.get("top_values", [])]
        self.assertIn("Commercial_Business", top_values)
        self.assertIn("SMB_Midmarket", top_values)
        self.assertGreaterEqual(len(top_values), 2)
        self.assertIn(company_size.get("semantic_class"), {"labeled_categorical", "nominal_coded_numeric", "identifier_helper"})

    def test_qualtrics_raw_export_stays_low_confidence_without_overclaiming_labels(self):
        bundle = build_prep_bundle(ROOT / "data" / "fixtures" / "qualtrics_raw_export.csv")
        df = bundle.working_df
        recommendation = _build_recommendation(
            list(df.columns),
            bundle.column_profiles,
            df.select_dtypes(include="number").columns.tolist(),
        )
        self.assertEqual(recommendation.get("schema_clarity"), "codes_only")
        self.assertFalse(recommendation.get("target"))
        self.assertLessEqual(len(recommendation.get("recommended_labels", {})), 3)


if __name__ == "__main__":
    unittest.main()
