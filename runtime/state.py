from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from runtime.events import Event, EventBus
from runtime.memory import PersistentMemory


def _resolve_base(root: Path | str | None = None) -> Path:
    """Resolve base dir: explicit root > ATLAS_ROOT env > cwd"""
    if root is not None:
        return Path(root).resolve()
    env_root = os.getenv("ATLAS_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path.cwd().resolve()


def app_dir(root: Path | str | None = None) -> Path:
    return _resolve_base(root) / ".atlas"


def workspace_dir(root: Path | str | None = None) -> Path:
    return _resolve_base(root) / "workspace"


def memory_file(root: Path | str | None = None) -> Path:
    return app_dir(root) / "memory.json"


@dataclass
class AppState:
    workspace: Path = field(default_factory=workspace_dir)
    memory_backend: PersistentMemory = field(default_factory=lambda: PersistentMemory(memory_file()))
    root: Path = field(default_factory=lambda: _resolve_base(None))
    event_bus: EventBus = field(default_factory=EventBus)

    @classmethod
    def load(cls, root: Path | str | None = None) -> "AppState":
        base = _resolve_base(root)
        a_dir = base / ".atlas"
        a_dir.mkdir(parents=True, exist_ok=True)
        workspace = base / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        mem_file = a_dir / "memory.json"
        memory_backend = PersistentMemory(mem_file)
        event_bus = EventBus()
        return cls(workspace=workspace, memory_backend=memory_backend, root=base, event_bus=event_bus)

    @property
    def memory(self) -> list[dict[str, Any]]:
        return self.memory_backend.items

    def save(self) -> None:
        self.memory_backend.save()

    def record(self, action: str, status: str, detail: str = "") -> None:
        entry = {"action": action, "status": status, "detail": detail}
        self.memory_backend.add(entry)
        # Wire EventBus: emit memory event
        try:
            self.event_bus.emit(Event(name="memory.added", payload=entry))
            self.event_bus.emit(Event(name=f"memory.{action}", payload=entry))
        except Exception:
            pass  # EventBus should never break core flow
