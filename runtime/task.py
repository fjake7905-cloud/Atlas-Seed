from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Task:
    raw: str
    action: str
    args: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
