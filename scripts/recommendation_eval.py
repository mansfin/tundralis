from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tundralis.app import _build_recommendation
from tundralis.prep import build_prep_bundle
CASE_PATH = ROOT / "data" / "fixtures" / "recommendation_eval_cases.json"


def evaluate_case(case: dict) -> dict:
    bundle = build_prep_bundle(ROOT / case["csv"])
    df = bundle.working_df
    recommendation = _build_recommendation(
        list(df.columns),
        bundle.column_profiles,
        df.select_dtypes(include="number").columns.tolist(),
    )
    shortlist = [item["name"] for item in recommendation["predictors"]]
    excluded = {item["name"]: item for item in recommendation["excluded"]}
    must_include = case.get("must_include", [])
    must_exclude = case.get("must_exclude", [])

    include_hits = [name for name in must_include if name in shortlist]
    include_misses = [name for name in must_include if name not in shortlist]
    exclude_hits = [name for name in must_exclude if name in excluded]
    exclude_misses = [name for name in must_exclude if name not in excluded]

    return {
        "name": case["name"],
        "target": recommendation["target"],
        "expected_target": case["expected_target"],
        "confidence": recommendation["confidence"],
        "schema_clarity": recommendation["schema_clarity"],
        "include_recall": len(include_hits) / max(len(must_include), 1),
        "exclude_recall": len(exclude_hits) / max(len(must_exclude), 1),
        "include_hits": include_hits,
        "include_misses": include_misses,
        "exclude_hits": exclude_hits,
        "exclude_misses": exclude_misses,
        "shortlist": shortlist,
        "excluded_reasons": {name: excluded[name]["reasons"] for name in exclude_hits},
    }


def main() -> int:
    cases = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    results = [evaluate_case(case) for case in cases]

    avg_include = sum(r["include_recall"] for r in results) / len(results)
    avg_exclude = sum(r["exclude_recall"] for r in results) / len(results)

    print("Recommendation evaluation")
    print("=" * 80)
    for result in results:
        print(f"\n[{result['name']}]")
        print(f"target: {result['target']} (expected {result['expected_target']})")
        print(f"confidence: {result['confidence']} | schema: {result['schema_clarity']}")
        print(f"include recall: {result['include_recall']:.2f} | exclude recall: {result['exclude_recall']:.2f}")
        print("shortlist:", ", ".join(result["shortlist"][:12]))
        if result["include_misses"]:
            print("missing expected drivers:", ", ".join(result["include_misses"]))
        if result["exclude_misses"]:
            print("bad survivors:", ", ".join(result["exclude_misses"]))

    print("\n" + "=" * 80)
    print(f"Average include recall: {avg_include:.2f}")
    print(f"Average exclude recall: {avg_exclude:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
