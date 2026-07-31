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


class AgentCoreTests(unittest.TestCase):
    def test_agent_loop_uses_tool_registry_and_persists_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path.cwd()
            try:
                os.chdir(tmp)
                state = AppState.load()
                executor = Executor(state)
                agent = BaseAgent(state=state, planner=Planner(), executor=executor)
                loop = AgentLoop(agent)

                step = loop.step("create demo.py")

                self.assertIn("Created:", step.output_text)
                self.assertIn("create", executor.tools.list())
                self.assertTrue((state.workspace / "demo.py").exists())
                self.assertTrue((Path(tmp) / ".atlas" / "memory.json").exists())

                reloaded = AppState.load()
                self.assertGreaterEqual(len(reloaded.memory), 2)
                self.assertTrue(any(item.get("action") == "create" for item in reloaded.memory))
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
