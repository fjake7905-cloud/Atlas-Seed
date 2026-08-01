from __future__ import annotations

from dataclasses import dataclass
import subprocess
import sys
from pathlib import Path

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
        self.tools.register(Tool("workspace_list", "List workspace folders.", self._workspace_list))
        self.tools.register(Tool("workspace_delete", "Delete a workspace folder.", self._workspace_delete))
        self.tools.register(Tool("create", "Create a file.", self._create_file))
        self.tools.register(Tool("read", "Read a file.", self._read_file))
        self.tools.register(Tool("write", "Write to a file.", self._write_file))
        self.tools.register(Tool("append", "Append to a file.", self._append_file))
        self.tools.register(Tool("delete", "Delete a file.", self._delete_file))
        self.tools.register(Tool("search", "Search text in workspace files.", self._search_files))
        self.tools.register(Tool("list", "List workspace files.", self._list_files))
        self.tools.register(Tool("run", "Run a Python file.", self._run_python))
        self.tools.register(Tool("memory", "Show recent memory or search it.", self._show_memory))

    def _check_capability_confirmation(self, action: str) -> ExecutionResult | None:
        if self.capabilities.needs_confirmation(action):
            if not self.state.auto_confirm:
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

    def _workspace_list(self, args: list[str]) -> ExecutionResult:
        base = self.state.workspace
        if args:
            try:
                base = resolve_path(self.state.workspace, args[0])
            except Exception as e:
                return ExecutionResult(False, f"Invalid path: {e}")
        if not base.exists():
            return ExecutionResult(False, f"Path not found: {base}")
        entries = []
        for item in sorted(base.iterdir()):
            if item.is_dir():
                entries.append(f"{item.name}/")
        if not entries:
            for item in sorted(base.iterdir()):
                suffix = "/" if item.is_dir() else ""
                entries.append(f"{item.name}{suffix}")
        self.state.record("workspace_list", "success", str(base))
        detail = "\n".join(entries) if entries else "(empty)"
        return ExecutionResult(True, f"Workspace listing: {base.relative_to(self.state.workspace.resolve()) if base != self.state.workspace else '.'}", detail)

    def _workspace_delete(self, args: list[str]) -> ExecutionResult:
        if not args:
            return ExecutionResult(False, "Usage: workspace delete <name>")
        path = resolve_path(self.state.workspace, args[0])
        if not path.exists():
            return ExecutionResult(False, f"Workspace not found: {args[0]}")
        if path.resolve() == self.state.workspace.resolve():
            return ExecutionResult(False, "Cannot delete root workspace")
        try:
            import shutil

            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            self.state.record("workspace_delete", "success", str(path))
            return ExecutionResult(True, f"Workspace deleted: {args[0]}")
        except Exception as e:
            self.state.record("workspace_delete", "failed", f"{path}: {e}")
            return ExecutionResult(False, f"Failed to delete {args[0]}: {e}")

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

    def _interpret_escapes(self, text: str) -> str:
        try:
            return text.encode("utf-8").decode("unicode_escape")
        except Exception:
            return text.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")

    def _write_file(self, args: list[str]) -> ExecutionResult:
        if len(args) < 2:
            return ExecutionResult(False, "Usage: write <file> <text>")
        path = resolve_path(self.state.workspace, args[0])
        raw_text = " ".join(args[1:])
        text = self._interpret_escapes(raw_text)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.state.record("write", "success", str(path))
        return ExecutionResult(True, f"Written: {path.relative_to(self.state.workspace.resolve())}")

    def _append_file(self, args: list[str]) -> ExecutionResult:
        if len(args) < 2:
            return ExecutionResult(False, "Usage: append <file> <text>")
        path = resolve_path(self.state.workspace, args[0])
        raw_text = " ".join(args[1:])
        text = self._interpret_escapes(raw_text)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = ""
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing and not existing.endswith("\n") and not text.startswith("\n"):
                text = "\n" + text
        if not path.exists():
            path.write_text(text, encoding="utf-8")
        else:
            with path.open("a", encoding="utf-8") as f:
                f.write(text)
        self.state.record("append", "success", str(path))
        return ExecutionResult(True, f"Appended: {path.relative_to(self.state.workspace.resolve())}")

    def _delete_file(self, args: list[str]) -> ExecutionResult:
        if not args:
            return ExecutionResult(False, "Usage: delete <file>")
        path = resolve_path(self.state.workspace, args[0])
        if not path.exists():
            return ExecutionResult(False, f"File not found: {args[0]}")
        try:
            if path.is_dir():
                import shutil

                shutil.rmtree(path)
            else:
                path.unlink()
            self.state.record("delete", "success", str(path))
            return ExecutionResult(True, f"Deleted: {args[0]}")
        except Exception as e:
            self.state.record("delete", "failed", f"{path}: {e}")
            return ExecutionResult(False, f"Failed to delete {args[0]}: {e}")

    def _search_files(self, args: list[str]) -> ExecutionResult:
        if not args:
            return ExecutionResult(False, "Usage: search <text> [path]")
        query = args[0]
        search_path = self.state.workspace
        if len(args) > 1:
            try:
                search_path = resolve_path(self.state.workspace, args[1])
            except Exception as e:
                return ExecutionResult(False, f"Invalid search path: {e}")
        if not search_path.exists():
            return ExecutionResult(False, f"Search path not found: {search_path}")
        matches = []
        try:
            for file_path in search_path.rglob("*"):
                if file_path.is_file():
                    try:
                        if file_path.stat().st_size > 1_000_000:
                            continue
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        if query.lower() in content.lower():
                            for i, line in enumerate(content.splitlines(), 1):
                                if query.lower() in line.lower():
                                    rel = file_path.relative_to(self.state.workspace.resolve())
                                    matches.append(f"{rel}:{i}: {line.strip()[:200]}")
                                    if len(matches) >= 50:
                                        break
                            if len(matches) >= 50:
                                break
                    except Exception:
                        continue
        except Exception as e:
            return ExecutionResult(False, f"Search failed: {e}")
        self.state.record("search", "success", f"{query} in {search_path}")
        if not matches:
            return ExecutionResult(True, f"No matches for '{query}'", "")
        detail = "\n".join(matches)
        if len(matches) >= 50:
            detail += "\n...[truncated 50 matches]"
        return ExecutionResult(True, f"Found {len(matches)} matches for '{query}':", detail)

    def _list_files(self, args: list[str]) -> ExecutionResult:
        path = self.state.workspace if not args else resolve_path(self.state.workspace, args[0])
        if not path.exists():
            return ExecutionResult(False, f"Path not found: {args[0] if args else '.'}")
        entries = []
        for item in sorted(path.iterdir()):
            suffix = "/" if item.is_dir() else ""
            entries.append(f"{item.name}{suffix}")
        self.state.record("list", "success", str(path))
        return ExecutionResult(
            True,
            f"Listing: {path.relative_to(self.state.workspace.resolve()) if path != self.state.workspace else '.'}",
            "\n".join(entries) if entries else "(empty)",
        )

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
        # Handle various memory subcommands
        if not args:
            # Recent 20
            lines = [
                f"[{entry.get('id','')} {entry.get('timestamp','')[:19]}] {entry['action']}: {entry['status']} - {entry.get('detail','')}"
                for entry in self.state.memory[-20:]
            ]
            self.state.record("memory", "success", "limit=20")
            return ExecutionResult(True, "Recent memory (20):", "\n".join(lines) if lines else "No memory yet.")

        sub = args[0].lower()

        if sub in {"search", "find"}:
            if len(args) < 2:
                return ExecutionResult(False, "Usage: memory search <text> [limit]")
            query = " ".join(args[1:]).strip()
            # Check if last arg is digit for limit
            limit = 20
            parts = query.split()
            if parts and parts[-1].isdigit():
                try:
                    limit = max(1, int(parts[-1]))
                    query = " ".join(parts[:-1])
                except Exception:
                    pass
            matches = self.state.memory_backend.search(query)
            # Show with id and timestamp
            lines = [
                f"[{e.get('id','')} {e.get('timestamp','')[:19]}] {e['action']}: {e['status']} - {e.get('detail','')}"
                for e in matches[-limit:]
            ]
            self.state.record("memory_search", "success", query)
            return ExecutionResult(True, f"Memory search: '{query}' (last {limit} of {len(matches)} matches)", "\n".join(lines) if lines else "No matches.")

        if sub in {"clear", "reset", "wipe"}:
            # Dangerous, but allow with auto_confirm
            if not self.state.auto_confirm:
                return ExecutionResult(
                    False,
                    "Confirmation required for 'memory clear' (deletes all memory). Use --yes or ATLAS_AUTO_CONFIRM=1",
                )
            count = self.state.memory_backend.clear()
            self.state.record("memory_clear", "success", f"cleared {count}")
            return ExecutionResult(True, f"Memory cleared: {count} entries removed")

        if sub in {"stats", "stat", "info"}:
            stats = self.state.memory_backend.stats()
            detail = (
                f"Total: {stats['total']}\n"
                f"Session: {stats['session_id']}\n"
                f"Oldest: {stats['oldest']}\n"
                f"Newest: {stats['newest']}\n"
                f"Actions: {stats['actions']}"
            )
            self.state.record("memory_stats", "success", f"total={stats['total']}")
            return ExecutionResult(True, "Memory stats:", detail)

        if sub in {"export", "save", "backup"}:
            export_path = None
            if len(args) > 1:
                try:
                    export_path = resolve_path(self.state.workspace, args[1])
                except Exception:
                    export_path = Path(args[1])
            saved = self.state.memory_backend.export(export_path)
            self.state.record("memory_export", "success", str(saved))
            return ExecutionResult(True, f"Memory exported to: {saved}")

        if sub in {"prune", "trim", "clean"}:
            keep = 100
            if len(args) > 1 and args[1].isdigit():
                keep = max(1, int(args[1]))
            pruned = self.state.memory_backend.prune(keep_last=keep)
            self.state.record("memory_prune", "success", f"pruned {pruned}, kept {keep}")
            return ExecutionResult(True, f"Memory pruned: {pruned} removed, kept last {keep}")

        if sub.isdigit():
            limit = max(1, int(sub))
            lines = [
                f"[{entry.get('id','')} {entry.get('timestamp','')[:19]}] {entry['action']}: {entry['status']} - {entry.get('detail','')}"
                for entry in self.state.memory[-limit:]
            ]
            self.state.record("memory", "success", f"limit={limit}")
            return ExecutionResult(True, f"Recent memory ({limit}):", "\n".join(lines) if lines else "No memory yet.")

        # Unknown subcommand -> treat as search
        query = " ".join(args).strip()
        matches = self.state.memory_backend.search(query)
        lines = [
            f"[{e.get('id','')} {e.get('timestamp','')[:19]}] {e['action']}: {e['status']} - {e.get('detail','')}"
            for e in matches[-20:]
        ]
        self.state.record("memory_search", "success", query)
        return ExecutionResult(True, f"Memory search: '{query}'", "\n".join(lines) if lines else "No matches.")
