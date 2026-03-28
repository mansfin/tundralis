import io
import unittest
from pathlib import Path

from tundralis.app import app

ROOT = Path(__file__).resolve().parents[1]


class TestSchemaBanner(unittest.TestCase):
    def test_mapping_page_contains_schema_banner_ui(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()
        response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("schemaConfidenceBanner", html)
        self.assertIn("schemaConfidenceTitle", html)
        self.assertIn("schemaConfidenceCopy", html)


if __name__ == "__main__":
    unittest.main()
