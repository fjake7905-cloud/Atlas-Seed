from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, DefaultDict, Any
from collections import defaultdict


@dataclass(frozen=True)
class Event:
    name: str
    payload: dict[str, Any]


class EventBus:
    def __init__(self) -> None:
        self._handlers: DefaultDict[str, list[Callable[[Event], None]]] = defaultdict(list)

    def on(self, event_name: str, handler: Callable[[Event], None]) -> None:
        self._handlers[event_name].append(handler)

    def emit(self, event: Event) -> None:
        for handler in self._handlers.get(event.name, []):
            handler(event)
