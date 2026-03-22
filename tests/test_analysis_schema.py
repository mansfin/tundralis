import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


class TestAnalysisSchema(unittest.TestCase):
    def test_generated_payload_matches_schema(self):
        if Draft202012Validator is None:
            self.skipTest("jsonschema not installed in this interpreter")
        schema = json.loads((ROOT / "schemas" / "kda-analysis-run.schema.json").read_text())
        payload_path = ROOT / "output" / "test-artifacts" / "sample_analysis_run.json"
        self.assertTrue(payload_path.exists(), "Run fixture regression test first or generate sample payload.")
        payload = json.loads(payload_path.read_text())
        Draft202012Validator(schema).validate(payload)


if __name__ == "__main__":
    unittest.main()
