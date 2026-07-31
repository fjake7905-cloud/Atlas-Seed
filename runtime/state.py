from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from runtime.memory import PersistentMemory


APP_DIR = Path.cwd() / ".atlas"
DEFAULT_WORKSPACE = Path.cwd() / "workspace"
MEMORY_FILE = APP_DIR / "memory.json"


@dataclass
class AppState:
    workspace: Path = field(default_factory=lambda: DEFAULT_WORKSPACE)
    memory_backend: PersistentMemory = field(default_factory=lambda: PersistentMemory(MEMORY_FILE))

    @classmethod
    def load(cls) -> "AppState":
        APP_DIR.mkdir(parents=True, exist_ok=True)
        workspace = DEFAULT_WORKSPACE
        workspace.mkdir(parents=True, exist_ok=True)
        return cls(workspace=workspace)

    @property
    def memory(self) -> list[dict[str, Any]]:
        return self.memory_backend.items

    def save(self) -> None:
        self.memory_backend.save()

    def record(self, action: str, status: str, detail: str = "") -> None:
        self.memory_backend.add({"action": action, "status": status, "detail": detail})
