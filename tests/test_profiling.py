import unittest
from pathlib import Path

from tundralis.profiling import profile_dataframe
from tundralis.utils import load_survey_data

ROOT = Path(__file__).resolve().parents[1]


class TestProfiling(unittest.TestCase):
    def test_profile_dataframe_fixture_outputs_expected_signals(self):
        df = load_survey_data(ROOT / "data" / "fixtures" / "client_style_kda.csv")
        profiles = profile_dataframe(df)

        overall = profiles["overall_sat"]
        self.assertEqual(overall["inferred_type"], "numeric")
        self.assertIn("likely_likert_or_coded_categorical", overall["warnings"])
        self.assertGreater(overall["missing_pct"], 0)
        self.assertEqual(overall["numeric_summary"]["min"], 1.0)
        self.assertEqual(overall["numeric_summary"]["max"], 7.0)

        response_id = profiles["response_id"]
        self.assertIn("likely_identifier", response_id["warnings"])
        self.assertIn("high_cardinality", response_id["warnings"])

        segment = profiles["segment"]
        self.assertEqual(segment["inferred_type"], "categorical")
        self.assertGreaterEqual(segment["distinct_count"], 3)
        self.assertTrue(any(row["value"] == "SMB" for row in segment["top_values"]))

        comments = profiles["free_text_comment"]
        self.assertIn(comments["inferred_type"], {"text", "categorical"})
        self.assertGreater(comments["missing_pct"], 0)


if __name__ == "__main__":
    unittest.main()
