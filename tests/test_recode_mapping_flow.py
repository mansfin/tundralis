import json
import subprocess
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output" / "test-artifacts"


class TestRecodeMappingFlow(unittest.TestCase):
    def test_mapping_config_with_recodes_runs_end_to_end(self):
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        json_path = OUTPUT_DIR / "recode_analysis_run.json"
        pptx_path = OUTPUT_DIR / "recode_report.pptx"
        mapping_path = OUTPUT_DIR / "recode_mapping.json"

        mapping = {
            "target_column": "overall_sat",
            "segment_columns": ["segment_group"],
            "predictor_columns": [
                "product_quality_score",
                "ease_use_score",
                "support_experience",
                "value_for_money",
                "onboarding_score",
                "service_reliability",
                "mobile_app_score",
                "acct_mgmt_score",
                "reporting_tools",
                "integration_setup",
            ],
            "recode_definitions": [
                {
                    "type": "map_values",
                    "source_column": "segment",
                    "output_column": "segment_group",
                    "mapping": {
                        "SMB": "Commercial",
                        "Mid-Market": "Commercial",
                        "Enterprise": "Enterprise"
                    }
                },
                {
                    "type": "boolean_flag",
                    "source_column": "region",
                    "output_column": "is_apac",
                    "operator": "equals",
                    "value": "APAC",
                    "true_value": 1,
                    "false_value": 0
                }
            ]
        }
        mapping_path.write_text(json.dumps(mapping), encoding="utf-8")

        cmd = [
            str(ROOT / ".venv" / "bin" / "python"),
            str(ROOT / "tundralis_kda.py"),
            "--data", str(ROOT / "data" / "fixtures" / "client_style_kda.csv"),
            "--mapping-config", str(mapping_path),
            "--no-ai",
            "--json-output", str(json_path),
            "--output", str(pptx_path),
        ]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        payload = json.loads(json_path.read_text())
        self.assertEqual(payload["input_summary"]["segment_columns"], ["segment_group"])
        self.assertEqual(len(payload["input_summary"]["recode_definitions"]), 2)
        self.assertTrue(json_path.exists())
        self.assertTrue(pptx_path.exists())


if __name__ == "__main__":
    unittest.main()
