"""租金分析模块 - 基于市场基准数据

使用香港差饷物业估价署的租金中位数数据，
为用户提供租金合理性分析。

使用场景：
- 有面积时：使用每平米月租基准对比
- 无面积时：使用月租中位数对比
"""

import json
import os
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum
from difflib import SequenceMatcher


class PriceAssessment(Enum):
    """租金评估结果"""
    BELOW_MARKET = "below_market"      # 低于市场价
    NORMAL = "normal"                   # 正常范围
    ABOVE_MARKET = "above_market"       # 高于市场价


@dataclass
class PriceAnalysisResult:
    """租金分析结果"""
    assessment: PriceAssessment
    deviation: float  # 偏离百分比 (-0.5 到 0.5)
    market_range: str  # 市场价格范围描述
    benchmark_value: float  # 基准值
    benchmark_type: str  # 基准类型 (monthly_median 或 per_sqm)
    district: str  # 区域
    reasoning: str  # 分析说明


class RentAnalyzer:
    """租金分析器"""

    # 偏离阈值
    BELOW_THRESHOLD = -0.15  # 低于15%算便宜
    ABOVE_THRESHOLD = 0.15   # 高于15%算贵

    def __init__(self, benchmark_path: str = None, use_rag: bool = True):
        """
        初始化租金分析器

        Args:
            benchmark_path: 基准数据文件路径
            use_rag: 是否使用 RAG 语义搜索（需要向量存储）
        """
        if benchmark_path is None:
            benchmark_path = os.path.join(
                os.path.dirname(__file__),
                "config",
                "rent_benchmarks.json"
            )
        self.benchmarks = self._load_benchmarks(benchmark_path)
        self.area_keywords = self.benchmarks.get("area_keywords", {})
        self.use_rag = use_rag
        self._rag_available = None  # 延迟检查

    def _load_benchmarks(self, path: str) -> Dict:
        """加载基准数据"""
        if not os.path.exists(path):
            print(f"[RentAnalyzer] 基准数据文件不存在: {path}")
            return {"regions": {}, "overall": {}, "area_keywords": {}}

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"[RentAnalyzer] 已加载基准数据，更新时间: {data.get('_meta', {}).get('updated', 'unknown')}")
            return data

    # 模糊匹配阈值 (0-1, 越高越严格)
    FUZZY_THRESHOLD = 0.85

    def _fuzzy_match_keyword(self, word: str, keywords: List[str]) -> Tuple[Optional[str], float]:
        """
        模糊匹配关键词

        Args:
            word: 待匹配的词
            keywords: 关键词列表

        Returns:
            (匹配到的关键词, 相似度分数)，未匹配返回 (None, 0)
        """
        word_lower = word.lower()
        best_match = None
        best_score = 0

        for keyword in keywords:
            keyword_lower = keyword.lower()

            # 完全匹配
            if keyword_lower == word_lower:
                return keyword, 1.0

            # 包含匹配
            if keyword_lower in word_lower or word_lower in keyword_lower:
                score = min(len(keyword_lower), len(word_lower)) / max(len(keyword_lower), len(word_lower))
                if score > best_score:
                    best_match = keyword
                    best_score = score

            # 模糊匹配 (Levenshtein 距离)
            else:
                ratio = SequenceMatcher(None, word_lower, keyword_lower).ratio()
                if ratio > best_score and ratio >= self.FUZZY_THRESHOLD:
                    best_match = keyword
                    best_score = ratio

        return best_match, best_score

    def _check_rag_available(self) -> bool:
        """检查 RAG 是否可用"""
        if self._rag_available is None:
            try:
                from rag_chain import is_rag_available
                self._rag_available = is_rag_available()
                if self._rag_available:
                    print("[RentAnalyzer] RAG 语义搜索已启用")
            except Exception as e:
                print(f"[RentAnalyzer] RAG 不可用: {e}")
                self._rag_available = False
        return self._rag_available

    def detect_district(self, text: str) -> Optional[str]:
        """
        从文本中检测区域

        优先使用 RAG 语义搜索，回退到关键词匹配

        Args:
            text: 房源描述文本

        Returns:
            检测到的区域名称，未检测到返回 None
        """
        if not text:
            return None

        # Step 1: 尝试 RAG 语义搜索
        if self.use_rag and self._check_rag_available():
            try:
                from rag_chain import detect_district_semantic
                result = detect_district_semantic(text)
                if result and result.confidence >= 0.5:
                    print(f"[RentAnalyzer] RAG 匹配: {result.district} (置信度: {result.confidence:.2f})")
                    return result.district
            except Exception as e:
                print(f"[RentAnalyzer] RAG 搜索失败，回退到关键词匹配: {e}")

        # Step 2: 精确匹配（遍历区域关键词）
        text_lower = text.lower()
        for district, keywords in self.area_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return district

        # Step 3: 模糊匹配（对文本中的词进行分词后逐个匹配）
        # 简单分词：按空格和标点分割
        import re
        words = re.split(r'[\s,\.\-_/]+', text)

        best_district = None
        best_score = 0

        for word in words:
            if len(word) < 2:  # 忽略太短的词
                continue

            for district, keywords in self.area_keywords.items():
                matched_keyword, score = self._fuzzy_match_keyword(word, keywords)
                if matched_keyword and score > best_score:
                    best_district = district
                    best_score = score

        return best_district

    def get_benchmark(self, district: str) -> Optional[Dict]:
        """
        获取区域基准数据

        Args:
            district: 区域名称

        Returns:
            基准数据字典，包含 monthly_median 和 per_sqm
        """
        # 在各区域中查找
        for region_name, districts in self.benchmarks.get("regions", {}).items():
            if district in districts:
                return districts[district]

        # 在整体数据中查找
        overall = self.benchmarks.get("overall", {})
        if district in overall:
            return overall[district]

        return None

    def get_region_for_district(self, district: str) -> Optional[str]:
        """获取区域所属的大区域（港岛/九龙/新界）"""
        for region_name, districts in self.benchmarks.get("regions", {}).items():
            if district in districts:
                return region_name
        return None

    def analyze_price(
        self,
        rent: float,
        district: Optional[str] = None,
        area_sqm: Optional[float] = None
    ) -> PriceAnalysisResult:
        """
        分析租金合理性

        Args:
            rent: 月租（港币）
            district: 区域名称（可选）
            area_sqm: 面积平方米（可选）

        Returns:
            PriceAnalysisResult 分析结果
        """
        # 获取基准数据
        benchmark = None
        benchmark_type = "monthly_median"

        if district:
            benchmark = self.get_benchmark(district)

        # 如果找不到区域基准，使用全港基准
        if benchmark is None:
            benchmark = self.benchmarks.get("overall", {}).get("全港", {})
            district = "全港"

        if not benchmark:
            # 无法分析
            return PriceAnalysisResult(
                assessment=PriceAssessment.NORMAL,
                deviation=0.0,
                market_range="无法获取市场数据",
                benchmark_value=0,
                benchmark_type="unknown",
                district=district or "未知",
                reasoning="未找到相关区域的租金基准数据"
            )

        # 计算偏离度
        if area_sqm and area_sqm > 0:
            # 有面积：使用每平米价格对比
            user_per_sqm = rent / area_sqm
            benchmark_per_sqm = benchmark.get("per_sqm", 0)
            if benchmark_per_sqm > 0:
                deviation = (user_per_sqm - benchmark_per_sqm) / benchmark_per_sqm
                benchmark_type = "per_sqm"
                benchmark_value = benchmark_per_sqm
            else:
                # 回退到月租对比
                deviation = (rent - benchmark.get("monthly_median", rent)) / benchmark.get("monthly_median", rent)
                benchmark_type = "monthly_median"
                benchmark_value = benchmark.get("monthly_median", 0)
        else:
            # 无面积：使用月租中位数对比
            median = benchmark.get("monthly_median", 0)
            if median > 0:
                deviation = (rent - median) / median
            else:
                deviation = 0
            benchmark_type = "monthly_median"
            benchmark_value = median

        # 判断评估结果
        if deviation < self.BELOW_THRESHOLD:
            assessment = PriceAssessment.BELOW_MARKET
        elif deviation > self.ABOVE_THRESHOLD:
            assessment = PriceAssessment.ABOVE_MARKET
        else:
            assessment = PriceAssessment.NORMAL

        # 生成市场价格范围描述
        market_range = self._generate_market_range(benchmark, benchmark_type)

        # 生成分析说明
        reasoning = self._generate_reasoning(
            assessment=assessment,
            deviation=deviation,
            district=district,
            benchmark_type=benchmark_type,
            benchmark_value=benchmark_value,
            rent=rent,
            area_sqm=area_sqm
        )

        return PriceAnalysisResult(
            assessment=assessment,
            deviation=deviation,
            market_range=market_range,
            benchmark_value=benchmark_value,
            benchmark_type=benchmark_type,
            district=district,
            reasoning=reasoning
        )

    def _generate_market_range(self, benchmark: Dict, benchmark_type: str) -> str:
        """生成市场价格范围描述"""
        if benchmark_type == "per_sqm":
            per_sqm = benchmark.get("per_sqm", 0)
            low = int(per_sqm * 0.85)
            high = int(per_sqm * 1.15)
            return f"${low}-${high}/平方米"
        else:
            median = benchmark.get("monthly_median", 0)
            low = int(median * 0.85)
            high = int(median * 1.15)
            return f"${low}-${high}/月"

    def _generate_reasoning(
        self,
        assessment: PriceAssessment,
        deviation: float,
        district: str,
        benchmark_type: str,
        benchmark_value: float,
        rent: float,
        area_sqm: Optional[float]
    ) -> str:
        """生成分析说明"""
        deviation_pct = int(deviation * 100)

        if assessment == PriceAssessment.BELOW_MARKET:
            if area_sqm:
                return f"该房源每平米租金比{district}市场中位数低约{-deviation_pct}%，价格较优惠。建议核实房源状况，确认是否有特殊原因。"
            else:
                return f"该房源月租比{district}市场中位数低约{-deviation_pct}%，价格较优惠。建议核实房源状况，确认是否有特殊原因。"

        elif assessment == PriceAssessment.ABOVE_MARKET:
            if area_sqm:
                return f"该房源每平米租金比{district}市场中位数高约{deviation_pct}%，价格偏高。建议与房东协商或对比其他房源。"
            else:
                return f"该房源月租比{district}市场中位数高约{deviation_pct}%，价格偏高。建议与房东协商或对比其他房源。"

        else:
            if area_sqm:
                return f"该房源每平米租金在{district}市场正常范围内，价格合理。"
            else:
                return f"该房源月租在{district}市场正常范围内，价格合理。"


