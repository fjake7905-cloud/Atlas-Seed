from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def build_context(
    workspace: Path,
    memory_items: List[Dict[str, Any]],
    task: str,
    max_files: int = 20,
    max_memory: int = 10,
) -> Dict[str, Any]:
    """Build context dict for model provider from workspace + memory + task"""

    # Workspace files listing
    workspace_files: List[str] = []
    try:
        if workspace.exists():
            for item in sorted(workspace.iterdir()):
                suffix = "/" if item.is_dir() else ""
                workspace_files.append(f"{item.name}{suffix}")
                if len(workspace_files) >= max_files:
                    break
    except Exception:
        pass

    # Recent memory
    recent_memory: List[str] = []
    try:
        for entry in memory_items[-max_memory:]:
            action = entry.get("action", "unknown")
            status = entry.get("status", "")
            detail = entry.get("detail", "")[:100]
            recent_memory.append(f"{action}:{status} - {detail}")
    except Exception:
        pass

    # Stats
    try:
        from runtime.memory import PersistentMemory

        # We don't have direct access to stats here, but we can compute simple
        total_mem = len(memory_items)
    except Exception:
        total_mem = len(memory_items)

    return {
        "workspace_path": str(workspace),
        "workspace_files": workspace_files,
        "recent_memory": recent_memory,
        "memory_total": total_mem,
        "task": task,
    }


def build_prompt_with_context(task: str, context: Dict[str, Any]) -> str:
    """Build a prompt string that includes context for LLM"""
    lines = [
        f"Task: {task}",
        f"Workspace: {context.get('workspace_path')} - Files: {', '.join(context.get('workspace_files', [])[:10])}",
        f"Memory total: {context.get('memory_total')} recent: {len(context.get('recent_memory', []))}",
    ]
    if context.get("recent_memory"):
        lines.append("Recent memory:")
        for mem in context["recent_memory"][-5:]:
            lines.append(f"  - {mem}")

    lines.append("\nInstructions:")
    lines.append("- If user wants file operation, return JSON: {\"action\": \"tool\", \"args\": [...]}")
    lines.append("- Available tools: create, read, write, append, delete, search, list, run, memory, workspace_create, workspace_list")
    lines.append("- Else answer in natural language")
    lines.append(f"\nUser request: {task}")

    return "\n".join(lines)
