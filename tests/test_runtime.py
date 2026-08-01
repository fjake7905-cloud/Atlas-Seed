from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents.base_agent import BaseAgent
from runtime.agent_loop import AgentLoop
from runtime.executor import Executor
from runtime.planner import Planner
from runtime.state import AppState


class RuntimeTests(unittest.TestCase):
    def test_agent_loop_creates_file_and_records_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Phase 2: root injection, no chdir needed
            state = AppState.load(root=Path(tmp))
            agent = BaseAgent(state=state, planner=Planner(), executor=Executor(state))
            loop = AgentLoop(agent)

            step = loop.step("create demo.py")

            self.assertIn("Created:", step.output_text)
            self.assertTrue((state.workspace / "demo.py").exists())
            self.assertGreaterEqual(len(state.memory), 2)
            self.assertEqual(state.root.resolve(), Path(tmp).resolve())

    def test_memory_search_finds_recent_activity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = AppState.load(root=Path(tmp))
            agent = BaseAgent(state=state, planner=Planner(), executor=Executor(state))
            loop = AgentLoop(agent)

            loop.step("create demo.py")
            search_step = loop.step("memory search demo.py")

            self.assertIn("Memory search:", search_step.output_text)
            self.assertIn("demo.py", search_step.output_text)

    def test_state_respects_atlas_root_env(self) -> None:
        import os

        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("ATLAS_ROOT")
            try:
                os.environ["ATLAS_ROOT"] = tmp
                state = AppState.load()
                self.assertEqual(state.root.resolve(), Path(tmp).resolve())
                self.assertTrue((Path(tmp) / ".atlas").exists())
                self.assertTrue((Path(tmp) / "workspace").exists())
            finally:
                if old is None:
                    os.environ.pop("ATLAS_ROOT", None)
                else:
                    os.environ["ATLAS_ROOT"] = old


if __name__ == "__main__":
    unittest.main()
