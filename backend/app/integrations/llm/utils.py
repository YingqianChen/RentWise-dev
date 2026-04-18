"""LLM utility functions"""

from typing import Any, Dict, List, Optional

from .provider import get_provider, get_model_name


async def chat_completion(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: Optional[int] = None,
    system_prompt: Optional[str] = None,
) -> str:
    """Simple chat completion with a prompt string"""
    provider = get_provider()
    if model is None:
        model = get_model_name()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    return await provider.chat_completion(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def chat_completion_json(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    system_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Chat completion with JSON output"""
    provider = get_provider()
    if model is None:
        model = get_model_name()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    return await provider.chat_completion_json(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def chat_with_messages(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: Optional[int] = None,
) -> str:
    """Chat completion with message list"""
    provider = get_provider()
    if model is None:
        model = get_model_name()

    return await provider.chat_completion(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def chat_completion_tools(
    messages: List[Dict[str, str]],
    tools: List[Dict[str, Any]],
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """Chat completion with tool use. See ``LLMProvider.chat_completion_tools``."""
    provider = get_provider()
    if model is None:
        model = get_model_name()

    return await provider.chat_completion_tools(
        messages=messages,
        tools=tools,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
