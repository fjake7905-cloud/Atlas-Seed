from __future__ import annotations

import argparse
import json
import os
import sys
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


def create_state(workspace: str | None = None, auto_confirm: bool = False) -> AppState:
    root = Path(workspace).resolve() if workspace else None
    return AppState.load(root=root, auto_confirm=auto_confirm)


def run_single_task(state: AppState, task: str, debug: bool = False) -> int:
    agent = BaseAgent(state=state, planner=Planner(model_provider=state.model_provider), executor=Executor(state))
    loop = AgentLoop(agent)

    if debug:
        print(f"[Debug] Provider: {state.model_provider.name if state.model_provider else 'none'}")
        print(f"[Debug] Workspace: {state.workspace.resolve()}")
        print(f"[Debug] Task: {task}")

    step = loop.step(task)
    print(step.output_text)
    return 0 if "Error" not in step.output_text and "Failed" not in step.output_text else 1


def run_batch(state: AppState, batch_file: str, debug: bool = False) -> int:
    path = Path(batch_file)
    if not path.exists():
        print(f"Batch file not found: {batch_file}", file=sys.stderr)
        return 1

    agent = BaseAgent(state=state, planner=Planner(model_provider=state.model_provider), executor=Executor(state))
    loop = AgentLoop(agent)

    lines = path.read_text(encoding="utf-8").splitlines()
    exit_code = 0

    for i, raw in enumerate(lines, 1):
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        if debug:
            print(f"\n[Batch {i}] atlas> {raw}")
        step = loop.step(raw)
        print(step.output_text)
        if "Error" in step.output_text and "Confirmation required" not in step.output_text:
            # Continue but track failure
            exit_code = 1

    return exit_code


def run_verify() -> int:
    try:
        import subprocess

        print("Running Atlas verification...")
        result = subprocess.run([sys.executable, "scripts/verify_atlas.py"], cwd=Path(__file__).parent)
        if result.returncode != 0:
            return result.returncode

        print("\nRunning pytest...")
        result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=Path(__file__).parent)
        return result.returncode
    except Exception as e:
        print(f"Verify failed: {e}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Atlas Seed - Autonomous agent platform",
        epilog="Examples: python atlas.py --task \"create demo.py\" --yes --workspace /tmp/ws",
    )
    parser.add_argument("--task", "-t", type=str, help="Run single task non-interactively and exit")
    parser.add_argument("--batch", "-b", type=str, help="Run batch file with one command per line")
    parser.add_argument("--workspace", "-w", type=str, help="Workspace root path (default cwd)")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm destructive operations")
    parser.add_argument("--no-confirm", action="store_true", help="Same as --yes (auto-confirm)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--verify", action="store_true", help="Run verification (verify_atlas.py + pytest) and exit")
    parser.add_argument("--version", "-v", action="store_true", help="Show version and exit")
    parser.add_argument("--list-tools", action="store_true", help="List available tools and exit")

    args = parser.parse_args()

    version = get_version()

    if args.version:
        print(f"Atlas Seed v{version}")
        return 0

    if args.verify:
        return run_verify()

    auto_yes = args.yes or args.no_confirm or os.getenv("ATLAS_AUTO_CONFIRM", "").lower() in {"1", "true", "yes"}
    state = create_state(workspace=args.workspace, auto_confirm=auto_yes)

    if args.list_tools:
        agent = BaseAgent(state=state, planner=Planner(), executor=Executor(state))
        tools = agent.executor.tools.list()
        caps = agent.executor.capabilities
        print(f"Atlas Seed v{version} - Available tools ({len(tools)}):")
        for tool_name in tools:
            desc = agent.executor.tools.describe(tool_name) or ""
            needs_confirm = " [needs confirm]" if caps.needs_confirmation(tool_name) else ""
            print(f"  {tool_name:20} - {desc}{needs_confirm}")
        return 0

    # Non-interactive single task
    if args.task:
        if args.debug:
            print(f"Atlas Seed v{version} - Non-interactive task mode")
        return run_single_task(state, args.task, debug=args.debug)

    # Batch mode
    if args.batch:
        if args.debug:
            print(f"Atlas Seed v{version} - Batch mode: {args.batch}")
        return run_batch(state, args.batch, debug=args.debug)

    # Interactive REPL (default)
    agent = BaseAgent(state=state, planner=Planner(model_provider=state.model_provider), executor=Executor(state))
    loop = AgentLoop(agent)

    print(f"Atlas Seed v{version}")
    print(f"Workspace: {state.workspace.resolve()}")
    print('Type "help" for commands, or "exit" to quit.')
    if state.auto_confirm:
        print('(Auto-confirm enabled for destructive operations)')
    if args.workspace:
        print(f'(Custom workspace: {args.workspace})')

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
                "  memory [search <text>]   - Show/search memory\n"
                "  memory search <text> [limit] - Search memory\n"
                "  memory stats             - Show memory statistics\n"
                "  memory export [file]     - Export memory to file\n"
                "  memory prune [keep]      - Keep only last N (default 100)\n"
                "  memory clear             - Clear all memory (dangerous)\n"
                "  exit / quit              - Exit\n"
                "Options:\n"
                "  --yes : auto-confirm dangerous operations\n"
                "  --task \"cmd\" : run single task non-interactively\n"
                "  --batch file.txt : run batch file\n"
                "  --workspace PATH : custom workspace root\n"
                "  --verify : run verification\n"
                "  --version : show version\n"
                "  --list-tools : list available tools\n"
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
