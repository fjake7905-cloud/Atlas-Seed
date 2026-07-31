from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
from typing import Any


APP_DIR = Path.cwd() / ".atlas"
DEFAULT_WORKSPACE = Path.cwd() / "workspace"
MEMORY_FILE = APP_DIR / "memory.json"


@dataclass
class AppState:
    workspace: Path = field(default_factory=lambda: DEFAULT_WORKSPACE)
    memory: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load(cls) -> "AppState":
        APP_DIR.mkdir(parents=True, exist_ok=True)
        workspace = DEFAULT_WORKSPACE
        workspace.mkdir(parents=True, exist_ok=True)

        memory: list[dict[str, Any]] = []
        if MEMORY_FILE.exists():
            try:
                memory = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                memory = []

        return cls(workspace=workspace, memory=memory)

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        MEMORY_FILE.write_text(
            json.dumps(self.memory, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def record(self, action: str, status: str, detail: str = "") -> None:
        self.memory.append({"action": action, "status": status, "detail": detail})
        self.save()
