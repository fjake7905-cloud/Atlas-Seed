from __future__ import annotations

from dataclasses import dataclass

from agents.base_agent import BaseAgent
from runtime.events import Event


@dataclass
class LoopStep:
    input_text: str
    output_text: str


class AgentLoop:
    def __init__(self, agent: BaseAgent) -> None:
        self.agent = agent

    def step(self, raw: str) -> LoopStep:
        try:
            self.agent.state.event_bus.emit(Event(name="loop.step.started", payload={"input": raw}))
        except Exception:
            pass

        result = self.agent.handle(raw)
        output = result.message
        if result.detail:
            output = f"{output}\n{result.detail}"

        step = LoopStep(input_text=raw, output_text=output)

        try:
            self.agent.state.event_bus.emit(
                Event(name="loop.step.finished", payload={"input": raw, "output": output, "success": result.success})
            )
        except Exception:
            pass

        return step
