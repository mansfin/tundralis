import json
import subprocess
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output" / "test-artifacts"


class TestFixtureRegression(unittest.TestCase):
    def test_end_to_end_generates_json_and_pptx(self):
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        json_path = OUTPUT_DIR / "sample_analysis_run.json"
        pptx_path = OUTPUT_DIR / "sample_report.pptx"

        cmd = [
            sys.executable,
            str(ROOT / "tundralis_kda.py"),
            "--data", str(ROOT / "data" / "sample_survey.csv"),
            "--target", "overall_satisfaction",
            "--no-ai",
            "--json-output", str(json_path),
            "--output", str(pptx_path),
        ]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue(json_path.exists())
        self.assertTrue(pptx_path.exists())

        payload = json.loads(json_path.read_text())
        self.assertEqual(payload["run_info"]["analysis_type"], "kda")
        self.assertGreater(payload["input_summary"]["rows_modeled"], 0)
        self.assertGreater(len(payload["drivers"]), 0)

        top_driver = sorted(payload["drivers"], key=lambda d: d["importance"]["rank"])[0]["driver_id"]
        predictor_set = set(payload["input_summary"]["predictor_columns"])
        self.assertIn(top_driver, predictor_set)


if __name__ == "__main__":
    unittest.main()
