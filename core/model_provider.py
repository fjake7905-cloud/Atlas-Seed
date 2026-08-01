from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ModelResponse:
    text: str
    model: str
    usage: Dict[str, Any] | None = None
    raw: Any | None = None


class ModelProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, context: Dict[str, Any] | None = None) -> ModelResponse:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class EchoProvider(ModelProvider):
    @property
    def name(self) -> str:
        return "echo"

    def complete(self, prompt: str, context: Dict[str, Any] | None = None) -> ModelResponse:
        ctx = context or {}
        workspace = ctx.get("workspace_files", [])
        memory = ctx.get("recent_memory", [])
        task = ctx.get("task", "")

        if "action" in prompt.lower() and "args" in prompt.lower():
            lower = prompt.lower()
            if "create" in lower and "file" in lower:
                import re

                m = re.search(r"create.*?file.*?([a-zA-Z0-9_\-]+\.py)", prompt, re.I)
                if m:
                    fname = m.group(1)
                    return ModelResponse(
                        text=f'{{"action": "create", "args": ["{fname}"]}}',
                        model=self.name,
                        usage={"echo": True},
                    )

        text = f"[EchoProvider] You asked: {prompt[:200]}\n"
        if task:
            text += f"Task: {task}\n"
        if workspace:
            text += f"Workspace files: {', '.join(workspace[:5])}\n"
        if memory:
            text += f"Recent memory: {len(memory)} items\n"
        text += "Atlas needs a real model for full intelligence. Set OPENAI_API_KEY or use Ollama."
        return ModelResponse(text=text, model=self.name)


class RuleBasedProvider(ModelProvider):
    @property
    def name(self) -> str:
        return "rule-based"

    def complete(self, prompt: str, context: Dict[str, Any] | None = None) -> ModelResponse:
        import re

        ctx = context or {}
        task = ctx.get("task", prompt)
        task_lower = task.lower()

        # Pattern: create file X
        m = re.search(r"create\s+(?:a\s+)?file\s+(?:named\s+)?([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)", task, re.I)
        if m:
            fname = m.group(1)
            return ModelResponse(text=f'{{"action": "create", "args": ["{fname}"]}}', model=self.name)

        # Pattern: write X with Y
        m = re.search(r"write\s+([a-zA-Z0-9_\-./]+)\s+(?:with\s+)?(.+)", task, re.I)
        if m:
            fname = m.group(1)
            content = m.group(2).strip()[:200]
            return ModelResponse(text=f'{{"action": "write", "args": ["{fname}", "{content}"]}}', model=self.name)

        # Pattern: read file X
        m = re.search(r"read\s+([a-zA-Z0-9_\-./]+)", task, re.I)
        if m:
            fname = m.group(1)
            return ModelResponse(text=f'{{"action": "read", "args": ["{fname}"]}}', model=self.name)

        # Pattern: list files - only check task, not full prompt to avoid matching available tools list
        if task_lower in {"ls", "list", "list files", "show files", "list workspace", "list files please"} or (
            "list" in task_lower and "file" in task_lower and len(task_lower) < 30
        ):
            return ModelResponse(text='{"action": "list", "args": []}', model=self.name)

        # Pattern: search for X - only if task starts with search
        if task_lower.startswith("search"):
            m = re.search(r"search\s+(?:for\s+)?(.+)", task, re.I)
            if m:
                query = m.group(1).strip()
                if len(query) > 100:
                    query = query[:100]
                return ModelResponse(text=f'{{"action": "search", "args": ["{query}"]}}', model=self.name)

        # Fallback: chat response
        return ModelResponse(
            text=f"[RuleBased] I understood: {task[:200]}. I can map simple commands to tools, but for complex reasoning need a real LLM.",
            model=self.name,
        )


class OpenAIProvider(ModelProvider):
    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model

    @property
    def name(self) -> str:
        return f"openai:{self.model_name}"

    def complete(self, prompt: str, context: Dict[str, Any] | None = None) -> ModelResponse:
        if not self.api_key:
            return ModelResponse(
                text="OpenAI API key not configured. Set OPENAI_API_KEY env var. Falling back: " + prompt[:200],
                model="openai:missing-key",
            )
        try:
            import json
            import urllib.request

            system_prompt = (
                "You are Atlas autonomous agent. You can call tools by returning JSON: {\"action\": \"tool_name\", \"args\": [\"arg1\", ...]}. "
                "Available tools: create, read, write, append, delete, search, list, run, memory, workspace_create, workspace_list. "
                "If user asks general question, answer in natural language. "
                "If user asks to do file operation, return JSON tool call."
            )
            ctx = context or {}
            if ctx.get("workspace_files"):
                system_prompt += f"\nWorkspace files: {ctx['workspace_files']}"
            if ctx.get("recent_memory"):
                system_prompt += f"\nRecent memory: {ctx['recent_memory'][:3]}"

            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 500,
            }
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                text = body["choices"][0]["message"]["content"]
                usage = body.get("usage")
                return ModelResponse(text=text, model=self.name, usage=usage, raw=body)
        except Exception as e:
            return ModelResponse(text=f"OpenAI provider error: {e}. Prompt was: {prompt[:200]}", model=self.name, usage={"error": str(e)})


class OllamaProvider(ModelProvider):
    def __init__(self, model: str = "llama3", base_url: str = "http://localhost:11434") -> None:
        self.model_name = model
        self.base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return f"ollama:{self.model_name}"

    def complete(self, prompt: str, context: Dict[str, Any] | None = None) -> ModelResponse:
        try:
            import json
            import urllib.request

            ctx = context or {}
            system = "You are Atlas agent. Return JSON tool call {\"action\":..., \"args\":[...]} for file tasks, else natural language."
            full_prompt = f"System: {system}\nContext: {ctx}\nUser: {prompt}\nAssistant:"

            payload = {"model": self.model_name, "prompt": full_prompt, "stream": False}
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                text = body.get("response", "")
                return ModelResponse(text=text, model=self.name, raw=body)
        except Exception as e:
            return ModelResponse(
                text=f"Ollama not reachable at {self.base_url} ({e}). Is Ollama running? Prompt: {prompt[:200]}",
                model=self.name,
                usage={"error": str(e)},
            )


def get_default_provider() -> ModelProvider:
    if os.getenv("OPENAI_API_KEY"):
        return OpenAIProvider()
    if os.getenv("ATLAS_USE_OLLAMA", "").lower() in {"1", "true", "yes"}:
        return OllamaProvider(model=os.getenv("OLLAMA_MODEL", "llama3"))
    return RuleBasedProvider()


def get_provider_by_name(name: str) -> ModelProvider:
    name = name.lower()
    if name.startswith("openai"):
        return OpenAIProvider()
    if name.startswith("ollama"):
        return OllamaProvider()
    if name.startswith("rule"):
        return RuleBasedProvider()
    return EchoProvider()
