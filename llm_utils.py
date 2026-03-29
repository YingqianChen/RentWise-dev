"""LLM 工具函数

统一的 LLM 调用接口，支持多个提供商：
- Ollama (本地/远程服务器)
- Groq (云端 API)

配置:
    LLM_PROVIDER: 提供商类型 ("ollama" 或 "groq")
    GROQ_API_KEY: Groq API 密钥
    OLLAMA_HOST: Ollama 服务器地址
    OLLAMA_API_KEY: Ollama API 密钥
"""

import json
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 全局提供商实例（延迟初始化）
_provider = None


def _get_provider():
    """获取 LLM 提供商实例（延迟初始化）"""
    global _provider
    if _provider is not None:
        return _provider

    from llm_provider import get_provider
    _provider = get_provider()
    return _provider


def _get_model() -> str:
    """获取默认模型名称"""
    provider_type = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider_type == "groq":
        # Groq 推荐的模型
        return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    else:
        return os.getenv("OLLAMA_MODEL", "llama3.3:is6620")


def _prompt_to_messages(prompt: str, system_prompt: Optional[str] = None) -> list:
    """
    将 prompt 字符串转换为 messages 格式

    Args:
        prompt: 用户输入
        system_prompt: 系统提示词（可选）

    Returns:
        消息列表
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return messages


def chat_completion(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: Optional[int] = None,
    system_prompt: Optional[str] = None,
) -> str:
    """
    聊天补全

    Args:
        prompt: 用户输入
        model: 模型名称（可选，默认使用配置的模型）
        temperature: 温度参数
        max_tokens: 最大 token 数
        system_prompt: 系统提示词（可选）

    Returns:
        模型响应文本
    """
    provider = _get_provider()
    if model is None:
        model = _get_model()

    messages = _prompt_to_messages(prompt, system_prompt)
    return provider.chat_completion(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def chat_completion_json(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    system_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """
    聊天补全（JSON 格式输出）

    Args:
        prompt: 用户输入
        model: 模型名称（可选，默认使用配置的模型）
        temperature: 温度参数
        max_tokens: 最大 token 数
        system_prompt: 系统提示词（可选）

    Returns:
        解析后的 JSON 字典
    """
    provider = _get_provider()
    if model is None:
        model = _get_model()

    messages = _prompt_to_messages(prompt, system_prompt)
    return provider.chat_completion_json(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


# ==================== 兼容旧接口 ====================

def _get_client():
    """
    兼容旧代码的客户端获取函数
    已弃用，请使用 chat_completion 或 chat_completion_json
    """
    import warnings
    warnings.warn(
        "_get_client() is deprecated, use chat_completion() instead",
        DeprecationWarning,
        stacklevel=2
    )
    return _get_provider()


def _extract_json_block(text: str) -> Dict[str, Any]:
    """从文本中提取 JSON 块（兼容旧代码）"""
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
