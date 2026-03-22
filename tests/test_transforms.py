import unittest

import pandas as pd

from tundralis.transforms import apply_recode_transforms


class TestTransforms(unittest.TestCase):
    def test_apply_map_values_bucket_and_flag(self):
        df = pd.DataFrame(
            {
                "segment": ["SMB", "Enterprise", "Mid-Market", None],
                "overall_sat": [3, 6, 5, 2],
                "region": ["APAC", "North America", "EMEA", "APAC"],
            }
        )

        recodes = [
            {
                "type": "map_values",
                "source_column": "segment",
                "output_column": "segment_group",
                "mapping": {"SMB": "Commercial", "Mid-Market": "Commercial", "Enterprise": "Enterprise"},
            },
            {
                "type": "bucket_numeric",
                "source_column": "overall_sat",
                "output_column": "overall_sat_bucket",
                "bins": [
                    {"min": None, "max": 3, "label": "Low", "include_min": True, "include_max": True},
                    {"min": 4, "max": 5, "label": "Mid", "include_min": True, "include_max": True},
                    {"min": 6, "max": None, "label": "High", "include_min": True, "include_max": True},
                ],
            },
            {
                "type": "boolean_flag",
                "source_column": "region",
                "output_column": "is_apac",
                "operator": "equals",
                "value": "APAC",
                "true_value": "yes",
                "false_value": "no",
            },
        ]

        transformed = apply_recode_transforms(df, recodes)
        self.assertEqual(transformed["segment_group"].tolist()[:3], ["Commercial", "Enterprise", "Commercial"])
        self.assertEqual(transformed["overall_sat_bucket"].tolist(), ["Low", "High", "Mid", "Low"])
        self.assertEqual(transformed["is_apac"].tolist(), ["yes", "no", "no", "yes"])

    def test_rejects_duplicate_output_column(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        with self.assertRaises(ValueError):
            apply_recode_transforms(
                df,
                [{"type": "boolean_flag", "source_column": "x", "output_column": "x", "operator": "gt", "value": 1}],
            )


if __name__ == "__main__":
    unittest.main()
