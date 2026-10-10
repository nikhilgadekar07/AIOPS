import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "ai-agents")

from agents.ambiguity_agent import detect_ambiguities
from agents.implementation_agent import apply_implementation_plan, generate_implementation_plan
from agents.spec_agent import generate_spec


class ImplementationAgentTests(unittest.TestCase):
    def test_generate_implementation_plan_returns_actionable_plan(self):
        spec = {
            "functional_requirements": [
                "Users can update the status of an existing order.",
                "Only valid statuses are accepted.",
            ],
            "affected_components": [
                "orders API",
                "order state model",
            ],
            "api_changes": [
                "Add PATCH /orders/{order_id} endpoint.",
            ],
        }

        plan = generate_implementation_plan(
            "Update order status",
            "Allow users to change the status of an existing order.",
            spec,
            codebase_chunks=[
                {
                    "file_path": "existing_code/app/orders.py",
                    "content": "Order status values are stored in a dictionary for created orders.",
                    "start_line": 1,
                    "end_line": 50,
                }
            ],
            use_llm=False,
        )

        self.assertEqual(plan["status"], "ready")
        self.assertIn("files", plan)
        self.assertTrue(plan["files"])
        self.assertTrue(plan["changes"][0]["file"].endswith(".py"))

    def test_apply_implementation_plan_updates_target_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan = {
                "changes": [
                    {"file": "generated_feature.py", "action": "create"},
                ]
            }

            applied = apply_implementation_plan(plan, str(root))
            self.assertTrue(applied)

            generated_file = root / "generated_feature.py"
            self.assertTrue(generated_file.exists())
            content = generated_file.read_text(encoding="utf-8")
            self.assertIn("handle_request", content)
            self.assertIn("status", content)

    def test_generate_implementation_plan_avoids_hardcoded_sample_app(self):
        spec = {
            "functional_requirements": [
                "Users can submit a request and receive a success response.",
            ],
            "affected_components": [
                "user request handler",
                "validation logic",
            ],
            "confidence": 0.8,
        }

        plan = generate_implementation_plan(
            "Build a request form",
            "I want a form where a user can enter a request and see a success message after submission.",
            spec,
            codebase_chunks=[],
            use_llm=False,
        )

        self.assertEqual(plan["status"], "ready")
        self.assertTrue(plan["changes"])
        for file_name in plan["files"]:
            self.assertNotIn("sample-app", file_name)
            self.assertNotIn("orders.py", file_name)

    def test_apply_implementation_plan_uses_feature_specific_template(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan = {
                "changes": [
                    {"file": "generated_customer_support_dashboard.py", "action": "create"},
                ]
            }

            applied = apply_implementation_plan(plan, str(root))
            self.assertTrue(applied)

            generated_file = root / "generated_customer_support_dashboard.py"
            content = generated_file.read_text(encoding="utf-8")
            for keyword in ["ticket", "status", "sidebar", "dashboard"]:
                self.assertIn(keyword.lower(), content.lower())
            self.assertNotIn("The request has been captured and is ready for a real implementation pass.", content)
            self.assertNotIn("Simple placeholder implementation", content)

    def test_run_request_supports_project_mode_and_human_review(self):
        from ui_server import RunRequest

        request = RunRequest(
            prompt="Build a customer portal for billing flows.",
            project_mode="existing",
            repo_url="https://github.com/example/project.git",
            require_human_review=True,
        )

        self.assertEqual(request.project_mode, "existing")
        self.assertEqual(request.repo_url, "https://github.com/example/project.git")
        self.assertTrue(request.require_human_review)

    def test_detect_ambiguities_falls_back_when_llm_is_unavailable(self):
        import agents.ambiguity_agent as ambiguity_agent

        original = ambiguity_agent.generate_json
        ambiguity_agent.generate_json = lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("Ollama unavailable"))

        try:
            questions = detect_ambiguities(
                "Update order status",
                "Allow a user to update the status of an existing order using valid values only.",
            )
            self.assertTrue(questions)
            self.assertIn("question", questions[0])
            self.assertIn("assumed_default", questions[0])
        finally:
            ambiguity_agent.generate_json = original

    def test_generate_spec_falls_back_when_llm_is_unavailable(self):
        import agents.spec_agent as spec_agent

        original = spec_agent.generate_json
        spec_agent.generate_json = lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("Ollama unavailable"))

        try:
            spec = generate_spec(
                "Update order status",
                "Allow a user to update the status of an existing order using valid values only.",
                [{"question": "What statuses are allowed?", "answer": "pending, shipped, delivered, cancelled"}],
            )
            self.assertIn("functional_requirements", spec)
            self.assertIn("confidence", spec)
            self.assertIn("review_status", spec)
            self.assertTrue(spec["functional_requirements"])
        finally:
            spec_agent.generate_json = original

    def test_generate_spec_falls_back_when_llm_returns_empty_json(self):
        import agents.spec_agent as spec_agent

        original = spec_agent.generate_json
        spec_agent.generate_json = lambda *args, **kwargs: {}

        try:
            spec = generate_spec(
                "Update order status",
                "Allow a user to update the status of an existing order using valid values only.",
                [{"question": "What statuses are allowed?", "answer": "pending, shipped, delivered, cancelled"}],
            )
            self.assertTrue(spec["functional_requirements"])
            self.assertGreaterEqual(spec["confidence"], 0.0)
        finally:
            spec_agent.generate_json = original


if __name__ == "__main__":
    unittest.main()
