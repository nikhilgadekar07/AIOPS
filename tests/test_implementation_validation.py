import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, 'ai-agents')

from agents.implementation_agent import validate_implementation
from run_full_pipeline import log_stage, write_live_status


class ImplementationValidationTests(unittest.TestCase):
    def test_validate_implementation_runs_for_generated_prompt_feature(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            generated_file = root / 'generated_feature.py'
            generated_file.write_text(
                '''def handle_request(request_text: str) -> dict:
    normalized = (request_text or "").strip()
    if not normalized:
        raise ValueError("Request text cannot be empty.")
    return {"status": "accepted", "summary": normalized}
''',
                encoding='utf-8',
            )

            result = validate_implementation(str(root))
            self.assertEqual(result['status'], 'passed')
            self.assertEqual(result['checks'][0]['name'], 'generated_feature_handler')

    def test_live_status_writes_progress_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_path = Path(temp_dir) / 'live_status.json'
            write_live_status(
                output_path=status_path,
                status='working',
                stage='Understanding Request',
                message='I am reading your request and narrowing the goal.',
                progress=15,
            )

            result = json.loads(status_path.read_text(encoding='utf-8'))
            self.assertEqual(result['status'], 'working')
            self.assertEqual(result['stage'], 'Understanding Request')
            self.assertEqual(result['progress'], 15)

    def test_log_stage_updates_live_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_path = Path(temp_dir) / 'live_status.json'
            stage_log = []

            log_stage(
                'Spec Generation',
                'Turning the prompt into a clear specification and acceptance criteria.',
                stage_log,
                output_path=status_path,
            )

            self.assertEqual(stage_log[-1]['stage'], 'Spec Generation')
            result = json.loads(status_path.read_text(encoding='utf-8'))
            self.assertEqual(result['stage'], 'Spec Generation')
            self.assertTrue(result['stages'])


if __name__ == '__main__':
    unittest.main()
