from __future__ import annotations
import unittest
from pathlib import Path
import tempfile

from core.model_provider import EchoProvider, RuleBasedProvider, get_default_provider, get_provider_by_name
from core.context_builder import build_context, build_prompt_with_context
from runtime.state import AppState
from agents.base_agent import BaseAgent
from runtime.agent_loop import AgentLoop
from runtime.executor import Executor
from runtime.planner import Planner


class ModelProviderTests(unittest.TestCase):
    def test_echo_provider(self) -> None:
        provider = EchoProvider()
        self.assertEqual(provider.name, "echo")
        resp = provider.complete("hello", context={"task": "hello"})
        self.assertIn("EchoProvider", resp.text)

    def test_rule_based_provider_create_file(self) -> None:
        provider = RuleBasedProvider()
        resp = provider.complete("create file test.py", context={"task": "create file test.py"})
        self.assertIn("create", resp.text)
        self.assertIn("test.py", resp.text)

    def test_rule_based_provider_chat(self) -> None:
        provider = RuleBasedProvider()
        resp = provider.complete("what is the weather?", context={"task": "what is the weather?"})
        self.assertIn("RuleBased", resp.text)
        self.assertNotIn('"action": "list"', resp.text)  # Should not return list for weather

    def test_get_default_provider(self) -> None:
        provider = get_default_provider()
        self.assertIsNotNone(provider.name)

    def test_context_builder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "workspace"
            ws.mkdir()
            (ws / "demo.py").write_text("print(1)")
            ctx = build_context(workspace=ws, memory_items=[{"action": "create", "status": "success", "detail": "demo.py"}], task="list files")
            self.assertIn("demo.py", str(ctx["workspace_files"]))
            self.assertEqual(ctx["task"], "list files")

            prompt = build_prompt_with_context("list files", ctx)
            self.assertIn("Task: list files", prompt)

    def test_planner_with_llm(self) -> None:
        provider = RuleBasedProvider()
        planner = Planner(model_provider=provider)

        # Rule-based high confidence
        plan = planner.plan("create demo.py")
        self.assertEqual(plan.action, "create")
        self.assertEqual(plan.confidence, 0.95)

        # Chat that should go via LLM but fallback to chat
        plan = planner.plan("what is the weather?")
        self.assertEqual(plan.action, "chat")

        # Natural language that LLM can map to read
        plan = planner.plan("I need to read notes.txt")
        self.assertEqual(plan.action, "read")

    def test_executor_uses_model_provider_for_chat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = AppState.load(root=Path(tmp), auto_confirm=True)
            # state has default provider rule-based
            self.assertIsNotNone(state.model_provider)
            agent = BaseAgent(state=state, planner=Planner(model_provider=state.model_provider), executor=Executor(state))
            loop = AgentLoop(agent)

            step = loop.step("what is in memory?")
            # Should not be "Atlas needs a model"
            self.assertNotIn("Atlas needs a model", step.output_text)
            self.assertTrue(len(step.output_text) > 10)


if __name__ == "__main__":
    unittest.main()
