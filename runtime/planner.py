from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Plan:
    action: str
    args: list[str]


class Planner:
    def plan(self, raw: str) -> Plan:
        parts = raw.split()
        if not parts:
            return Plan(action="noop", args=[])

        head = parts[0].lower()
        if head == "workspace" and len(parts) >= 2:
            return Plan(action=f"workspace_{parts[1].lower()}", args=parts[2:])
        if head in {"create", "read", "write", "list", "run", "memory"}:
            return Plan(action=head, args=parts[1:])
        return Plan(action="chat", args=[raw])
