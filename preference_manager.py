"""用户偏好管理模块"""

from typing import Optional, List, Tuple

from models import UserPreference, ListingInfo, ListingRecord
from repository import PreferenceRepository


class PreferenceManager:
    """用户偏好管理器"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.repo = PreferenceRepository()

    def get_or_create_preferences(self) -> UserPreference:
        """获取或创建用户偏好"""
        pref = self.repo.get_preference(self.user_id)
        if pref is None:
            pref = UserPreference(user_id=self.user_id)
            self.repo.save_preference(pref)
        return pref

    def update_preferences(
        self,
        max_budget: Optional[float] = None,
        preferred_areas: Optional[List[str]] = None,
        max_commute_time: Optional[int] = None,
        commute_destination: Optional[str] = None,
        must_have: Optional[List[str]] = None,
        deal_breakers: Optional[List[str]] = None
    ) -> UserPreference:
        """更新用户偏好"""
        pref = self.get_or_create_preferences()

        if max_budget is not None:
            pref.max_budget = max_budget
        if preferred_areas is not None:
            pref.preferred_areas = preferred_areas
        if max_commute_time is not None:
            pref.max_commute_time = max_commute_time
        if commute_destination is not None:
            pref.commute_destination = commute_destination
        if must_have is not None:
            pref.must_have = must_have
        if deal_breakers is not None:
            pref.deal_breakers = deal_breakers

        return self.repo.save_preference(pref)

    def calculate_match_score(self, listing: ListingInfo) -> float:
        """
        计算房源与用户偏好的匹配度评分

        返回0-100的分数，越高表示越匹配
        """
        pref = self.get_or_create_preferences()

        if not pref:
            return 50.0  # 默认中等分数

        scores = []
        weights = []

        # 1. 价格匹配度 (权重: 30%)
        if pref.max_budget and listing.monthly_rent not in ["unknown", "", None]:
            price_score = self._calculate_price_score(
                listing.monthly_rent, pref.max_budget
            )
            scores.append(price_score)
            weights.append(0.30)

        # 2. 区域匹配度 (权重: 25%)
        if pref.preferred_areas:
            area_score = self._calculate_area_score(
                listing, pref.preferred_areas
            )
            scores.append(area_score)
            weights.append(0.25)

        # 3. 设施匹配度 (权重: 20%)
        if pref.must_have:
            facility_score = self._calculate_facility_score(
                listing, pref.must_have
            )
            scores.append(facility_score)
            weights.append(0.20)

        # 4. 排除项检查 (权重: 25%)
        if pref.deal_breakers:
            dealbreaker_score = self._calculate_dealbreaker_score(
                listing, pref.deal_breakers
            )
            scores.append(dealbreaker_score)
            weights.append(0.25)

        # 计算加权平均分
        if not scores:
            return 50.0

        total_weight = sum(weights)
        weighted_sum = sum(s * w for s, w in zip(scores, weights))

        return round(weighted_sum / total_weight, 1) if total_weight > 0 else 50.0

    def _calculate_price_score(self, rent_str: str, max_budget: float) -> float:
        """计算价格匹配分数"""
        import re

        # 提取数字
        numbers = re.findall(r'[\d,]+', str(rent_str))
        if not numbers:
            return 50.0

        try:
            rent_value = float(numbers[0].replace(",", ""))

            if rent_value <= max_budget * 0.8:
                return 100.0  # 远低于预算，优秀
            elif rent_value <= max_budget:
                return 80.0   # 在预算内，良好
            elif rent_value <= max_budget * 1.1:
                return 60.0   # 略超预算10%，可接受
            elif rent_value <= max_budget * 1.2:
                return 40.0   # 超预算20%，勉强
            else:
                return 20.0   # 远超预算，不推荐
        except (ValueError, TypeError):
            return 50.0

    def _calculate_area_score(
        self, listing: ListingInfo, preferred_areas: List[str]
    ) -> float:
        """计算区域匹配分数"""
        # 将房源信息转换为文本进行匹配
        listing_text = " ".join([
            str(v) for v in listing.model_dump().values()
            if v and v != "unknown"
        ]).lower()

        matches = 0
        for area in preferred_areas:
            if area.lower() in listing_text:
                matches += 1

        if not preferred_areas:
            return 50.0

        # 匹配比例
        match_ratio = matches / len(preferred_areas)

        if match_ratio >= 1.0:
            return 100.0
        elif match_ratio >= 0.5:
            return 75.0
        elif match_ratio > 0:
            return 50.0
        else:
            return 25.0

    def _calculate_facility_score(
        self, listing: ListingInfo, must_have: List[str]
    ) -> float:
        """计算设施匹配分数"""
        listing_text = str(listing.furnished).lower()

        matches = 0
        for item in must_have:
            if item.lower() in listing_text:
                matches += 1

        if not must_have:
            return 50.0

        match_ratio = matches / len(must_have)
        return match_ratio * 100

    def _calculate_dealbreaker_score(
        self, listing: ListingInfo, deal_breakers: List[str]
    ) -> float:
        """计算排除项分数（触碰排除项扣分）"""
        listing_text = " ".join([
            str(v) for v in listing.model_dump().values()
            if v and v != "unknown"
        ]).lower()

        violations = 0
        for item in deal_breakers:
            if item.lower() in listing_text:
                violations += 1

        if not deal_breakers:
            return 100.0  # 没有排除项，满分

        # 每触碰一个排除项扣50分
        score = 100 - (violations * 50)
        return max(score, 0)  # 不低于0

    def get_preference_warnings(
        self, record: ListingRecord
    ) -> List[Tuple[str, dict]]:
        """
        根据用户偏好生成个性化警告

        返回与用户偏好相关的警告信息列表
        每个警告是 (翻译键, 参数字典) 的元组
        """
        pref = self.get_or_create_preferences()
        warnings = []

        # 价格警告
        if pref.max_budget and record.listing_info.monthly_rent != "unknown":
            import re
            numbers = re.findall(r'[\d,]+', str(record.listing_info.monthly_rent))
            if numbers:
                try:
                    rent = float(numbers[0].replace(",", ""))
                    if rent > pref.max_budget:
                        warnings.append((
                            "budget_exceeded",
                            {"rent": f"{rent:,.0f}", "budget": f"{pref.max_budget:,.0f}"}
                        ))
                    elif rent > pref.max_budget * 0.9:
                        warnings.append((
                            "budget_near_limit",
                            {"rent": f"{rent:,.0f}"}
                        ))
                except (ValueError, TypeError):
                    pass

        # 缺失重要信息警告
        critical_fields = ["deposit", "repair_responsibility"]
        for field in critical_fields:
            if field in record.missing_fields:
                warnings.append(("missing_critical", {"field": field}))

        # 匹配度低警告
        if record.match_score and record.match_score < 50:
            warnings.append(("low_match", {"score": str(record.match_score)}))

        return warnings
