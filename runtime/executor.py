from __future__ import annotations

from dataclasses import dataclass
import subprocess
import sys

from core.capabilities import CapabilityRegistry, resolve_path
from core.tools import Tool, ToolRegistry
from runtime.events import Event
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
        self.tools = ToolRegistry()
        self.capabilities = CapabilityRegistry()
        self._register_tools()

    def _register_tools(self) -> None:
        self.tools.register(Tool("workspace_create", "Create a workspace folder.", self._workspace_create))
        self.tools.register(Tool("workspace_show", "Show the active workspace.", self._workspace_show))
        self.tools.register(Tool("create", "Create a file.", self._create_file))
        self.tools.register(Tool("read", "Read a file.", self._read_file))
        self.tools.register(Tool("write", "Write to a file.", self._write_file))
        self.tools.register(Tool("list", "List workspace files.", self._list_files))
        self.tools.register(Tool("run", "Run a Python file.", self._run_python))
        self.tools.register(Tool("memory", "Show recent memory or search it.", self._show_memory))

    def _check_capability_confirmation(self, action: str) -> ExecutionResult | None:
        """Check if action needs confirmation and if auto_confirm is set"""
        if self.capabilities.needs_confirmation(action):
            if not self.state.auto_confirm:
                # Emit event for confirmation requirement
                try:
                    self.state.event_bus.emit(
                        Event(name="capability.confirm.required", payload={"action": action, "dangerous": True})
                    )
                except Exception:
                    pass
                return ExecutionResult(
                    False,
                    f"Confirmation required for '{action}' (destructive). Use --yes, set ATLAS_AUTO_CONFIRM=1, or confirm interactively.",
                )
            else:
                try:
                    self.state.event_bus.emit(
                        Event(name="capability.confirm.auto", payload={"action": action, "auto_confirm": True})
                    )
                except Exception:
                    pass
        return None

    def execute(self, plan: Plan) -> ExecutionResult:
        try:
            self.state.event_bus.emit(Event(name="tool.started", payload={"action": plan.action, "args": plan.args}))
        except Exception:
            pass

        route = self.router.route(plan)
        if route.target == "chat":
            self.state.record(plan.action, "needs-model", plan.args[0] if plan.args else "")
            result = ExecutionResult(False, "Atlas needs a model for that request.")
            try:
                self.state.event_bus.emit(Event(name="tool.finished", payload={"action": plan.action, "success": False, "reason": "needs-model"}))
            except Exception:
                pass
            return result

        # Check capability confirmation before execution
        confirm_result = self._check_capability_confirmation(plan.action)
        if confirm_result is not None:
            return confirm_result

        try:
            if plan.action == "noop":
                result = ExecutionResult(True, "No command provided.")
            else:
                tool = self.tools.get(plan.action)
                if tool is None:
                    result = ExecutionResult(False, f"Unknown command: {plan.action}")
                else:
                    tool_result = self.tools.execute(plan.action, plan.args)
                    if isinstance(tool_result, ExecutionResult):
                        result = tool_result
                    else:
                        result = ExecutionResult(True, str(tool_result))

            try:
                self.state.event_bus.emit(
                    Event(
                        name="tool.finished",
                        payload={"action": plan.action, "success": result.success, "message": result.message},
                    )
                )
                self.state.event_bus.emit(Event(name=f"tool.{plan.action}.finished", payload={"success": result.success}))
            except Exception:
                pass

            return result
        except Exception as exc:
            self.state.record(plan.action, "error", str(exc))
            try:
                self.state.event_bus.emit(Event(name="tool.failed", payload={"action": plan.action, "error": str(exc)}))
            except Exception:
                pass
            return ExecutionResult(False, f"Error: {exc}")

    def _workspace_create(self, args: list[str]) -> ExecutionResult:
        if not args:
            return ExecutionResult(False, "Usage: workspace create <name>")
        path = resolve_path(self.state.workspace, args[0])
        path.mkdir(parents=True, exist_ok=True)
        self.state.record("workspace_create", "success", str(path))
        return ExecutionResult(True, f"Workspace created: {path}")

    def _workspace_show(self, args: list[str]) -> ExecutionResult:
        self.state.record("workspace_show", "success", str(self.state.workspace))
        return ExecutionResult(True, "Current workspace:", str(self.state.workspace.resolve()))

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
            return ExecutionResult(False, "Usage: write <file> <text>")
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
        try:
            completed = subprocess.run(
                [sys.executable, str(path)],
                capture_output=True,
                text=True,
                cwd=self.state.workspace,
                timeout=15,
            )
            self.state.record("run", "success" if completed.returncode == 0 else "failed", str(path))
            detail = (completed.stdout or "") + (completed.stderr or "")
            if len(detail) > 10000:
                detail = detail[:10000] + "\n...[truncated 10KB limit]"
            result = ExecutionResult(
                completed.returncode == 0,
                f"Ran: {path.relative_to(self.state.workspace.resolve())}",
                detail.strip(),
            )
            try:
                self.state.event_bus.emit(Event(name="tool.run.finished", payload={"success": result.success, "path": str(path)}))
            except Exception:
                pass
            return result
        except subprocess.TimeoutExpired as exc:
            self.state.record("run", "timeout", str(path))
            out = (exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")) if exc.stdout else ""
            err = (exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")) if exc.stderr else ""
            detail = (out + err).strip() or "Process timed out after 15s"
            try:
                self.state.event_bus.emit(Event(name="tool.run.timeout", payload={"path": str(path)}))
            except Exception:
                pass
            return ExecutionResult(False, f"Timeout: {path.relative_to(self.state.workspace.resolve())}", detail)
        except Exception as exc:
            self.state.record("run", "error", f"{path}: {exc}")
            try:
                self.state.event_bus.emit(Event(name="tool.run.failed", payload={"path": str(path), "error": str(exc)}))
            except Exception:
                pass
            return ExecutionResult(False, f"Error running {path.relative_to(self.state.workspace.resolve())}: {exc}")

    def _show_memory(self, args: list[str]) -> ExecutionResult:
        if args and args[0].lower() in {"search", "find"}:
            if len(args) < 2:
                return ExecutionResult(False, "Usage: memory search <text>")
            query = " ".join(args[1:]).strip()
            matches = self.state.memory_backend.search(query)
            lines = [f"{entry['action']}: {entry['status']} - {entry.get('detail', '')}" for entry in matches[-20:]]
            self.state.record("memory_search", "success", query)
            return ExecutionResult(True, f"Memory search: {query}", "\n".join(lines) if lines else "No matches.")

        limit = 20
        if args and args[0].isdigit():
            limit = max(1, int(args[0]))
        lines = [f"{entry['action']}: {entry['status']} - {entry.get('detail', '')}" for entry in self.state.memory[-limit:]]
        self.state.record("memory", "success", f"limit={limit}")
        return ExecutionResult(True, "Recent memory:", "\n".join(lines) if lines else "No memory yet.")
