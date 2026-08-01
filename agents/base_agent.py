from __future__ import annotations

from dataclasses import dataclass

from runtime.events import Event
from runtime.executor import Executor, ExecutionResult
from runtime.planner import Planner, Plan
from runtime.state import AppState
from runtime.task import Task


@dataclass
class BaseAgent:
    state: AppState
    planner: Planner
    executor: Executor

    def __post_init__(self):
        # Wire model provider to planner if available (Task 17)
        if self.state.model_provider is not None:
            try:
                self.planner.model_provider = self.state.model_provider
            except Exception:
                pass

    def handle(self, raw: str) -> ExecutionResult:
        # Ensure planner has latest provider (in case state provider changed)
        if self.state.model_provider is not None:
            try:
                self.planner.model_provider = self.state.model_provider
            except Exception:
                pass

        plan = self.planner.plan(raw)
        task = Task(raw=raw, action=plan.action, args=plan.args)
        self.state.record("task_created", "success", task.action)
        try:
            self.state.event_bus.emit(Event(name="task.created", payload={"raw": raw, "action": plan.action, "args": plan.args, "confidence": getattr(plan, "confidence", 1.0), "source": getattr(plan, "source", "rule")}))
            self.state.event_bus.emit(Event(name=f"task.{plan.action}.created", payload={"raw": raw}))
        except Exception:
            pass

        result = self.executor.execute(plan)

        self.state.record("task_finished", "success" if result.success else "failed", result.message)
        try:
            self.state.event_bus.emit(
                Event(
                    name="task.finished",
                    payload={"action": plan.action, "success": result.success, "message": result.message},
                )
            )
            self.state.event_bus.emit(Event(name=f"task.{plan.action}.finished", payload={"success": result.success}))
        except Exception:
            pass

        return result
