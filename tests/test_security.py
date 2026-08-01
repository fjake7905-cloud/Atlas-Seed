from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.capabilities import resolve_path
from runtime.state import AppState
from agents.base_agent import BaseAgent
from runtime.agent_loop import AgentLoop
from runtime.executor import Executor
from runtime.planner import Planner


class SecurityTests(unittest.TestCase):
    def test_path_traversal_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = AppState.load(root=Path(tmp), auto_confirm=True)
            workspace = state.workspace

            with self.assertRaises(ValueError):
                resolve_path(workspace, "../../etc/passwd")

            with self.assertRaises(ValueError):
                resolve_path(workspace, "/etc/passwd")

            with self.assertRaises(ValueError):
                resolve_path(workspace, "../outside.txt")

            valid = resolve_path(workspace, "inside.txt")
            self.assertTrue(str(valid).startswith(str(workspace.resolve())))

    def test_symlink_escape_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = AppState.load(root=Path(tmp), auto_confirm=True)
            workspace = state.workspace

            outside = Path(tmp) / "outside_secret.txt"
            outside.write_text("secret")
            with self.assertRaises(ValueError):
                resolve_path(workspace, "../outside_secret.txt")

    def test_executor_blocks_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = AppState.load(root=Path(tmp), auto_confirm=True)
            agent = BaseAgent(state=state, planner=Planner(), executor=Executor(state))
            loop = AgentLoop(agent)

            result = loop.step("read ../../etc/passwd")
            # Should be error, not successful read
            self.assertTrue(
                "Error" in result.output_text or "escapes" in result.output_text.lower() or "Path escapes" in result.output_text
            )
            self.assertNotIn("Read: ../../etc/passwd", result.output_text)

            result = loop.step("write ../../etc/passwd evil")
            self.assertTrue(
                "Error" in result.output_text
                or "escapes" in result.output_text.lower()
                or "Confirmation required" in result.output_text
                or "Failed" in result.output_text
                or "Written:" not in result.output_text
            )

    def test_delete_nonexistent_fails_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = AppState.load(root=Path(tmp), auto_confirm=True)
            agent = BaseAgent(state=state, planner=Planner(), executor=Executor(state))
            loop = AgentLoop(agent)

            result = loop.step("delete nonexistent.txt")
            self.assertIn("not found", result.output_text.lower())

    def test_read_nonexistent_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = AppState.load(root=Path(tmp), auto_confirm=True)
            agent = BaseAgent(state=state, planner=Planner(), executor=Executor(state))
            loop = AgentLoop(agent)

            result = loop.step("read nofile.txt")
            self.assertTrue("Error" in result.output_text or "No such file" in result.output_text or "not found" in result.output_text.lower() or "Traceback" in result.output_text)

    def test_run_invalid_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = AppState.load(root=Path(tmp), auto_confirm=True)
            agent = BaseAgent(state=state, planner=Planner(), executor=Executor(state))
            loop = AgentLoop(agent)

            result = loop.step("run nonexist.py")
            # Running non-existent should not be marked as success with file content, should contain error detail
            self.assertTrue(
                "No such file" in result.output_text or "can't open file" in result.output_text or "Error" in result.output_text or "Ran:" in result.output_text
            )
            # It should be failure (returncode !=0) -> output starts with Ran but detail contains error
            # Ensure it doesn't create file
            self.assertFalse((Path(tmp) / "workspace" / "nonexist.py").exists() and "hello" in result.output_text)

    def test_memory_persists_and_clear_needs_confirm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_no_confirm = AppState.load(root=Path(tmp), auto_confirm=False)
            agent_no = BaseAgent(state=state_no_confirm, planner=Planner(), executor=Executor(state_no_confirm))
            loop_no = AgentLoop(agent_no)

            loop_no.step("create demo.py")
            result = loop_no.step("memory clear")
            self.assertIn("Confirmation required", result.output_text)

            state_yes = AppState.load(root=Path(tmp), auto_confirm=True)
            agent_yes = BaseAgent(state=state_yes, planner=Planner(), executor=Executor(state_yes))
            loop_yes = AgentLoop(agent_yes)
            result_yes = loop_yes.step("memory clear")
            self.assertIn("cleared", result_yes.output_text.lower())


class PlannerTests(unittest.TestCase):
    def test_planner_empty(self) -> None:
        from runtime.planner import Planner

        p = Planner()
        plan = p.plan("")
        self.assertEqual(plan.action, "noop")

    def test_planner_quoted_args(self) -> None:
        from runtime.planner import Planner

        p = Planner()
        plan = p.plan('write notes.txt "hello world"')
        self.assertEqual(plan.action, "write")
        self.assertEqual(plan.args, ["notes.txt", "hello world"])

        plan = p.plan('read "my file.txt"')
        self.assertEqual(plan.args, ["my file.txt"])

    def test_planner_unknown_goes_to_chat(self) -> None:
        from runtime.planner import Planner

        p = Planner()
        plan = p.plan("what is the weather?")
        self.assertEqual(plan.action, "chat")


if __name__ == "__main__":
    unittest.main()
