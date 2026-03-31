from pathlib import Path
import unittest


class TestWebSmokeContract(unittest.TestCase):
    def read(self, path: str) -> str:
        return Path(path).read_text()

    def test_mapping_template_has_phase1_phase2_ui_hooks(self):
        text = self.read('web/templates/mapping.html')
        self.assertIn('recommendationConfidenceStrip', text)
        self.assertIn('predictorShortlist', text)
        self.assertIn('toggleAllPredictors', text)
        self.assertIn('toggleAdvancedSegmentBuilder', text)
        self.assertIn('toggleConfirmDetails', text)

    def test_result_template_has_insight_page_sections(self):
        text = self.read('web/templates/result.html')
        self.assertIn('Analysis complete', text)
        self.assertIn('Decision summary', text)
        self.assertIn('Top actions to prioritize', text)
        self.assertIn('Run confidence', text)
        self.assertIn('Deliverables', text)
        self.assertIn('Download report', text)
        self.assertIn('Download JSON', text)


if __name__ == '__main__':
    unittest.main()
