from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any


@dataclass(frozen=True)
class Capability:
    name: str
    description: str
    handler: Callable[..., Any] | None = None
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


class CapabilityRegistry:
    """Registry for tool capabilities, including confirmation requirements"""

    def __init__(self) -> None:
        self._caps: dict[str, Capability] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        # Safe operations - no confirmation needed
        self.register(Capability("create", "Create an empty file", needs_confirmation=False))
        self.register(Capability("read", "Read a file", needs_confirmation=False))
        self.register(Capability("list", "List workspace files", needs_confirmation=False))
        self.register(Capability("workspace_show", "Show workspace", needs_confirmation=False))
        self.register(Capability("workspace_create", "Create workspace folder", needs_confirmation=False))
        self.register(Capability("memory", "Show memory", needs_confirmation=False))

        # Destructive operations - need confirmation in interactive mode
        self.register(Capability("write", "Write to a file (overwrites)", needs_confirmation=True))
        self.register(Capability("run", "Run a Python file (arbitrary code)", needs_confirmation=True))
        self.register(Capability("delete", "Delete a file (future)", needs_confirmation=True))
        self.register(Capability("workspace_delete", "Delete workspace (future)", needs_confirmation=True))

    def register(self, cap: Capability) -> None:
        self._caps[cap.name] = cap

    def get(self, name: str) -> Capability | None:
        return self._caps.get(name)

    def needs_confirmation(self, name: str) -> bool:
        cap = self.get(name)
        return cap.needs_confirmation if cap else False

    def list(self) -> list[str]:
        return sorted(self._caps)

    def list_dangerous(self) -> list[str]:
        return [name for name, cap in self._caps.items() if cap.needs_confirmation]
