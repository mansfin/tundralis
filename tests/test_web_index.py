import unittest

from tundralis.app import app


class TestWebIndex(unittest.TestCase):
    def test_index_renders_upload_progress_bar(self):
        client = app.test_client()
        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("uploadProgressWrap", html)
        self.assertIn("uploadProgressFill", html)
        self.assertIn("uploadProgressLabel", html)
        self.assertIn("Inspect columns", html)


if __name__ == "__main__":
    unittest.main()
