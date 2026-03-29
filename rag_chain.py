"""RAG向量检索模块

提供语义搜索能力，用于：
1. 从用户输入中检测区域
2. 获取相关区域的租金基准数据

使用向量相似度搜索替代简单的关键词匹配。
"""

import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from langchain_core.documents import Document

# 延迟导入，避免在未安装依赖时报错
_vectorstore = None
_embeddings = None


def get_chroma_path() -> str:
    """获取 ChromaDB 存储路径"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")


def get_embeddings():
    """获取嵌入模型（延迟初始化）"""
    global _embeddings
    if _embeddings is None:
        from langchain_ollama import OllamaEmbeddings
        _embeddings = OllamaEmbeddings(model="nomic-embed-text")
    return _embeddings


def get_vectorstore():
    """获取向量存储（延迟初始化）"""
    global _vectorstore
    if _vectorstore is None:
        from langchain_chroma import Chroma
        chroma_path = get_chroma_path()
        if not os.path.exists(chroma_path):
            raise FileNotFoundError(
                f"向量存储不存在: {chroma_path}\n"
                "请先运行: python rent_documents.py --build"
            )
        _vectorstore = Chroma(
            persist_directory=chroma_path,
            embedding_function=get_embeddings()
        )
    return _vectorstore


def is_rag_available() -> bool:
    """检查 RAG 是否可用"""
    try:
        get_vectorstore()
        return True
    except Exception:
        return False


@dataclass
class DistrictMatch:
    """区域匹配结果"""
    district: str           # 区域名称（中文）
    district_en: str        # 区域名称（英文）
    region: str             # 大区域（港岛/九龙/新界）
    confidence: float       # 匹配置信度 (0-1)
    monthly_median: int     # 月租中位数
    per_sqm: int           # 每平米租金
    keywords: List[str]     # 相关关键词


def detect_district_semantic(text: str, k: int = 3) -> Optional[DistrictMatch]:
    """
    使用语义搜索检测区域

    Args:
        text: 用户输入的房源描述
        k: 返回的候选数量

    Returns:
        最匹配的区域，未找到返回 None
    """
    try:
        vectorstore = get_vectorstore()

        # 执行相似度搜索
        results = vectorstore.similarity_search_with_score(text, k=k)

        if not results:
            return None

        # 取最匹配的结果
        best_doc, best_score = results[0]
        metadata = best_doc.metadata

        # Chroma 返回的是距离，越小越相似
        # 转换为置信度 (假设距离范围 0-2)
        confidence = max(0, 1 - best_score / 2)

        # 过滤低置信度结果
        if confidence < 0.3:
            return None

        return DistrictMatch(
            district=metadata.get("district", ""),
            district_en=metadata.get("district_en", ""),
            region=metadata.get("region", ""),
            confidence=confidence,
            monthly_median=metadata.get("monthly_median", 0),
            per_sqm=metadata.get("per_sqm", 0),
            keywords=metadata.get("keywords", [])
        )

    except Exception as e:
        print(f"[rag_chain] 语义搜索失败: {e}")
        return None


def get_rent_benchmark(query: str, k: int = 3) -> List[Dict[str, Any]]:
    """
    根据查询获取租金基准数据

    Args:
        query: 查询文本（可以是区域名、地名或描述）
        k: 返回结果数量

    Returns:
        匹配的区域数据列表
    """
    try:
        vectorstore = get_vectorstore()
        results = vectorstore.similarity_search_with_score(query, k=k)

        output = []
        for doc, score in results:
            metadata = doc.metadata
            confidence = max(0, 1 - score / 2)

            output.append({
                "district": metadata.get("district", ""),
                "district_en": metadata.get("district_en", ""),
                "region": metadata.get("region", ""),
                "monthly_median": metadata.get("monthly_median", 0),
                "per_sqm": metadata.get("per_sqm", 0),
                "confidence": confidence,
                "keywords": metadata.get("keywords", []),
                "content": doc.page_content
            })

        return output

    except Exception as e:
        print(f"[rag_chain] 获取租金基准失败: {e}")
        return []


def search_by_district(district: str) -> Optional[Dict[str, Any]]:
    """
    精确搜索区域数据

    Args:
        district: 区域名称（中文或英文）

    Returns:
        区域数据字典
    """
    results = get_rent_benchmark(district, k=1)

    if results:
        return results[0]

    return None


class RAGChain:
    """RAG检索链"""

    def __init__(self):
        self._vectorstore = None

    @property
    def vectorstore(self):
        if self._vectorstore is None:
            self._vectorstore = get_vectorstore()
        return self._vectorstore

    def detect_district(self, text: str) -> Optional[DistrictMatch]:
        """检测区域"""
        return detect_district_semantic(text)

    def get_benchmark(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """获取租金基准"""
        return get_rent_benchmark(query, k)

    def is_available(self) -> bool:
        """检查是否可用"""
        return is_rag_available()


# 模块级别的实例（延迟初始化）
_rag_chain: Optional[RAGChain] = None


def get_rag_chain() -> RAGChain:
    """获取 RAG 链实例（单例）"""
    global _rag_chain
    if _rag_chain is None:
        _rag_chain = RAGChain()
    return _rag_chain
