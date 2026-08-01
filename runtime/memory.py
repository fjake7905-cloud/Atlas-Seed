from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class PersistentMemory:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.items: list[dict[str, Any]] = []
        self.session_id: str = str(uuid.uuid4())[:8]
        self.load()
        try:
            from runtime.logger import get_logger

            get_logger().debug(f"PersistentMemory init: path={path} session={self.session_id} items={len(self.items)}")
        except Exception:
            pass

    def load(self) -> None:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self.items = data
                    for item in self.items:
                        if "id" not in item:
                            item["id"] = str(uuid.uuid4())[:8]
                        if "timestamp" not in item:
                            item["timestamp"] = datetime.now(timezone.utc).isoformat()
                else:
                    self.items = []
            except json.JSONDecodeError:
                self.items = []

    def add(self, event: dict[str, Any]) -> None:
        enriched = dict(event)
        if "id" not in enriched:
            enriched["id"] = str(uuid.uuid4())[:8]
        if "timestamp" not in enriched:
            enriched["timestamp"] = datetime.now(timezone.utc).isoformat()
        if "session_id" not in enriched:
            enriched["session_id"] = self.session_id
        self.items.append(enriched)
        self.save()
        try:
            from runtime.logger import get_logger

            get_logger().debug(f"Memory add: {enriched.get('action')}={enriched.get('status')} id={enriched.get('id')}")
        except Exception:
            pass

    def search(self, text: str) -> list[dict[str, Any]]:
        query = text.lower()
        results = []
        for item in self.items:
            haystack = (
                f"{item.get('action','')} {item.get('status','')} {item.get('detail','')} {item.get('id','')} {item.get('timestamp','')}"
            ).lower()
            if query in haystack or query in str(item).lower():
                results.append(item)
        return results

    def search_by_action(self, action: str) -> list[dict[str, Any]]:
        return [item for item in self.items if item.get("action") == action]

    def search_by_status(self, status: str) -> list[dict[str, Any]]:
        return [item for item in self.items if item.get("status") == status]

    def prune(self, keep_last: int = 100) -> int:
        if len(self.items) <= keep_last:
            return 0
        pruned = len(self.items) - keep_last
        self.items = self.items[-keep_last:]
        self.save()
        try:
            from runtime.logger import get_logger

            get_logger().info(f"Memory pruned: {pruned} removed, kept {keep_last}")
        except Exception:
            pass
        return pruned

    def clear(self) -> int:
        count = len(self.items)
        self.items = []
        self.save()
        try:
            from runtime.logger import get_logger

            get_logger().warning(f"Memory cleared: {count} entries removed")
        except Exception:
            pass
        return count

    def export(self, path: Path | None = None) -> Path:
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.items, ensure_ascii=False, indent=2), encoding="utf-8")
            return path
        return self.path

    def stats(self) -> dict[str, Any]:
        actions = {}
        for item in self.items:
            act = item.get("action", "unknown")
            actions[act] = actions.get(act, 0) + 1
        return {
            "total": len(self.items),
            "actions": actions,
            "session_id": self.session_id,
            "oldest": self.items[0].get("timestamp") if self.items else None,
            "newest": self.items[-1].get("timestamp") if self.items else None,
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
