from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Plan:
    action: str
    args: list[str]
    confidence: float = 1.0
    raw: str = ""
    source: str = "rule"  # rule or llm


class Planner:
    def __init__(self, model_provider: Any | None = None):
        self.model_provider = model_provider

    def plan(self, raw: str) -> Plan:
        raw_stripped = raw.strip()
        if not raw_stripped:
            return Plan(action="noop", args=[], confidence=1.0, raw=raw, source="rule")

        try:
            parts = shlex.split(raw_stripped)
        except ValueError:
            parts = raw_stripped.split()

        if not parts:
            return Plan(action="noop", args=[], confidence=1.0, raw=raw, source="rule")

        head = parts[0].lower()

        # Workspace commands: create, show, list, delete, current, switch
        if head == "workspace" and len(parts) >= 2:
            sub = parts[1].lower()
            if sub in {"create", "show", "list", "delete", "current", "switch"}:
                # Map current -> show, switch -> switch
                if sub == "current":
                    return Plan(action="workspace_show", args=parts[2:], confidence=1.0, raw=raw, source="rule")
                return Plan(action=f"workspace_{sub}", args=parts[2:], confidence=1.0, raw=raw, source="rule")
            return Plan(action="chat", args=[raw], confidence=0.5, raw=raw, source="rule")

        # File operations
        if head in {"create", "read", "write", "list", "run", "memory", "append", "delete", "search"}:
            return Plan(action=head, args=parts[1:], confidence=0.95, raw=raw, source="rule")

        if head in {"ls"}:
            return Plan(action="list", args=parts[1:], confidence=0.9, raw=raw, source="rule")
        if head in {"cat"}:
            return Plan(action="read", args=parts[1:], confidence=0.9, raw=raw, source="rule")
        if head in {"rm"}:
            return Plan(action="delete", args=parts[1:], confidence=0.9, raw=raw, source="rule")
        if head in {"pwd", "whereami"}:
            return Plan(action="workspace_show", args=[], confidence=0.9, raw=raw, source="rule")

        if self.model_provider is not None:
            llm_plan = self._plan_with_llm(raw_stripped)
            if llm_plan is not None:
                return llm_plan

        return Plan(action="chat", args=[raw], confidence=0.4, raw=raw, source="rule")

    def _plan_with_llm(self, raw: str) -> Plan | None:
        if self.model_provider is None:
            return None
        try:
            prompt = (
                f"User request: {raw}\n"
                "Available tools: create <file>, read <file>, write <file> <text>, append <file> <text>, "
                "delete <file>, search <text>, list, run <file>, memory, workspace_create <name>, workspace_list, workspace_switch <name>\n"
                "If request is a file operation, return JSON: {\"action\": \"tool_name\", \"args\": [\"arg1\", ...]}\n"
                "If general question, return JSON: {\"action\": \"chat\", \"args\": [\"question\"]}\n"
                "Return ONLY JSON, no explanation.\n"
            )
            response = self.model_provider.complete(prompt, context={"task": raw})
            text = response.text.strip()
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                json_str = text[start : end + 1]
                try:
                    data = json.loads(json_str)
                    action = data.get("action")
                    args = data.get("args", [])
                    if isinstance(action, str) and isinstance(args, list):
                        known_actions = {
                            "create",
                            "read",
                            "write",
                            "append",
                            "delete",
                            "search",
                            "list",
                            "run",
                            "memory",
                            "workspace_create",
                            "workspace_show",
                            "workspace_list",
                            "workspace_delete",
                            "workspace_switch",
                            "chat",
                            "noop",
                        }
                        if action in known_actions:
                            return Plan(
                                action=action,
                                args=[str(a) for a in args],
                                confidence=0.75,
                                raw=raw,
                                source="llm",
                            )
                except json.JSONDecodeError:
                    pass
            try:
                data = json.loads(text)
                action = data.get("action")
                args = data.get("args", [])
                if isinstance(action, str) and isinstance(args, list):
                    return Plan(action=action, args=[str(a) for a in args], confidence=0.7, raw=raw, source="llm")
            except Exception:
                pass
        except Exception:
            pass
        return None
