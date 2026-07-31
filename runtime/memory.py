from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class PersistentMemory:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.items: list[dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                self.items = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.items = []

    def add(self, event: dict[str, Any]) -> None:
        self.items.append(event)
        self.save()

    def search(self, text: str) -> list[dict[str, Any]]:
        return [item for item in self.items if text.lower() in str(item).lower()]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
