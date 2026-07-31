from __future__ import annotations

import sys
from pathlib import Path

from runtime.executor import Executor
from runtime.planner import Planner
from runtime.state import AppState


def main() -> int:
    state = AppState.load()
    planner = Planner()
    executor = Executor(state)

    print("Atlas Seed v0.1")
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
                "  memory\n"
                "  exit"
            )
            continue

        plan = planner.plan(raw)
        result = executor.execute(plan)
        print(result.message)
        if result.detail:
            print(result.detail)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
