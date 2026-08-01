from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Plan:
    action: str
    args: list[str]


class Planner:
    def plan(self, raw: str) -> Plan:
        raw = raw.strip()
        if not raw:
            return Plan(action="noop", args=[])

        # Try shlex to handle quoted strings, fallback to split on error
        try:
            parts = shlex.split(raw)
        except ValueError:
            # Unclosed quotes - treat as chat or fallback to simple split
            parts = raw.split()

        if not parts:
            return Plan(action="noop", args=[])

        head = parts[0].lower()

        # Workspace commands: workspace create <name>, workspace show, workspace list, workspace delete
        if head == "workspace" and len(parts) >= 2:
            sub = parts[1].lower()
            # Map to internal action names
            if sub in {"create", "show", "list", "delete"}:
                return Plan(action=f"workspace_{sub}", args=parts[2:])
            # Unknown workspace subcommand -> chat
            return Plan(action="chat", args=[raw])

        # File operations
        if head in {"create", "read", "write", "list", "run", "memory", "append", "delete", "search"}:
            return Plan(action=head, args=parts[1:])

        # Short aliases
        if head in {"ls"}:
            return Plan(action="list", args=parts[1:])
        if head in {"cat"}:
            return Plan(action="read", args=parts[1:])
        if head in {"rm"}:
            return Plan(action="delete", args=parts[1:])

        return Plan(action="chat", args=[raw])
