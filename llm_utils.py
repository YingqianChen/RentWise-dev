import json
import os
from typing import Any, Dict, Optional
from ollama import Client
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def _get_client() -> Client:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    api_key = os.getenv("OLLAMA_API_KEY", "")
    
    if not api_key:
        raise RuntimeError("API Key (Bearer token) is not set.")
    
    # 初始化 Ollama 客户端
    return Client(
        host=host,
        headers={'Authorization': f'Bearer {api_key}'}
    )

def _extract_json_block(text: str) -> Dict[str, Any]:
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

def chat_completion(
    prompt: str,
    model: str,
    temperature: float = 0.1,
    max_tokens: Optional[int] = None,
) -> str:
    client = _get_client()
    
    response = client.generate(
        model=model,
        prompt=prompt,
        stream=False,
        options={
            "temperature": temperature,
            "num_predict": max_tokens,
        }
    )
    # Ollama 返回的是字典，内容在 'response' 字段中
    return response.get('response', "")


def chat_completion_json(
    prompt: str,
    model: str,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    client = _get_client()
    
    # 使用 Ollama 的 format='json' 强制输出 JSON
    response = client.generate(
        model=model,
        prompt=prompt,
        format='json', # 核心修改
        stream=False,
        options={
            "temperature": temperature,
            "num_predict": max_tokens,
        }
    )
    
    try:
        return json.loads(response.get('response', '{}'))
    except json.JSONDecodeError:
        # 如果模型输出还是带了 markdown 代码块，尝试手动提取
        return _extract_json_block(response.get('response', '{}'))