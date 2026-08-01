from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    handler: Callable[[list[str]], Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list(self) -> list[str]:
        return sorted(self._tools)

    def execute(self, name: str, args: list[str]) -> Any:
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        return tool.handler(args)

    def describe(self, name: str) -> str | None:
        tool = self.get(name)
        return tool.description if tool else None