# 模块级别的分析器实例（延迟初始化）
_analyzer: Optional[RentAnalyzer] = None


def get_analyzer() -> RentAnalyzer:
    """获取租金分析器实例（单例）"""
    global _analyzer
    if _analyzer is None:
        _analyzer = RentAnalyzer()
    return _analyzer


def analyze_rent_price(
    rent: float,
    district: Optional[str] = None,
    area_sqm: Optional[float] = None
) -> PriceAnalysisResult:
    """
    便捷函数：分析租金合理性

    Args:
        rent: 月租（港币）
        district: 区域名称（可选）
        area_sqm: 面积平方米（可选）

    Returns:
        PriceAnalysisResult 分析结果
    """
    return get_analyzer().analyze_price(rent, district, area_sqm)


def build_rag_index():
    """
    构建 RAG 向量索引

    运行此函数来创建向量存储，之后 detect_district 将使用语义搜索
    """
    from rent_documents import build_vectorstore, load_benchmarks, create_rent_documents

    print("[RentAnalyzer] 正在构建 RAG 向量索引...")
    documents = create_rent_documents(load_benchmarks())
    build_vectorstore(documents)
    print("[RentAnalyzer] RAG 向量索引构建完成")


def is_rag_ready() -> bool:
    """检查 RAG 向量存储是否已就绪"""
    try:
        from rag_chain import is_rag_available
        return is_rag_available()
    except Exception:
        return False
