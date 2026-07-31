from __future__ import annotations

import os
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
            cwd = Path.cwd()
            try:
                os.chdir(tmp)
                state = AppState.load()
                agent = BaseAgent(state=state, planner=Planner(), executor=Executor(state))
                loop = AgentLoop(agent)

                step = loop.step("create demo.py")

                self.assertIn("Created:", step.output_text)
                self.assertTrue((state.workspace / "demo.py").exists())
                self.assertGreaterEqual(len(state.memory), 2)
            finally:
                os.chdir(cwd)

    def test_memory_search_finds_recent_activity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path.cwd()
            try:
                os.chdir(tmp)
                state = AppState.load()
                agent = BaseAgent(state=state, planner=Planner(), executor=Executor(state))
                loop = AgentLoop(agent)

                loop.step("create demo.py")
                search_step = loop.step("memory search demo.py")

                self.assertIn("Memory search:", search_step.output_text)
                self.assertIn("demo.py", search_step.output_text)
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
