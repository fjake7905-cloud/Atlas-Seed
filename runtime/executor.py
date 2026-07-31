from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Optional

from core.capabilities import CapabilityResult, resolve_path
from runtime.planner import Plan
from runtime.state import AppState
from runtime.router import Router


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    message: str
    detail: str = ""


class Executor:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.router = Router()

    def execute(self, plan: Plan) -> ExecutionResult:
        route = self.router.route(plan)
        if route.target == "chat":
            self.state.record(plan.action, "needs-model", plan.args[0] if plan.args else "")
            return ExecutionResult(False, "Atlas needs a model for that request.")

        try:
            if plan.action == "workspace_create":
                return self._workspace_create(plan.args)
            if plan.action == "workspace_show":
                return ExecutionResult(True, "Current workspace:", str(self.state.workspace.resolve()))
            if plan.action == "create":
                return self._create_file(plan.args)
            if plan.action == "read":
                return self._read_file(plan.args)
            if plan.action == "write":
                return self._write_file(plan.args)
            if plan.action == "list":
                return self._list_files(plan.args)
            if plan.action == "run":
                return self._run_python(plan.args)
            if plan.action == "memory":
                return self._show_memory()
            if plan.action == "noop":
                return ExecutionResult(True, "No command provided.")
            return ExecutionResult(False, f"Unknown command: {plan.action}")
        except Exception as exc:
            self.state.record(plan.action, "error", str(exc))
            return ExecutionResult(False, f"Error: {exc}")

    def _workspace_create(self, args: list[str]) -> ExecutionResult:
        if not args:
            return ExecutionResult(False, "Usage: workspace create <name>")
        path = resolve_path(self.state.workspace, args[0])
        path.mkdir(parents=True, exist_ok=True)
        self.state.record("workspace_create", "success", str(path))
        return ExecutionResult(True, f"Workspace created: {path}")

    def _create_file(self, args: list[str]) -> ExecutionResult:
        if not args:
            return ExecutionResult(False, "Usage: create <file>")
        path = resolve_path(self.state.workspace, args[0])
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("", encoding="utf-8")
        self.state.record("create", "success", str(path))
        return ExecutionResult(True, f"Created: {path.relative_to(self.state.workspace.resolve())}")

    def _read_file(self, args: list[str]) -> ExecutionResult:
        if not args:
            return ExecutionResult(False, "Usage: read <file>")
        path = resolve_path(self.state.workspace, args[0])
        content = path.read_text(encoding="utf-8")
        self.state.record("read", "success", str(path))
        return ExecutionResult(True, f"Read: {path.relative_to(self.state.workspace.resolve())}", content)

    def _write_file(self, args: list[str]) -> ExecutionResult:
        if len(args) < 2:
            return ExecutionResult(False, 'Usage: write <file> <text>')
        path = resolve_path(self.state.workspace, args[0])
        text = " ".join(args[1:])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.state.record("write", "success", str(path))
        return ExecutionResult(True, f"Written: {path.relative_to(self.state.workspace.resolve())}")

    def _list_files(self, args: list[str]) -> ExecutionResult:
        path = self.state.workspace if not args else resolve_path(self.state.workspace, args[0])
        entries = []
        for item in sorted(path.iterdir()):
            suffix = "/" if item.is_dir() else ""
            entries.append(f"{item.name}{suffix}")
        self.state.record("list", "success", str(path))
        return ExecutionResult(True, f"Listing: {path.relative_to(self.state.workspace.resolve()) if path != self.state.workspace else '.'}", "\n".join(entries))

    def _run_python(self, args: list[str]) -> ExecutionResult:
        if not args:
            return ExecutionResult(False, "Usage: run <python file>")
        path = resolve_path(self.state.workspace, args[0])
        completed = subprocess.run(["python", str(path)], capture_output=True, text=True, cwd=self.state.workspace)
        self.state.record("run", "success" if completed.returncode == 0 else "failed", str(path))
        detail = (completed.stdout or "") + (completed.stderr or "")
        return ExecutionResult(completed.returncode == 0, f"Ran: {path.relative_to(self.state.workspace.resolve())}", detail.strip())

    def _show_memory(self) -> ExecutionResult:
        lines = [f"{entry['action']}: {entry['status']} - {entry.get('detail', '')}" for entry in self.state.memory[-20:]]
        return ExecutionResult(True, "Recent memory:", "\n".join(lines) if lines else "No memory yet.")
