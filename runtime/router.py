from __future__ import annotations

from dataclasses import dataclass

from runtime.planner import Plan


@dataclass(frozen=True)
class Route:
    target: str
    reason: str
    confidence: float = 1.0


class Router:
    def route(self, plan: Plan) -> Route:
        # High confidence rule-based plans go to local
        known_local = {
            "create",
            "read",
            "write",
            "list",
            "run",
            "memory",
            "append",
            "delete",
            "search",
            "workspace_create",
            "workspace_show",
            "workspace_list",
            "workspace_delete",
        }

        if plan.action in known_local:
            # Confidence from planner, default 1.0
            conf = getattr(plan, "confidence", 1.0)
            source = getattr(plan, "source", "rule")
            reason = f"local file/system capability via {source} (conf={conf:.2f})"
            return Route(target="local", reason=reason, confidence=conf)

        if plan.action == "noop":
            return Route(target="local", reason="noop", confidence=1.0)

        # Chat with low confidence if from rule, higher if from LLM that still says chat
        conf = getattr(plan, "confidence", 0.4)
        source = getattr(plan, "source", "rule")
        if plan.action == "chat":
            if source == "llm" and conf >= 0.7:
                # LLM says it's chat with high confidence - needs model but we have one
                return Route(target="local", reason=f"chat via llm (conf={conf:.2f}) - will use model provider", confidence=conf)
            return Route(target="chat", reason=f"needs model or clarification via {source} (conf={conf:.2f})", confidence=conf)

        # Unknown action -> chat
        return Route(target="chat", reason=f"unknown action {plan.action} via {plan.source} (conf={conf:.2f})", confidence=conf)
