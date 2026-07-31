from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REQUIRED_FILES = [
    "ATLAS_RULES.md",
    "atlas.py",
    ".gitignore",
    "runtime/__init__.py",
    "runtime/state.py",
    "runtime/events.py",
    "runtime/planner.py",
    "runtime/router.py",
    "runtime/executor.py",
    "runtime/task.py",
    "runtime/agent_loop.py",
    "runtime/memory.py",
    "core/__init__.py",
    "core/capabilities.py",
    "core/tools.py",
    "agents/__init__.py",
    "agents/base_agent.py",
    "tests/test_runtime.py",
    "tests/test_tools.py",
    "tests/test_memory.py",
]

REQUIRED_MARKERS = {
    "runtime/planner.py": ["class Planner", "def plan"],
    "runtime/executor.py": ["class Executor", "def execute"],
    "runtime/agent_loop.py": ["class AgentLoop", "def step"],
    "runtime/memory.py": ["class PersistentMemory", "def add"],
    "core/tools.py": ["class ToolRegistry", "def register"],
    "agents/base_agent.py": ["class BaseAgent", "def handle"],
    "tests/test_runtime.py": ["class RuntimeTests"],
    "tests/test_tools.py": ["class ToolTests"],
    "tests/test_memory.py": ["class MemoryTests"],
}


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    details: str = ""


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()

    results = []
    for item in REQUIRED_FILES:
        path = root / item
        results.append(CheckResult(item, path.exists(), "present" if path.exists() else "missing"))

    for item, markers in REQUIRED_MARKERS.items():
        path = root / item
        if not path.exists():
            results.append(CheckResult(item, False, "file missing"))
            continue
        missing = [m for m in markers if m not in read_text(path)]
        results.append(CheckResult(item, not missing, "ok" if not missing else str(missing)))

    ok = True
    for result in results:
        ok &= result.ok
        print(f"{'OK' if result.ok else 'FAIL'} {result.name}: {result.details}")

    print("RESULT: PASS" if ok else "RESULT: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
