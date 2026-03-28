import json
import unittest
from pathlib import Path

from tundralis.app import _build_recommendation
from tundralis.prep import build_prep_bundle

ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = ROOT / "data" / "fixtures" / "recommendation_eval_cases.json"


class TestRecommendationRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads(CASE_PATH.read_text(encoding="utf-8"))

    def _evaluate_case(self, case: dict) -> dict:
        bundle = build_prep_bundle(ROOT / case["csv"])
        df = bundle.working_df
        recommendation = _build_recommendation(
            list(df.columns),
            bundle.column_profiles,
            df.select_dtypes(include="number").columns.tolist(),
        )
        shortlist = [item["name"] for item in recommendation["predictors"]]
        excluded = {item["name"]: item for item in recommendation["excluded"]}
        included = set(shortlist)

        must_include_hits = [name for name in case.get("must_include", []) if name in included]
        must_exclude_hits = [name for name in case.get("must_exclude", []) if name in excluded]

        return {
            "target": recommendation["target"],
            "shortlist": shortlist,
            "excluded": excluded,
            "recommendation": recommendation,
            "include_recall": len(must_include_hits) / max(len(case.get("must_include", [])), 1),
            "exclude_recall": len(must_exclude_hits) / max(len(case.get("must_exclude", [])), 1),
            "must_include_hits": must_include_hits,
            "must_exclude_hits": must_exclude_hits,
        }

    def test_cases_meet_minimum_quality_bar(self):
        summaries = []
        for case in self.cases:
            result = self._evaluate_case(case)
            summaries.append((case["name"], result))
            self.assertEqual(
                result["target"],
                case["expected_target"],
                msg=f"{case['name']}: expected target {case['expected_target']}, got {result['target']}",
            )
            self.assertGreaterEqual(
                result["include_recall"],
                0.75,
                msg=f"{case['name']}: weak must-include recall {result['must_include_hits']} / {case.get('must_include', [])}",
            )
            self.assertGreaterEqual(
                result["exclude_recall"],
                0.85,
                msg=f"{case['name']}: weak must-exclude recall {result['must_exclude_hits']} / {case.get('must_exclude', [])}",
            )

        avg_include = sum(result["include_recall"] for _, result in summaries) / len(summaries)
        avg_exclude = sum(result["exclude_recall"] for _, result in summaries) / len(summaries)
        self.assertGreaterEqual(avg_include, 0.85, msg=f"average include recall too low: {avg_include:.2f}")
        self.assertGreaterEqual(avg_exclude, 0.90, msg=f"average exclude recall too low: {avg_exclude:.2f}")

    def test_fixture_report_is_human_readable_on_failure(self):
        report_rows = []
        for case in self.cases:
            result = self._evaluate_case(case)
            report_rows.append(
                {
                    "name": case["name"],
                    "target": result["target"],
                    "confidence": result["recommendation"]["confidence"],
                    "include_recall": round(result["include_recall"], 2),
                    "exclude_recall": round(result["exclude_recall"], 2),
                    "shortlist_preview": result["shortlist"][:8],
                }
            )
        self.assertEqual(len(report_rows), len(self.cases))


if __name__ == "__main__":
    unittest.main()
