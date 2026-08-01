from __future__ import annotations

import json
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
    state = AppState.load()
    agent = BaseAgent(state=state, planner=Planner(), executor=Executor(state))
    loop = AgentLoop(agent)

    version = get_version()
    # Keep marker "Atlas Seed" for verification
    print(f"Atlas Seed v{version}")
    print(f"Workspace: {state.workspace.resolve()}")
    print('Type "help" for commands, or "exit" to quit.')

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
                "  exit"
            )
            continue

        step = loop.step(raw)
        print(step.output_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
