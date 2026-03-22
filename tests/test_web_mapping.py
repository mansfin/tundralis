import io
import unittest
from pathlib import Path

from tundralis.app import app

ROOT = Path(__file__).resolve().parents[1]


class TestWebMapping(unittest.TestCase):
    def test_inspect_renders_column_inspector(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()

        response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Column inspector", html)
        self.assertIn("Recode studio", html)
        self.assertIn("overall_sat", html)
        self.assertIn("high_cardinality", html)


if __name__ == "__main__":
    unittest.main()
