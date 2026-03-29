"""租金数据向量化脚本

将 rent_benchmarks.json 中的区域数据转换为向量存储，
用于语义搜索和相似度匹配。

使用方法:
    python rent_documents.py --build    # 构建向量索引
    python rent_documents.py --info     # 查看向量存储信息
"""

import json
import os
import argparse
from typing import List, Dict, Any

from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma


def get_project_root() -> str:
    """获取项目根目录"""
    return os.path.dirname(os.path.abspath(__file__))


def get_chroma_path() -> str:
    """获取 ChromaDB 存储路径"""
    return os.path.join(get_project_root(), "chroma_db")


def get_benchmark_path() -> str:
    """获取基准数据文件路径"""
    return os.path.join(get_project_root(), "config", "rent_benchmarks.json")


def load_benchmarks() -> Dict[str, Any]:
    """加载租金基准数据"""
    path = get_benchmark_path()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_rent_documents(benchmarks: Dict[str, Any]) -> List[Document]:
    """
    从基准数据创建文档列表

    每个区域创建一个文档，内容包含：
    - 区域名称（中英文）
    - 租金中位数
    - 每平米价格
    - 相关关键词/地名
    """
    documents = []
    area_keywords = benchmarks.get("area_keywords", {})

    # 遍历所有区域
    for region_name, districts in benchmarks.get("regions", {}).items():
        for district_name, district_data in districts.items():
            # 获取关键词
            keywords = area_keywords.get(district_name, [])

            # 创建文档内容
            content = f"""香港{region_name} - {district_name}
租金中位数: {district_data.get('monthly_median', 'N/A')} 港币/月
每平米租金: {district_data.get('per_sqm', 'N/A')} 港币/平方米
英文名: {district_data.get('name_en', district_name)}
相关地名: {', '.join(keywords[:10])}

这是香港{region_name}的住宅租金参考数据，来源于香港差饷物业估价署。
"""
            # 创建 Document 对象
            doc = Document(
                page_content=content,
                metadata={
                    "district": district_name,
                    "district_en": district_data.get('name_en', district_name),
                    "region": region_name,
                    "monthly_median": district_data.get('monthly_median', 0),
                    "per_sqm": district_data.get('per_sqm', 0),
                    "keywords": keywords,
                    "type": "rent_benchmark"
                }
            )
            documents.append(doc)

    # 添加大区域概览文档
    for region_name, region_data in benchmarks.get("overall", {}).items():
        if region_name == "全港":
            content = f"""香港整体租金概况
月租中位数: {region_data.get('monthly_median', 'N/A')} 港币/月
每平米租金: {region_data.get('per_sqm', 'N/A')} 港币/平方米

这是香港整体的住宅租金参考数据，来源于香港差饷物业估价署。
"""
            doc = Document(
                page_content=content,
                metadata={
                    "district": region_name,
                    "district_en": "Hong Kong Overall",
                    "region": "全港",
                    "monthly_median": region_data.get('monthly_median', 0),
                    "per_sqm": region_data.get('per_sqm', 0),
                    "keywords": [],
                    "type": "rent_benchmark"
                }
            )
            documents.append(doc)

    print(f"[rent_documents] 创建 {len(documents)} 个文档")
    return documents


def get_embeddings():
    """获取嵌入模型"""
    return OllamaEmbeddings(model="nomic-embed-text")


def build_vectorstore(documents: List[Document] = None, persist: bool = True) -> Chroma:
    """
    构建向量存储

    Args:
        documents: 文档列表，如果为 None 则自动创建
        persist: 是否持久化到磁盘
    """
    if documents is None:
        benchmarks = load_benchmarks()
        documents = create_rent_documents(benchmarks)

    embeddings = get_embeddings()
    persist_directory = get_chroma_path() if persist else None

    # 创建向量存储
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=persist_directory
    )

    print(f"[rent_documents] 向量存储已构建，持久化到: {persist_directory}")
    return vectorstore


def load_vectorstore() -> Chroma:
    """加载已有的向量存储"""
    persist_directory = get_chroma_path()
    embeddings = get_embeddings()

    return Chroma(
        persist_directory=persist_directory,
        embedding_function=embeddings
    )


def get_vectorstore_info() -> Dict[str, Any]:
    """获取向量存储信息"""
    try:
        vectorstore = load_vectorstore()
        # 获取集合信息
        collection = vectorstore._collection
        count = collection.count()

        return {
            "path": get_chroma_path(),
            "document_count": count,
            "status": "ok"
        }
    except Exception as e:
        return {
            "path": get_chroma_path(),
            "document_count": 0,
            "status": f"error: {str(e)}"
        }


def main():
    parser = argparse.ArgumentParser(description="租金数据向量化工具")
    parser.add_argument("--build", action="store_true", help="构建向量索引")
    parser.add_argument("--info", action="store_true", help="查看向量存储信息")

    args = parser.parse_args()

    if args.build:
        print("正在构建向量索引...")
        documents = create_rent_documents(load_benchmarks())
        build_vectorstore(documents)
        print("完成！")

    elif args.info:
        info = get_vectorstore_info()
        print(f"向量存储路径: {info['path']}")
        print(f"文档数量: {info['document_count']}")
        print(f"状态: {info['status']}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
