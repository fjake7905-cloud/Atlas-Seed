from __future__ import annotations

import json
import os
from pathlib import Path

from agents.base_agent import BaseAgent
from runtime.agent_loop import AgentLoop
from runtime.executor import Executor
from runtime.planner import Planner
from runtime.state import AppState


def get_version() -> str:
    """Read version from atlas_manifest.json (single source of truth), fallback to 0.5"""
    try:
        manifest_path = Path(__file__).parent / "atlas_manifest.json"
        if manifest_path.exists():
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            ver = data.get("version")
            if isinstance(ver, str) and ver:
                return ver
    except Exception:
        pass
    return "0.5"


def main() -> int:
    auto_yes = "--yes" in os.sys.argv or os.getenv("ATLAS_AUTO_CONFIRM", "").lower() in {"1", "true", "yes"}
    state = AppState.load(auto_confirm=auto_yes)
    agent = BaseAgent(state=state, planner=Planner(), executor=Executor(state))
    loop = AgentLoop(agent)

    version = get_version()
    print(f"Atlas Seed v{version}")
    print(f"Workspace: {state.workspace.resolve()}")
    print('Type "help" for commands, or "exit" to quit.')
    if state.auto_confirm:
        print('(Auto-confirm enabled for destructive operations)')

    def on_confirm_required(event):
        if not state.auto_confirm:
            print(f"[Security] Confirmation required for: {event.payload.get('action')}")

    try:
        state.event_bus.on("capability.confirm.required", on_confirm_required)
    except Exception:
        pass

    while True:
        try:
            raw = input("atlas> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return 0

        if not raw:
            continue

        if raw.lower() in {"exit", "quit"}:
            print("Bye.")
            return 0

        if raw.lower() == "help":
            print(
                "Commands:\n"
                "  workspace create <name>  - Create sub-workspace\n"
                "  workspace show           - Show current workspace path\n"
                "  workspace list [path]    - List workspaces/folders\n"
                "  workspace delete <name>  - Delete workspace folder\n"
                "  create <file>            - Create empty file\n"
                "  read <file>              - Read file content\n"
                "  write <file> <text>      - Write to file (supports quoted strings, \\n)\n"
                "  append <file> <text>     - Append to file\n"
                "  delete <file>            - Delete file\n"
                "  search <text> [path]     - Search text in files\n"
                "  list [path]              - List files (ls)\n"
                "  run <python file>        - Run Python file\n"
                "  memory                   - Show recent memory (20)\n"
                "  memory <N>               - Show recent N entries\n"
                "  memory [search <text>]   - Show/search memory (legacy format, also: search <text> [limit])\n"
                "  memory search <text> [limit] - Search memory\n"
                "  memory stats             - Show memory statistics\n"
                "  memory export [file]     - Export memory to file\n"
                "  memory prune [keep]      - Keep only last N (default 100)\n"
                "  memory clear             - Clear all memory (dangerous)\n"
                "  exit / quit              - Exit\n"
                "Options:\n"
                "  --yes : auto-confirm dangerous operations (write, run, delete, memory clear)\n"
                "Examples:\n"
                "  write notes.txt \"hello world\"\n"
                "  write multi.txt \"line1\\nline2\\nline3\"\n"
                "  append log.txt \"new entry\"\n"
                "  search TODO\n"
                "  memory search demo.py 5\n"
                "  memory stats\n"
                "  read \"my file.txt\"\n"
            )
            continue

        step = loop.step(raw)

        if "Confirmation required" in step.output_text and not state.auto_confirm:
            print(step.output_text)
            try:
                confirm = input("Confirm? (y/n): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nCancelled.")
                continue
            if confirm in {"y", "yes"}:
                state.auto_confirm = True
                step = loop.step(raw)
                state.auto_confirm = False
                print(step.output_text)
            else:
                print("Cancelled.")
            continue

        print(step.output_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
