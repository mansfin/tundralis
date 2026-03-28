import io
import re
import unittest
from pathlib import Path

from tundralis.app import app

ROOT = Path(__file__).resolve().parents[1]


class TestCodebookUpload(unittest.TestCase):
    def test_codebook_upload_updates_display_name_map(self):
        client = app.test_client()
        csv_bytes = (ROOT / "data" / "fixtures" / "client_style_kda.csv").read_bytes()
        inspect_response = client.post(
            "/inspect",
            data={"survey_file": (io.BytesIO(csv_bytes), "client_style_kda.csv")},
            content_type="multipart/form-data",
        )
        self.assertEqual(inspect_response.status_code, 200)
        html = inspect_response.get_data(as_text=True)
        match = re.search(r"const jobId = \"([a-f0-9]{12})\";", html)
        self.assertIsNotNone(match)
        job_id = match.group(1)

        codebook_bytes = (ROOT / "data" / "fixtures" / "simple_codebook.csv").read_bytes()
        response = client.post(
            f"/mapping/{job_id}/codebook",
            data={"codebook_file": (io.BytesIO(codebook_bytes), "simple_codebook.csv")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["display_name_map"]["overall_sat"], "Overall satisfaction")
        self.assertIn("recommendation", payload)


if __name__ == "__main__":
    unittest.main()
