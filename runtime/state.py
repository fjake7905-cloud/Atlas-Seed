from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from runtime.memory import PersistentMemory


def app_dir() -> Path:
    return Path.cwd() / ".atlas"


def workspace_dir() -> Path:
    return Path.cwd() / "workspace"


def memory_file() -> Path:
    return app_dir() / "memory.json"


@dataclass
class AppState:
    workspace: Path = field(default_factory=workspace_dir)
    memory_backend: PersistentMemory = field(default_factory=lambda: PersistentMemory(memory_file()))

    @classmethod
    def load(cls) -> "AppState":
        app_dir().mkdir(parents=True, exist_ok=True)
        workspace = workspace_dir()
        workspace.mkdir(parents=True, exist_ok=True)
        return cls(workspace=workspace)

    @property
    def memory(self) -> list[dict[str, Any]]:
        return self.memory_backend.items

    def save(self) -> None:
        self.memory_backend.save()

    def record(self, action: str, status: str, detail: str = "") -> None:
        self.memory_backend.add({"action": action, "status": status, "detail": detail})
