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
    # Check for --yes flag to auto-confirm dangerous ops
    auto_yes = "--yes" in os.sys.argv or os.getenv("ATLAS_AUTO_CONFIRM", "").lower() in {"1", "true", "yes"}
    state = AppState.load(auto_confirm=auto_yes)
    agent = BaseAgent(state=state, planner=Planner(), executor=Executor(state))
    loop = AgentLoop(agent)

    version = get_version()
    # Keep marker "Atlas Seed" for verification
    print(f"Atlas Seed v{version}")
    print(f"Workspace: {state.workspace.resolve()}")
    print('Type "help" for commands, or "exit" to quit.')
    if state.auto_confirm:
        print('(Auto-confirm enabled for destructive operations)')

    # Subscribe to capability confirmation events for logging
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
                "  workspace create <name>\n"
                "  workspace show\n"
                "  create <file>\n"
                "  read <file>\n"
                "  write <file> <text>\n"
                "  list\n"
                "  run <python file>\n"
                "  memory [search <text>]\n"
                "  exit\n"
                "Options:\n"
                "  --yes : auto-confirm dangerous operations (write, run)\n"
            )
            continue

        step = loop.step(raw)

        # Handle confirmation requirement
        if "Confirmation required" in step.output_text and not state.auto_confirm:
            print(step.output_text)
            try:
                confirm = input("Confirm? (y/n): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nCancelled.")
                continue
            if confirm in {"y", "yes"}:
                # Temporarily enable auto_confirm and retry
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
