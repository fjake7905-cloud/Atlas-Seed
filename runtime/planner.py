from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Plan:
    action: str
    args: list[str]
    confidence: float = 1.0
    raw: str = ""
    source: str = "rule"


def _strip_outer_quotes(s: str) -> str:
    """Strip outer matching quotes if entire string is wrapped, preserving inner quotes"""
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        # Check if inner doesn't have unescaped same quote at ends? Simple: strip if starts/ends with same quote
        # For "hello world" -> strip, for "nested 'quotes'" -> strip outer double, keep inner single
        return s[1:-1]
    return s


def _parse_write_like_args(raw: str, action: str) -> list[str] | None:
    """
    Parse write/append args preserving exact user text.
    raw: original raw string like 'write hello.py print('hello')'
    action: 'write' or 'append'
    Returns [filename, text] preserving exact text with quotes
    """
    # Remove action prefix case-insensitive
    # Find action word at start
    pattern = rf'^\s*{re.escape(action)}\s+'
    m = re.match(pattern, raw, re.IGNORECASE)
    if not m:
        return None
    rest = raw[m.end():]  # After action
    if not rest.strip():
        return []

    # Extract filename as first token respecting quotes, and text as remainder exact
    # Regex for first token: quoted double, quoted single, or non-space
    # Use DOTALL to preserve multiline
    file_match = re.match(r'^\s*(".*?"|\'.*?\'|\S+)\s*', rest, re.DOTALL)
    if not file_match:
        return None

    filename_raw = file_match.group(1)  # Includes quotes if present
    filename = _strip_outer_quotes(filename_raw)

    # Text is everything after filename token in original rest, preserving exact
    text_start = file_match.end()
    text = rest[text_start:]  # Preserve exact, including leading spaces? Lstrip one time for separation but keep inner
    # For file content, we want to preserve exactly as typed after filename, but strip leading spaces once
    # and also strip outer wrapper quotes if entire text is quoted
    text = text.lstrip()

    # If text is empty, return only filename (will be caught as usage error later)
    if not text:
        return [filename]

    # Preserve exact text, but strip outer wrapper quotes if whole text is quoted
    # Example: write notes.txt "hello world" -> text raw is "\"hello world\"" -> should become "hello world"
    # Example: write hello.py print('hello') -> text raw is "print('hello')" -> should stay as is (no outer wrapper)
    # We check: if text starts and ends with same quote and the inner doesn't break outer wrapping
    # For simplicity, if text is wrapped in matching quotes and length>=2, strip outer
    # But only if the outer quotes are not part of code like print('...') which starts with p, not quote
    # So check if text[0] in quotes and text[-1] same and text[0] != inner content start
    # Actually for "hello world", text = "\"hello world\"" -> starts and ends with "
    # For print('hello'), text = "print('hello')" -> starts with p, not quote, so not stripped
    # For "'single quoted'"? Edge.

    # Check if entire text is wrapped in quotes
    stripped_text = text.strip()
    if len(stripped_text) >= 2 and stripped_text[0] == stripped_text[-1] and stripped_text[0] in ('"', "'"):
        # Ensure it's not something like print('hello') which starts with p, ends with ), not quote
        # So this condition only triggers when whole text is quoted
        # Example: "\"hello world\"" -> stripped_text[0]=='"' and [-1]=='"' -> strip
        # Example: "'single'" -> strip
        # For safety, only strip if the outer quotes are the first and last char and there is no extra content outside
        # Since stripped_text is whole text trimmed, if it starts and ends with same quote, strip them
        text = _strip_outer_quotes(stripped_text)
    else:
        # Keep exact as is (preserve embedded quotes)
        text = text

    return [filename, text]


class Planner:
    def __init__(self, model_provider: Any | None = None):
        self.model_provider = model_provider

    def plan(self, raw: str) -> Plan:
        raw_stripped = raw.strip()
        if not raw_stripped:
            return Plan(action="noop", args=[], confidence=1.0, raw=raw, source="rule")

        # For write/append, use special parsing to preserve exact text
        lower = raw_stripped.lower()
        if lower.startswith("write ") or lower.startswith("write\t"):
            parsed = _parse_write_like_args(raw_stripped, "write")
            if parsed is not None:
                # parsed may be [filename] or [filename, text]
                return Plan(action="write", args=parsed, confidence=0.95, raw=raw, source="rule")
        if lower.startswith("append ") or lower.startswith("append\t"):
            parsed = _parse_write_like_args(raw_stripped, "append")
            if parsed is not None:
                return Plan(action="append", args=parsed, confidence=0.95, raw=raw, source="rule")

        # For other commands, use shlex
        try:
            parts = shlex.split(raw_stripped)
        except ValueError:
            parts = raw_stripped.split()

        if not parts:
            return Plan(action="noop", args=[], confidence=1.0, raw=raw, source="rule")

        head = parts[0].lower()

        # Workspace commands
        if head == "workspace" and len(parts) >= 2:
            sub = parts[1].lower()
            if sub in {"create", "show", "list", "delete", "current", "switch"}:
                if sub == "current":
                    return Plan(action="workspace_show", args=parts[2:], confidence=1.0, raw=raw, source="rule")
                return Plan(action=f"workspace_{sub}", args=parts[2:], confidence=1.0, raw=raw, source="rule")
            return Plan(action="chat", args=[raw], confidence=0.5, raw=raw, source="rule")

        # File operations
        if head in {"create", "read", "write", "list", "run", "memory", "append", "delete", "search"}:
            # For write/append we already handled above with exact preservation, but this is fallback
            # If we reach here via shlex path, args are from shlex (may have lost quotes)
            # For write/append, we should try to re-parse preserving exact if possible
            if head in {"write", "append"}:
                # Try exact parsing again as fallback
                exact = _parse_write_like_args(raw_stripped, head)
                if exact is not None and len(exact) >= 2:
                    # Prefer exact preserved version over shlex version
                    return Plan(action=head, args=exact, confidence=0.95, raw=raw, source="rule")
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
