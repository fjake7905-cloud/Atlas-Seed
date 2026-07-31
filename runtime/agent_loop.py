from __future__ import annotations

from dataclasses import dataclass

from agents.base_agent import BaseAgent


@dataclass
class LoopStep:
    input_text: str
    output_text: str


class AgentLoop:
    def __init__(self, agent: BaseAgent) -> None:
        self.agent = agent

    def step(self, raw: str) -> LoopStep:
        result = self.agent.handle(raw)
        output = result.message
        if result.detail:
            output = f"{output}\n{result.detail}"
        return LoopStep(input_text=raw, output_text=output)
