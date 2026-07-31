from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any


@dataclass(frozen=True)
class Capability:
    name: str
    description: str
    handler: Callable[..., Any]
    needs_confirmation: bool = False


@dataclass(frozen=True)
class CapabilityResult:
    success: bool
    message: str
    detail: str = ""


def resolve_path(workspace: Path, target: str) -> Path:
    path = (workspace / target).resolve()
    workspace_resolved = workspace.resolve()
    if workspace_resolved not in path.parents and path != workspace_resolved:
        raise ValueError("Path escapes workspace")
    return path
