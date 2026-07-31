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
    "runtime/events.py",
    "runtime/state.py",
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
    "tests/test_agent_core.py",
]

REQUIRED_MARKERS = {
    "atlas.py": ["Atlas Seed", "workspace", "help", "memory [search <text>]"],
    "runtime/state.py": ["class AppState", "memory_backend", "def record"],
    "runtime/planner.py": ["class Planner", "def plan"],
    "runtime/executor.py": ["class Executor", "ToolRegistry", "def execute", "memory_search"],
    "runtime/agent_loop.py": ["class AgentLoop", "def step"],
    "runtime/memory.py": ["class PersistentMemory", "def add"],
    "core/tools.py": ["class ToolRegistry", "def register", "def execute"],
    "agents/base_agent.py": ["class BaseAgent", "def handle"],
    "tests/test_runtime.py": ["class RuntimeTests"],
    "tests/test_tools.py": ["class ToolTests"],
    "tests/test_memory.py": ["class MemoryTests"],
    "tests/test_agent_core.py": ["class AgentCoreTests", "tool_registry", "persists_memory"],
}


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    details: str = ""


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_required_files(repo_root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    for rel_path in REQUIRED_FILES:
        path = repo_root / rel_path
        results.append(CheckResult(name=rel_path, ok=path.exists(), details="present" if path.exists() else "missing"))
    return results


def check_content_markers(repo_root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    for rel_path, markers in REQUIRED_MARKERS.items():
        path = repo_root / rel_path
        if not path.exists():
            results.append(CheckResult(name=rel_path, ok=False, details="file missing"))
            continue
        content = read_text(path)
        missing = [marker for marker in markers if marker not in content]
        results.append(CheckResult(name=rel_path, ok=not missing, details="ok" if not missing else f"missing markers: {', '.join(missing)}"))
    return results


def format_results(title: str, results: Iterable[CheckResult]) -> tuple[str, bool]:
    lines = [title]
    all_ok = True
    for result in results:
        status = "OK" if result.ok else "FAIL"
        all_ok &= result.ok
        lines.append(f"- {status} {result.name}: {result.details}")
    return "\n".join(lines), all_ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify that Atlas Seed files and core behaviors exist.")
    parser.add_argument("--repo-root", default=".", help="Repository root to inspect.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if not repo_root.exists():
        print(f"Repo root not found: {repo_root}", file=sys.stderr)
        return 2

    file_results = check_required_files(repo_root)
    marker_results = check_content_markers(repo_root)

    file_report, files_ok = format_results("Required files", file_results)
    marker_report, markers_ok = format_results("Required markers", marker_results)

    print(file_report)
    print()
    print(marker_report)
    print()

    overall = files_ok and markers_ok
    print("RESULT: PASS" if overall else "RESULT: FAIL")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
