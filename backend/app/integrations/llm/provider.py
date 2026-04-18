"""LLM Provider abstraction layer

Supports multiple LLM providers with unified interface:
- Ollama (local/remote server)
- Groq (cloud API)
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ...core.config import settings


class LLMProvider(ABC):
    """LLM provider abstract base class"""

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Chat completion"""
        pass

    @abstractmethod
    async def chat_completion_json(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Chat completion with JSON output"""
        pass

    @abstractmethod
    async def chat_completion_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Chat completion with tool use.

        Returns a uniform shape across providers::

            {
                "tool_calls": [{"id": str, "name": str, "args": dict}, ...],
                "content": str | None,
                "finish_reason": "tool_calls" | "stop" | "length",
            }

        ``tools`` follows OpenAI's schema: each item is ``{"type": "function",
        "function": {"name": str, "description": str, "parameters": <JSONSchema>}}``.
        """
        pass


class OllamaProvider(LLMProvider):
    """Ollama provider"""

    def __init__(self, host: str, api_key: str):
        import ollama
        self.client = ollama.AsyncClient(
            host=host,
            headers={'Authorization': f'Bearer {api_key}'} if api_key else None
        )

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> str:
        response = await self.client.chat(
            model=model,
            messages=messages,
            options={
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        )
        return response.get('message', {}).get('content', "")

    async def chat_completion_json(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        response = await self.client.chat(
            model=model,
            messages=messages,
            format='json',
            options={
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        )
        content = response.get('message', {}).get('content', '{}')
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return self._extract_json_block(content)

    def _extract_json_block(self, text: str) -> Dict[str, Any]:
        """Extract JSON block from text"""
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Model response does not contain a valid JSON object.")
        return json.loads(text[start: end + 1])

    async def chat_completion_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Emulate tool-calling via JSON mode for Ollama.

        Ollama models don't return structured ``tool_calls``, so we inline the
        tool catalogue into a system hint and ask for a JSON object shaped like
        ``{"tool_name": "...", "args": {...}}`` or ``{"final_answer": "..."}``.
        """
        rendered = _render_tool_catalogue(tools)
        augmented = [
            {
                "role": "system",
                "content": (
                    "You can call tools. Respond with JSON only, matching one of:\n"
                    '  {"tool_name": "<name>", "args": {<kwargs>}}\n'
                    '  {"final_answer": "<text>"}\n'
                    f"Available tools:\n{rendered}"
                ),
            },
            *messages,
        ]
        obj = await self.chat_completion_json(
            messages=augmented,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return _normalize_ollama_tool_response(obj)


class GroqProvider(LLMProvider):
    """Groq provider"""

    def __init__(self, api_key: str):
        from groq import AsyncGroq
        self.client = AsyncGroq(api_key=api_key)

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> str:
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        response = await self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    async def chat_completion_json(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        response = await self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return self._extract_json_block(content)

    def _extract_json_block(self, text: str) -> Dict[str, Any]:
        """Extract JSON block from text"""
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Model response does not contain a valid JSON object.")
        return json.loads(text[start: end + 1])

    async def chat_completion_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Native Groq tool-calling (OpenAI-compatible)."""
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "tools": tools,
            "tool_choice": "auto",
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message
        raw_tool_calls = getattr(message, "tool_calls", None) or []
        tool_calls = []
        for tc in raw_tool_calls:
            fn = getattr(tc, "function", None)
            name = getattr(fn, "name", None) if fn else None
            arg_str = getattr(fn, "arguments", None) if fn else None
            try:
                args = json.loads(arg_str) if arg_str else {}
            except json.JSONDecodeError:
                args = {}
            if name:
                tool_calls.append({"id": getattr(tc, "id", ""), "name": name, "args": args})
        return {
            "tool_calls": tool_calls,
            "content": message.content,
            "finish_reason": choice.finish_reason or "stop",
        }


# ---------------------------------------------------------------------------
# Ollama tool-use emulation helpers
# ---------------------------------------------------------------------------


def _render_tool_catalogue(tools: List[Dict[str, Any]]) -> str:
    """Pretty-print the OpenAI-style tools list for inclusion in an Ollama prompt."""
    lines: List[str] = []
    for t in tools:
        fn = t.get("function") or {}
        name = fn.get("name", "?")
        desc = fn.get("description", "")
        params = fn.get("parameters") or {}
        lines.append(f"- {name}: {desc}")
        props = (params.get("properties") or {})
        if props:
            for pname, pspec in props.items():
                ptype = pspec.get("type", "any")
                pdesc = pspec.get("description", "")
                lines.append(f"    {pname} ({ptype}): {pdesc}")
    return "\n".join(lines)


def _normalize_ollama_tool_response(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce Ollama JSON-mode output into the uniform tool-calls shape."""
    if isinstance(obj.get("final_answer"), str):
        return {
            "tool_calls": [],
            "content": obj["final_answer"],
            "finish_reason": "stop",
        }
    tool_name = obj.get("tool_name") or obj.get("tool")
    args = obj.get("args") or obj.get("arguments") or {}
    if isinstance(tool_name, str):
        return {
            "tool_calls": [{"id": "ollama_call_0", "name": tool_name, "args": args if isinstance(args, dict) else {}}],
            "content": None,
            "finish_reason": "tool_calls",
        }
    # Nothing we can parse — treat as a plain response.
    return {
        "tool_calls": [],
        "content": json.dumps(obj, ensure_ascii=False),
        "finish_reason": "stop",
    }


# Provider instance cache
_provider_instance: Optional[LLMProvider] = None


def get_provider() -> LLMProvider:
    """Get LLM provider instance (singleton)"""
    global _provider_instance

    if _provider_instance is not None:
        return _provider_instance

    provider_type = settings.LLM_PROVIDER.lower()

    if provider_type == "groq":
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is required for Groq provider")
        _provider_instance = GroqProvider(api_key=settings.GROQ_API_KEY)

    elif provider_type == "ollama":
        _provider_instance = OllamaProvider(
            host=settings.OLLAMA_HOST,
            api_key=settings.OLLAMA_API_KEY
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider_type}")

    return _provider_instance


def get_model_name() -> str:
    """Get default model name for current provider"""
    if settings.LLM_PROVIDER.lower() == "groq":
        return settings.GROQ_MODEL
    return settings.OLLAMA_MODEL
