from __future__ import annotations

from dataclasses import dataclass

from runtime.planner import Plan


@dataclass(frozen=True)
class Route:
    target: str
    reason: str


class Router:
    def route(self, plan: Plan) -> Route:
        if plan.action in {"create", "read", "write", "list", "run", "memory", "workspace_create", "workspace_show"}:
            return Route(target="local", reason="local file/system capability")
        return Route(target="chat", reason="needs model or user clarification")
