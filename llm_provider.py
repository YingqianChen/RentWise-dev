"""LLM 提供商抽象层

支持多个 LLM 提供商的统一接口：
- Ollama (本地/远程服务器)
- Groq (云端 API)

使用方法:
    from llm_provider import get_provider

    provider = get_provider()
    response = provider.chat_completion([{"role": "user", "content": "Hello"}])
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class LLMProvider(ABC):
    """LLM 提供商抽象基类"""

    @abstractmethod
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        聊天补全

        Args:
            messages: 消息列表，格式 [{"role": "user/assistant/system", "content": "..."}]
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            模型响应文本
        """
        pass

    @abstractmethod
    def chat_completion_json(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        聊天补全（JSON 格式输出）

        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            解析后的 JSON 字典
        """
        pass


class OllamaProvider(LLMProvider):
    """Ollama 提供商"""

    def __init__(self, host: str, api_key: str):
        from ollama import Client
        self.client = Client(
            host=host,
            headers={'Authorization': f'Bearer {api_key}'}
        )

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> str:
        # Ollama 使用 generate 方法，需要将 messages 转换为 prompt
        prompt = self._messages_to_prompt(messages)
        response = self.client.generate(
            model=model,
            prompt=prompt,
            stream=False,
            options={
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        )
        return response.get('response', "")

    def chat_completion_json(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        prompt = self._messages_to_prompt(messages)
        response = self.client.generate(
            model=model,
            prompt=prompt,
            format='json',
            stream=False,
            options={
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        )
        try:
            return json.loads(response.get('response', '{}'))
        except json.JSONDecodeError:
            return self._extract_json_block(response.get('response', '{}'))

    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """将消息列表转换为单个 prompt（Ollama 兼容）"""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
            else:
                parts.append(f"User: {content}")
        return "\n".join(parts)

    def _extract_json_block(self, text: str) -> Dict[str, Any]:
        """从文本中提取 JSON 块"""
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Model response does not contain a valid JSON object.")
        return json.loads(text[start : end + 1])


class GroqProvider(LLMProvider):
    """Groq 提供商"""

    def __init__(self, api_key: str):
        from groq import Groq
        self.client = Groq(api_key=api_key)

    def chat_completion(
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

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def chat_completion_json(
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

        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return self._extract_json_block(content)

    def _extract_json_block(self, text: str) -> Dict[str, Any]:
        """从文本中提取 JSON 块"""
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Model response does not contain a valid JSON object.")
        return json.loads(text[start : end + 1])


def get_provider(provider_type: str = None, **kwargs) -> LLMProvider:
    """
    获取 LLM 提供商实例

    Args:
        provider_type: 提供商类型 ("ollama" 或 "groq")，默认从环境变量读取
        **kwargs: 提供商特定参数

    Returns:
        LLMProvider 实例
    """
    if provider_type is None:
        provider_type = os.getenv("LLM_PROVIDER", "ollama").lower()

    if provider_type == "groq":
        api_key = kwargs.get("api_key") or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is required for Groq provider")
        return GroqProvider(api_key=api_key)

    elif provider_type == "ollama":
        host = kwargs.get("host") or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        api_key = kwargs.get("api_key") or os.getenv("OLLAMA_API_KEY", "")
        if not api_key:
            raise ValueError("OLLAMA_API_KEY is required for Ollama provider")
        return OllamaProvider(host=host, api_key=api_key)

    else:
        raise ValueError(f"Unknown LLM provider: {provider_type}")
