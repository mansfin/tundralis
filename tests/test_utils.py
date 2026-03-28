from pathlib import Path
import unittest

from tundralis.utils import load_survey_data

ROOT = Path(__file__).resolve().parents[1]


class TestLoadSurveyData(unittest.TestCase):
    def test_loads_standard_csv_without_skipping_rows(self):
        df = load_survey_data(ROOT / "data" / "fixtures" / "client_style_kda.csv")
        self.assertIn("overall_sat", df.columns)
        self.assertGreater(len(df), 0)

    def test_detects_and_skips_qualtrics_metadata_rows(self):
        df = load_survey_data(ROOT / "data" / "fixtures" / "qualtrics_raw_export.csv")
        self.assertEqual(df.columns.tolist(), ["QID1", "QID2", "ResponseId"])
        self.assertEqual(len(df), 3)
        self.assertEqual(df.iloc[0].to_dict(), {"QID1": 5, "QID2": 4, "ResponseId": "R_001"})


if __name__ == "__main__":
    unittest.main()
