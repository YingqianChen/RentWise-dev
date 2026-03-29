"""风险检测模块 - 混合智能方案（规则引擎 + LLM深度分析）"""

from typing import List, Tuple, Optional, Dict, Any
import os
import re
import yaml

from models import ListingInfo, RiskItem
from utils import is_unknown
from llm_analyzer import analyze_deep_risks
from i18n import get_text


# ==================== 配置加载 ====================

def _load_risk_config() -> Dict[str, Any]:
    """从YAML文件加载风险配置"""
    config_path = os.path.join(os.path.dirname(__file__), "config", "risk_rules.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

# 加载配置
_RISK_CONFIG = _load_risk_config()

# 字段风险等级配置 (从YAML加载，如失败则使用默认值)
FIELD_RISK_CONFIG = _RISK_CONFIG.get("field_risks", {
    "deposit": {
        "level": "high",
        "title_key": "risk_deposit_missing",
        "description_key": "risk_deposit_missing_desc",
    },
    "agent_fee": {
        "level": "medium",
        "title_key": "risk_agent_fee_missing",
        "description_key": "risk_agent_fee_missing_desc",
    },
    "management_fee_included": {
        "level": "medium",
        "title_key": "risk_management_fee_unclear",
        "description_key": "risk_management_fee_unclear_desc",
    },
    "rates_included": {
        "level": "medium",
        "title_key": "risk_rates_unclear",
        "description_key": "risk_rates_unclear_desc",
    },
    "repair_responsibility": {
        "level": "medium",
        "title_key": "risk_repair_unclear",
        "description_key": "risk_repair_unclear_desc",
    },
    "move_in_date": {
        "level": "low",
        "title_key": "risk_movein_missing",
        "description_key": "risk_movein_missing_desc",
    },
})

# 数值合理性检查规则 (从YAML加载，如失败则使用默认值)
VALUE_VALIDATION_RULES = _RISK_CONFIG.get("value_validation", {
    "monthly_rent": {
        "pattern": r"^\$?[\d,]+(\.\d{1,2})?$",
        "min": 1000,
        "max": 200000,
        "risk_if_invalid": {
            "level": "medium",
            "title_key": "risk_unusual_rent",
            "description_key": "risk_unusual_rent_desc",
        }
    },
    "deposit": {
        "pattern": r"^\$?[\d,]+(\.\d{1,2})?$|^(one|two|three|\d+)\s*months?$",
        "risk_if_invalid": {
            "level": "medium",
            "title_key": "risk_unclear_deposit",
            "description_key": "risk_unclear_deposit_desc",
        }
    },
})

# 风险等级数值映射
RISK_LEVELS = _RISK_CONFIG.get("risk_levels", {"low": 1, "medium": 2, "high": 3})


# ==================== 规则检测函数 ====================

def detect_missing_fields(info: ListingInfo) -> List[str]:
    """
    检测缺失字段

    Returns:
        缺失字段名称列表
    """
    missing = []
    for field_name, value in info.model_dump().items():
        if is_unknown(str(value)):
            missing.append(field_name)
    return missing


def detect_risks_by_rules(info: ListingInfo, lang: str = None, original_text: str = None) -> List[RiskItem]:
    """
    基于规则检测风险（确定性高的规则）

    Args:
        info: 房源信息
        lang: 语言代码 (en, zh-cn, zh-hk)
        original_text: 原始文本（用于区域检测）

    Returns:
        风险项目列表
    """
    risks: List[RiskItem] = []

    # 基于字段缺失的风险
    for field_name, config in FIELD_RISK_CONFIG.items():
        value = getattr(info, field_name, "unknown")
        if is_unknown(value):
            title = get_text(config["title_key"], lang)
            description = get_text(config["description_key"], lang)
            risks.append(RiskItem(
                level=config["level"],
                title=title,
                description=description,
                source="rule"
            ))

    # 数值异常检查
    risks.extend(_check_value_anomalies(info, lang))

    # 价格风险检测（使用市场基准）
    risks.extend(_check_price_risk(info, lang, original_text))

    return risks


def _check_value_anomalies(info: ListingInfo, lang: str = None) -> List[RiskItem]:
    """检查数值异常"""
    risks = []
    import re

    # 检查异常高的押金（超过3个月租金视为异常）
    if not is_unknown(info.deposit) and not is_unknown(info.monthly_rent):
        deposit_str = info.deposit.lower()
        rent_str = info.monthly_rent.lower().replace("$", "").replace(",", "")

        # 尝试提取租金数值
        try:
            rent_match = re.search(r'\d+', rent_str)
            if rent_match:
                rent_value = int(rent_match.group())

                # 检查押金描述
                if "month" in deposit_str:
                    month_match = re.search(r'(\d+)\s*month', deposit_str)
                    if month_match:
                        months = int(month_match.group(1))
                        if months > 3:
                            title = get_text("risk_excessive_deposit", lang)
                            description = get_text("risk_excessive_deposit_desc", lang).format(months=months)
                            risks.append(RiskItem(
                                level="high",
                                title=title,
                                description=description,
                                source="rule"
                            ))
                        elif months == 1:
                            title = get_text("risk_below_standard_deposit", lang)
                            description = get_text("risk_below_standard_deposit_desc", lang)
                            risks.append(RiskItem(
                                level="low",
                                title=title,
                                description=description,
                                source="rule"
                            ))
        except (ValueError, AttributeError):
            pass

    # 检查管理费说明矛盾
    if not is_unknown(info.management_fee_included):
        mgmt_lower = info.management_fee_included.lower()
        if "not" in mgmt_lower and "included" in mgmt_lower:
            # 明确说不包含，这是正常的明确说明
            pass
        elif "separate" in mgmt_lower or "extra" in mgmt_lower:
            title = get_text("risk_mgmt_separate", lang)
            description = get_text("risk_mgmt_separate_desc", lang)
            risks.append(RiskItem(
                level="low",
                title=title,
                description=description,
                source="rule"
            ))

    return risks


def _check_price_risk(info: ListingInfo, lang: str = None, original_text: str = None) -> List[RiskItem]:
    """
    检查价格风险（基于市场基准数据）

    Args:
        info: 房源信息
        lang: 语言代码
        original_text: 原始文本（用于区域检测）

    Returns:
        风险项目列表
    """
    risks = []

    # 如果没有月租信息，跳过
    if is_unknown(info.monthly_rent):
        return risks

    # 提取月租数值
    try:
        rent_str = info.monthly_rent.lower().replace("$", "").replace("hkd", "").replace(",", "").strip()
        rent_match = re.search(r'[\d.]+', rent_str)
        if not rent_match:
            return risks
        rent_value = float(rent_match.group())

        if rent_value <= 0:
            return risks
    except (ValueError, AttributeError):
        return risks

    # 尝试检测区域
    district = None
    area_sqm = None

    if original_text:
        try:
            from rent_analyzer import get_analyzer
            analyzer = get_analyzer()
            district = analyzer.detect_district(original_text)
        except Exception as e:
            print(f"[PriceRisk] 区域检测失败: {e}")

    # 分析价格
    try:
        from rent_analyzer import analyze_rent_price, PriceAssessment
        result = analyze_rent_price(rent_value, district, area_sqm)

        if result.assessment == PriceAssessment.ABOVE_MARKET:
            # 价格高于市场价
            deviation_pct = int(result.deviation * 100)
            risks.append(RiskItem(
                level="medium",
                title="租金高于市场价",
                description=f"该房源租金比{result.district}市场中位数高约{deviation_pct}%。市场参考价: {result.market_range}。建议与房东协商或对比其他房源。",
                source="rule"
            ))
        elif result.assessment == PriceAssessment.BELOW_MARKET:
            # 价格低于市场价（有利，但需提醒核实）
            deviation_pct = int(abs(result.deviation) * 100)
            risks.append(RiskItem(
                level="low",
                title="租金低于市场价",
                description=f"该房源租金比{result.district}市场中位数低约{deviation_pct}%，价格较优惠。市场参考价: {result.market_range}。建议核实房源状况和租赁条款。",
                source="rule"
            ))
    except Exception as e:
        print(f"[PriceRisk] 价格分析失败: {e}")

    return risks


# ==================== 混合分析函数 ====================

def run_hybrid_analysis(
    info: ListingInfo,
    original_text: str,
    use_llm: bool = True,
    model: str = "llama3.3:is6620",
    lang: str = None
) -> Tuple[List[str], List[RiskItem]]:
    """
    运行混合智能分析（规则 + LLM）

    Args:
        info: 房源信息
        original_text: 原始文本（用于LLM分析和区域检测）
        use_llm: 是否使用LLM深度分析
        model: LLM模型名称
        lang: 语言代码 (en, zh-cn, zh-hk)

    Returns:
        (缺失字段列表, 合并后的风险列表)
    """
    # 1. 规则检测（确定性高）
    missing_fields = detect_missing_fields(info)
    rule_risks = detect_risks_by_rules(info, lang, original_text)

    # 2. LLM深度分析（上下文相关）
    llm_risks = []
    if use_llm and original_text:
        llm_risks = analyze_deep_risks(original_text, info, model, lang)

    # 3. 合并风险列表（去重）
    all_risks = _merge_risks(rule_risks, llm_risks)

    return missing_fields, all_risks


def _merge_risks(rule_risks: List[RiskItem], llm_risks: List[RiskItem]) -> List[RiskItem]:
    """
    合并规则风险和LLM风险，避免重复

    策略：
    - 相同title的风险，保留级别更高的那个
    - 优先保留rule来源的（确定性更高）
    """
    merged = {}

    # 先添加规则风险
    for risk in rule_risks:
        key = risk.title.lower().strip()
        merged[key] = risk

    # 再添加LLM风险（如果title不重复）
    for risk in llm_risks:
        key = risk.title.lower().strip()
        if key not in merged:
            merged[key] = risk
        else:
            # 如果已存在，比较级别，保留更严重的
            existing_level = _risk_level_value(merged[key].level)
            new_level = _risk_level_value(risk.level)
            if new_level > existing_level:
                merged[key] = risk

    return list(merged.values())


def _risk_level_value(level: str) -> int:
    """将风险级别转换为数值，用于比较"""
    return RISK_LEVELS.get(level.lower(), 1)


# ==================== 向后兼容 ====================

def run_rule_checks(info: ListingInfo, lang: str = None) -> Tuple[List[str], List[RiskItem]]:
    """
    原始规则检查函数（向后兼容）

    仅使用规则引擎，不调用LLM
    """
    missing_fields = detect_missing_fields(info)
    risks = detect_risks_by_rules(info, lang)
    return missing_fields, risks
