"""RentWise - Hong Kong Rental Decision Assistant

Enhanced version with:
- User authentication
- Hybrid risk analysis (Rules + LLM)
- User preferences and match scoring
- Listing persistence
"""

from typing import Dict, List, Tuple, Optional
import streamlit as st
import pandas as pd

# 配置验证（必须在其他模块之前导入）
try:
    from config import settings
except Exception as e:
    st.set_page_config(page_title="RentWise - 配置错误", layout="wide")
    st.error(f"⚠️ 配置错误: {e}")
    st.info("""
    **解决方案:**

    1. 复制 `.env.example` 为 `.env`:
       ```
       cp .env.example .env
       ```

    2. 编辑 `.env` 文件，设置必要配置:
       ```
       SECRET_KEY=your-secret-key-at-least-16-characters
       DATABASE_URL=sqlite:///./rentwise.db
       ```

    3. 重新启动应用
    """)
    st.stop()

# 初始化数据库
from database import init_db
init_db()

from auth import StreamlitAuthManager, init_auth
from comparer import compare_listings, summarize_comparison
from extractor import extract_listing_info, generate_follow_up_questions, generate_listing_name
from models import AnalysisResult, ListingRecord
from ocr_utils import extract_text_from_image_bytes
from rules import run_hybrid_analysis, run_rule_checks
from utils import build_combined_text
from preference_manager import PreferenceManager
from repository import ListingRepository
from i18n import t, get_language
from onboarding import is_first_visit, show_welcome_dialog, render_progress_indicator, get_preference_hint

# 初始化认证
init_auth()


def analyze_listing(
    text_inputs: Dict[str, str],
    image_files: List,
    model_name: str,
    lang: str = None,
) -> AnalysisResult:
    """分析房源（使用混合智能）"""
    ocr_texts: List[str] = []
    for image_file in image_files:
        if image_file is None:
            continue
        image_bytes = image_file.getvalue()
        ocr_text = extract_text_from_image_bytes(image_bytes)
        if ocr_text:
            ocr_texts.append(ocr_text)

    combined_text = build_combined_text(text_inputs, ocr_texts)
    if not combined_text.strip():
        raise ValueError("Please provide at least one text input or image.")

    listing_info = extract_listing_info(combined_text, model=model_name)

    # 使用混合智能分析（规则 + LLM）
    missing_fields, risks = run_hybrid_analysis(
        listing_info, combined_text, use_llm=True, model=model_name, lang=lang
    )

    suggested_questions = generate_follow_up_questions(
        missing_fields=missing_fields, risks=risks, model=model_name, lang=lang
    )

    return AnalysisResult(
        listing_info=listing_info,
        missing_fields=missing_fields,
        risks=risks,
        suggested_questions=suggested_questions,
        combined_text=combined_text,
        ocr_texts=ocr_texts,
    )


def render_analysis(
    title: str,
    result: AnalysisResult,
    show_save: bool = True,
    user_id: Optional[str] = None,
    model_name: str = "llama3.3:is6620"
) -> None:
    """渲染分析结果 - 渐进式加载版本"""
    import time

    st.subheader(title)

    # 显示匹配度评分（如果已计算）
    if result.match_score is not None:
        score = result.match_score
        if score >= 80:
            st.success(f"✨ {t('match_score')}: {score}% - {t('highly_recommended')}")
        elif score >= 60:
            st.info(f"👍 {t('match_score')}: {score}% - {t('good_match')}")
        elif score >= 40:
            st.warning(f"⚠️ {t('match_score')}: {score}% - {t('moderate_match')}")
        else:
            st.error(f"❌ {t('match_score')}: {score}% - {t('poor_match')}")

    # 创建标签页进行渐进式展示
    tab1, tab2, tab3, tab4 = st.tabs([
        f"📋 {t('structured_summary')}",
        f"❓ {t('missing_info')}",
        f"⚠️ {t('risk_alerts')}",
        f"💬 {t('suggested_questions')}"
    ])

    # Tab 1: 结构化摘要
    with tab1:
        field_mapping = {
            t("monthly_rent"): result.listing_info.monthly_rent,
            t("deposit"): result.listing_info.deposit,
            t("agent_fee"): result.listing_info.agent_fee,
            t("management_fee"): result.listing_info.management_fee_included,
            t("rates_included"): result.listing_info.rates_included,
            t("lease_term"): result.listing_info.lease_term,
            t("move_in_date"): result.listing_info.move_in_date,
            t("furnished_label"): result.listing_info.furnished,
            t("repair_responsibility_label"): result.listing_info.repair_responsibility,
        }
        df = pd.DataFrame({
            "字段": list(field_mapping.keys()),
            "值": list(field_mapping.values())
        })
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Tab 2: 缺失重要信息
    with tab2:
        if result.missing_fields:
            field_name_map = {
                "monthly_rent": t("monthly_rent"),
                "deposit": t("deposit"),
                "agent_fee": t("agent_fee"),
                "management_fee_included": t("management_fee"),
                "rates_included": t("rates_included"),
                "lease_term": t("lease_term"),
                "move_in_date": t("move_in_date"),
                "furnished": t("furnished_label"),
                "repair_responsibility": t("repair_responsibility_label"),
            }
            st.warning(f"📋 {len(result.missing_fields)} {t('missing_fields')}")
            for field in result.missing_fields:
                translated_name = field_name_map.get(field, field)
                st.markdown(f"- ❓ **{translated_name}**")
        else:
            st.success(f"✅ {t('no_missing')}")

    # Tab 3: 风险提醒
    with tab3:
        if result.risks:
            # 统计风险数量
            high_count = len([r for r in result.risks if r.level == "high"])
            medium_count = len([r for r in result.risks if r.level == "medium"])
            low_count = len([r for r in result.risks if r.level == "low"])

            # 风险概览
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(f"🔴 {t('high_risk')}", high_count)
            with col2:
                st.metric(f"🟡 {t('medium_risk')}", medium_count)
            with col3:
                st.metric(f"🔵 {t('low_risk')}", low_count)

            st.markdown("---")

            # 高风险详情
            if high_count > 0:
                st.markdown(f"### 🔴 {t('high_risk')}")
                for risk in [r for r in result.risks if r.level == "high"]:
                    source_tag = "🤖 AI" if risk.source == "llm" else "📋 Rule"
                    with st.container(border=True):
                        st.markdown(f"**{risk.title}**")
                        st.caption(f"{source_tag} | {risk.description}")

            # 中风险详情
            if medium_count > 0:
                st.markdown(f"### 🟡 {t('medium_risk')}")
                for risk in [r for r in result.risks if r.level == "medium"]:
                    source_tag = "🤖 AI" if risk.source == "llm" else "📋 Rule"
                    with st.container(border=True):
                        st.markdown(f"**{risk.title}**")
                        st.caption(f"{source_tag} | {risk.description}")

            # 低风险详情
            if low_count > 0:
                st.markdown(f"### 🔵 {t('low_risk')}")
                for risk in [r for r in result.risks if r.level == "low"]:
                    source_tag = "🤖 AI" if risk.source == "llm" else "📋 Rule"
                    with st.container(border=True):
                        st.markdown(f"**{risk.title}**")
                        st.caption(f"{source_tag} | {risk.description}")
        else:
            st.success(f"✅ {t('no_risks')}")

    # Tab 4: 建议跟进问题
    with tab4:
        if result.suggested_questions:
            st.info(f"💬 {len(result.suggested_questions)} {t('suggested_questions')}")
            for idx, question in enumerate(result.suggested_questions, start=1):
                st.markdown(f"**{idx}.** {question}")
        else:
            st.info(t("no_questions"))

        # 个性化警告（基于用户偏好）
        if user_id:
            st.markdown("---")
            st.markdown(f"**{t('personalized_alerts')}**")
            pm = PreferenceManager(user_id)
            record = ListingRecord(
                user_id=user_id,
                name="temp",
                listing_info=result.listing_info,
                missing_fields=result.missing_fields,
                risks=result.risks,
                suggested_questions=result.suggested_questions,
                match_score=result.match_score,
            )
            warnings = pm.get_preference_warnings(record)
            if warnings:
                for warning_key, params in warnings:
                    warning_text = t(warning_key)
                    for key, value in params.items():
                        warning_text = warning_text.replace(f"${{{key}}}", value)
                        warning_text = warning_text.replace(f"{{{key}}}", value)
                    st.warning(f"⚠️ {warning_text}")
            else:
                st.success(f"✅ {t('no_risks')}")

    # 保存按钮
    if show_save and user_id:
        st.markdown("---")
        with st.container(border=True):
            st.markdown(f"**💾 Save This Listing**")
            col1, col2 = st.columns([3, 1])
            with col1:
                # 使用唯一标识符避免缓存问题
                import uuid
                unique_id = str(uuid.uuid4())[:8]
                default_name = generate_listing_name(
                    result.listing_info,
                    result.combined_text or "",
                    model=model_name
                )
                listing_name = st.text_input(
                    t("listing_name"),
                    value=default_name,
                    key=f"save_name_{unique_id}"
                )
            with col2:
                st.write("")
                st.write("")
                if st.button(f"💾 {t('save')}", key=f"btn_save_{unique_id}", type="primary"):
                    repo = ListingRepository()
                    record = ListingRecord(
                        user_id=user_id,
                        name=listing_name,
                        listing_info=result.listing_info,
                        missing_fields=result.missing_fields,
                        risks=result.risks,
                        suggested_questions=result.suggested_questions,
                        match_score=result.match_score,
                        combined_text=result.combined_text,
                    )
                    try:
                        saved = repo.create_listing(record)
                        st.success(f"{t('save_success')}: '{saved.name}'")
                        st.rerun()
                    except Exception as e:
                        st.error(f"{t('save_fail')}: {e}")

    st.markdown(f"**{t('ocr_text')}**")
    if result.ocr_texts:
        with st.expander(f"📄 {t('ocr_text')} ({len(result.ocr_texts)} pages)", expanded=False):
            for idx, text in enumerate(result.ocr_texts, start=1):
                st.text_area(f"OCR Text {idx}", text, height=120, disabled=True, key=f"ocr_{idx}_{title}")
    else:
        st.caption(t("ocr_no_text"))


def listing_input_block(prefix: str) -> Tuple[Dict[str, str], List]:
    """房源输入模块 - 清爽版（默认空，可选加载示例）"""
    examples = {
        "Single_Listing_A": {
            "listing_text": (
                "【港岛·西营盘】两房一厅，实用面积450呎，月租$22,000（包差饷、管理费），两个月租金，佣金：半个月租金，一年生约一年死约，可提前两个月解约。起租日期：2025年5月1日，可商议。基本家电（冷气、炉头、热水炉），不包床和衣柜。小修由租客负责，大修由业主负责"
            ),
            "chat_text": (
                "Agent: 单位新装修，有露台，高层开扬。业主愿意提供3天免租期作装修期。"
                "租客: 管理费已包，那差饷呢？Agent: 差饷业主交。"
            ),
            "note_text": (
                "查看时发现厨房抽气扇有点旧，业主答应交楼前更换。另外大厦有24小时保安，可养猫。"
            )
        },
        "Compare_Listing_A": {
            "listing_text": (
                "【九龙·黄埔】三房两厅，实用面积680呎，月租$28,000，按金：两个月租金，管理费租客自付（约$2,000/月）。租期两年固定期，无生约，起租：2025年6月1日。全屋定制家具，包电器（雪柜、洗衣机、电视）"
            ),
            "chat_text": (
                "Agent: 单位新装，业主移民放盘。管理费每月$1,800，租客直接交管理公司。"
                "租客: 可唔可以再平？Agent: 业主已减至$28,000，底价了。"
            ),
            "note_text": (
                "天台使用权只给顶楼单位，此单位不包天台。附近有黄埔天地，购物方便。"
            )
        },
        "Compare_Listing_B": {
            "listing_text": (
                "【新界·沙田】两房一厅，实用面积510呎，月租$18,500（全包），按金为两个月租金，管理费：已包在租金内，一年生约一年死约，5月15日起租，空房，只包冷气及热水炉。业主负责固定装置维修"
            ),
            "chat_text": (
                "Agent: 近大学站，步行5分钟。可即日睇楼。租客: 按金可否分期付？"
                "Agent: 需一次付清，但业主可提供14天免租期作装修用。"
            ),
            "note_text": (
                "单位向东南，安静。大厦有会所（泳池、健身室），住客需另付会费。"
            )
        }
    }

    default = examples.get(prefix, {})

    st.markdown(f"### {t('inputs_heading')}")

    # 示例加载按钮
    if st.button("📝 加载示例文本", key=f"load_example_{prefix}", help="点击加载示例房源信息"):
        st.session_state[f"{prefix}_listing_text"] = default.get("listing_text", "")
        st.session_state[f"{prefix}_chat_text"] = default.get("chat_text", "")
        st.session_state[f"{prefix}_note_text"] = default.get("note_text", "")
        st.rerun()

    listing_text = st.text_area(
        t("listing_text"),
        key=f"{prefix}_listing_text",
        height=120,
        placeholder="粘贴房源信息，例如：月租$15000，押金两个月，旺角两房..."
    )
    chat_text = st.text_area(
        t("chat_text"),
        key=f"{prefix}_chat_text",
        height=120,
        placeholder="可选：粘贴与中介的聊天记录..."
    )
    note_text = st.text_area(
        t("note_text"),
        key=f"{prefix}_note_text",
        height=100,
        placeholder="可选：添加个人备注..."
    )

    text_files = st.file_uploader(
        t("upload_text"),
        type=["txt"],
        accept_multiple_files=True,
        key=f"{prefix}_txt_files",
    )

    image_files = st.file_uploader(
        t("upload_images"),
        type=["png", "jpg", "jpeg", "webp", "bmp"],
        accept_multiple_files=True,
        key=f"{prefix}_images",
    )

    uploaded_text = []
    for text_file in text_files or []:
        try:
            uploaded_text.append(text_file.getvalue().decode("utf-8", errors="ignore"))
        except Exception:
            continue
    uploaded_text_combined = "\n".join([txt for txt in uploaded_text if txt.strip()])

    text_inputs = {
        "listing_text": listing_text,
        "chat_text": chat_text,
        "note_text": note_text,
        "uploaded_text_files": uploaded_text_combined,
    }
    return text_inputs, image_files


def render_preferences(user_id: str) -> None:
    """渲染用户偏好设置界面 - 引导式版本"""
    st.subheader(t("preferences"))

    pm = PreferenceManager(user_id)
    pref = pm.get_or_create_preferences()

    # 使用步骤式引导设置
    step1, step2, step3 = st.tabs([
        "💰 Step 1: Budget",
        "📍 Step 2: Location",
        "🏠 Step 3: Requirements"
    ])

    # Step 1: 预算设置
    with step1:
        st.markdown("### 💰 Set Your Budget")
        st.markdown("Define your maximum monthly rent budget in HKD.")

        max_budget = st.slider(
            t("max_budget"),
            min_value=5000,
            max_value=100000,
            value=int(pref.max_budget) if pref.max_budget else 20000,
            step=1000,
            format="HKD $%d"
        )

        # 显示预算范围提示
        if max_budget < 10000:
            st.info("💡 Budget under $10,000: Consider shared flats or older buildings in outer districts.")
        elif max_budget < 20000:
            st.info("💡 Budget $10,000-$20,000: Suitable for small flats in most areas or larger flats in outer districts.")
        elif max_budget < 35000:
            st.info("💡 Budget $20,000-$35,000: Good range for 1-2 bedroom flats in popular areas.")
        else:
            st.info("💡 Budget $35,000+: Premium options available in most districts.")

    # Step 2: 区域设置
    with step2:
        st.markdown("### 📍 Preferred Locations")
        st.markdown("Enter areas you'd like to live in (one per line).")

        # 常见香港区域快速选择
        common_areas = {
            "en": ["Mong Kok", "Causeway Bay", "Central", "Wan Chai", "Tsim Sha Tsui",
                   "Sham Shui Po", "Kwun Tong", "Sha Tin", "Tsuen Wan", "Tuen Mun"],
            "zh-cn": ["旺角", "铜锣湾", "中环", "湾仔", "尖沙咀",
                      "深水埗", "观塘", "沙田", "荃湾", "屯门"],
            "zh-hk": ["旺角", "銅鑼灣", "中環", "灣仔", "尖沙咀",
                      "深水埗", "觀塘", "沙田", "荃灣", "屯門"]
        }

        lang = get_language()
        area_options = common_areas.get(lang, common_areas["en"])

        st.markdown("**Quick Select:**")
        selected_quick = st.multiselect(
            "Select from common areas",
            options=area_options,
            default=[a for a in (pref.preferred_areas or []) if a in area_options],
            key="quick_area_select"
        )

        st.markdown("**Or enter custom areas:**")
        custom_areas = st.text_area(
            "Custom areas",
            value="\n".join([a for a in (pref.preferred_areas or []) if a not in area_options]),
            placeholder="e.g.,\nSai Ying Pun\nWhampoa\nTai Po",
            height=80,
        )

        # 合并选择
        preferred_areas = list(selected_quick) + [a.strip() for a in custom_areas.split("\n") if a.strip()]

        # 通勤设置
        st.markdown("---")
        st.markdown("### 🚇 Commute Preferences")
        col1, col2 = st.columns(2)
        with col1:
            max_commute = st.slider(
                t("max_commute"),
                min_value=10,
                max_value=90,
                value=pref.max_commute_time if pref.max_commute_time else 30,
                step=5,
                format="%d min"
            )
        with col2:
            commute_dest = st.text_input(
                t("commute_destination"),
                value=pref.commute_destination or "",
                placeholder="e.g., Central, HKU, CUHK"
            )

    # Step 3: 其他需求
    with step3:
        st.markdown("### 🏠 Property Requirements")
        st.markdown("Specify what you need and what you want to avoid.")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**✅ Must Have:**")
            must_have_options = ["AC", "Washing Machine", "Fridge", "Cooker", "Water Heater", "Furnished", "Balcony", "Pet Friendly"]
            existing_must = pref.must_have or []
            selected_must = st.multiselect(
                "Select essential facilities",
                options=must_have_options,
                default=[m for m in existing_must if m in must_have_options],
                key="must_have_select"
            )
            custom_must = st.text_input(
                "Other requirements (comma separated)",
                value=", ".join([m for m in existing_must if m not in must_have_options]),
                placeholder="e.g., Gym, Pool, Parking"
            )
            must_have = selected_must + [m.strip() for m in custom_must.split(",") if m.strip()]

        with col2:
            st.markdown("**❌ Deal Breakers:**")
            deal_breaker_options = ["No Pets Allowed", "No Cooking", "Shared Bathroom", "No Visitors", "Short Term Only"]
            existing_deal = pref.deal_breakers or []
            selected_deal = st.multiselect(
                "Select deal breakers",
                options=deal_breaker_options,
                default=[d for d in existing_deal if d in deal_breaker_options],
                key="deal_breaker_select"
            )
            custom_deal = st.text_input(
                "Other deal breakers (comma separated)",
                value=", ".join([d for d in existing_deal if d not in deal_breaker_options]),
                placeholder="e.g., No elevator, Old building"
            )
            deal_breakers = selected_deal + [d.strip() for d in custom_deal.split(",") if d.strip()]

    # 保存按钮
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown("**Current Settings Summary:**")
        st.caption(f"💰 Budget: HKD ${max_budget:,} | 📍 Areas: {len(preferred_areas)} selected")
    with col3:
        # 初始化保存状态
        if "saving_preferences" not in st.session_state:
            st.session_state["saving_preferences"] = False

        save_btn = st.button(
            f"💾 {t('save_preferences')}",
            type="primary",
            use_container_width=True,
            disabled=st.session_state["saving_preferences"]
        )

        if save_btn:
            st.session_state["saving_preferences"] = True
            with st.spinner("正在保存..."):
                try:
                    pm.update_preferences(
                        max_budget=float(max_budget) if max_budget > 0 else None,
                        preferred_areas=preferred_areas,
                        max_commute_time=int(max_commute) if max_commute > 0 else None,
                        commute_destination=commute_dest.strip() or None,
                        must_have=must_have,
                        deal_breakers=deal_breakers,
                    )
                    st.session_state["saving_preferences"] = False
                    st.success(t("save_success"))
                    # 导航到下一步（房源分析）
                    st.session_state["active_tab"] = 1
                    st.rerun()
                except Exception as e:
                    st.session_state["saving_preferences"] = False
                    st.error(f"保存失败: {e}")


def render_saved_listings(user_id: str) -> Optional[ListingRecord]:
    """渲染已保存房源列表（支持编辑）"""
    st.subheader(t("saved_listings"))

    repo = ListingRepository()
    listings = repo.get_user_listings(user_id)

    if not listings:
        st.info(t("no_saved"))
        return None

    selected = None

    # 初始化编辑状态
    if "editing_listing_id" not in st.session_state:
        st.session_state["editing_listing_id"] = None

    for listing in listings:
        is_editing = st.session_state["editing_listing_id"] == listing.id

        with st.expander(f"{listing.name} ({t('match_score')}: {listing.match_score or 'N/A'}%)", expanded=is_editing):
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

            with col1:
                st.write(f"**Rent:** {listing.listing_info.monthly_rent}")
                st.write(f"**Deposit:** {listing.listing_info.deposit}")
                st.write(f"**Furnished:** {listing.listing_info.furnished}")

            with col2:
                if st.button(f"📖 {t('view')}", key=f"view_{listing.id}"):
                    selected = listing

            with col3:
                if st.button(f"✏️ 编辑", key=f"edit_{listing.id}"):
                    st.session_state["editing_listing_id"] = listing.id
                    st.rerun()

            with col4:
                if st.button(f"🗑️ {t('delete')}", key=f"delete_{listing.id}"):
                    if repo.delete_listing(listing.id, user_id):
                        st.success(t("deleted"))
                        st.session_state["editing_listing_id"] = None
                        st.rerun()
                    else:
                        st.error(t("save_fail"))

            st.write(f"Updated: {listing.updated_at.strftime('%Y-%m-%d %H:%M')}")

            # 编辑表单
            if is_editing:
                st.markdown("---")
                st.markdown("**编辑房源信息**")

                # 名称编辑
                new_name = st.text_input(
                    "房源名称",
                    value=listing.name,
                    key=f"edit_name_{listing.id}"
                )

                # 房源信息编辑 - 3列布局展示全部9个字段
                col_a, col_b, col_c = st.columns(3)

                with col_a:
                    new_rent = st.text_input(
                        "月租",
                        value=listing.listing_info.monthly_rent or "",
                        key=f"edit_rent_{listing.id}"
                    )
                    new_mgmt_fee = st.text_input(
                        "管理费",
                        value=listing.listing_info.management_fee_included or "",
                        key=f"edit_mgmt_{listing.id}"
                    )
                    new_move_in = st.text_input(
                        "入住日期",
                        value=listing.listing_info.move_in_date or "",
                        key=f"edit_movein_{listing.id}"
                    )

                with col_b:
                    new_deposit = st.text_input(
                        "押金",
                        value=listing.listing_info.deposit or "",
                        key=f"edit_deposit_{listing.id}"
                    )
                    new_rates = st.text_input(
                        "差饷",
                        value=listing.listing_info.rates_included or "",
                        key=f"edit_rates_{listing.id}"
                    )
                    new_furnished = st.text_input(
                        "家具",
                        value=listing.listing_info.furnished or "",
                        key=f"edit_furnished_{listing.id}"
                    )

                with col_c:
                    new_agent_fee = st.text_input(
                        "中介费",
                        value=listing.listing_info.agent_fee or "",
                        key=f"edit_agent_fee_{listing.id}"
                    )
                    new_lease = st.text_input(
                        "租期",
                        value=listing.listing_info.lease_term or "",
                        key=f"edit_lease_{listing.id}"
                    )
                    new_repair = st.text_input(
                        "维修责任",
                        value=listing.listing_info.repair_responsibility or "",
                        key=f"edit_repair_{listing.id}"
                    )

                # 保存/取消按钮
                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.button("💾 保存修改", key=f"save_edit_{listing.id}", type="primary"):
                        # 更新房源信息
                        listing.name = new_name
                        listing.listing_info.monthly_rent = new_rent
                        listing.listing_info.deposit = new_deposit
                        listing.listing_info.agent_fee = new_agent_fee
                        listing.listing_info.management_fee_included = new_mgmt_fee
                        listing.listing_info.rates_included = new_rates
                        listing.listing_info.lease_term = new_lease
                        listing.listing_info.move_in_date = new_move_in
                        listing.listing_info.furnished = new_furnished
                        listing.listing_info.repair_responsibility = new_repair

                        # 保存到数据库
                        updated = repo.update_listing(listing)
                        if updated:
                            st.success("修改已保存")
                            st.session_state["editing_listing_id"] = None
                            st.rerun()
                        else:
                            st.error("保存失败")

                with col_cancel:
                    if st.button("❌ 取消", key=f"cancel_edit_{listing.id}"):
                        st.session_state["editing_listing_id"] = None
                        st.rerun()

    return selected


def load_custom_css() -> None:
    """加载自定义CSS样式"""
    import os
    css_path = os.path.join(os.path.dirname(__file__), "styles.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(
        page_title="RentWise - HK Rental Decision Assistant",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # 加载自定义CSS
    load_custom_css()

    st.title(f"🏠 {t('app_title')}")
    st.caption(t("app_subtitle"))

    # 初始化认证
    auth_manager = StreamlitAuthManager()

    # 侧边栏：用户信息和设置
    with st.sidebar:
        st.header(t("settings"))

        # 显示登录状态
        if auth_manager.is_authenticated():
            user = st.session_state.get("current_user")
            st.success(f"{t('logged_in_as')}: {user.email}")
            if st.button(t("logout")):
                auth_manager.logout()
                st.rerun()
            user_id = user.id
        else:
            st.warning(t("please_login"))
            user_id = None

        st.markdown("---")
        model_name = st.text_input("LLM model", value="llama3.3:is6620")

        if user_id:
            st.markdown("---")
            st.header(t("quick_stats"))
            repo = ListingRepository()
            count = len(repo.get_user_listings(user_id))
            st.metric(t("saved_listings_count"), count)

    # 如果需要登录，显示登录界面
    if not auth_manager.require_auth():
        return

    user_id = auth_manager.get_current_user_id()

    # 欢迎弹窗（首次访问）
    if is_first_visit():
        show_welcome_dialog()
        st.markdown("---")

    # 主界面导航（使用 st.radio 实现可编程导航）
    tab_labels = [
        "⚙️ 偏好设置 (第1步)",
        "📊 房源分析 (第2步)",
        "⚖️ 房源对比",
        f"💾 {t('saved_listings')}"
    ]

    # 初始化活动标签页
    if "active_tab" not in st.session_state:
        st.session_state["active_tab"] = 0

    selected_tab = st.radio(
        "导航",
        tab_labels,
        index=st.session_state["active_tab"],
        horizontal=True,
        label_visibility="collapsed"
    )
    st.session_state["active_tab"] = tab_labels.index(selected_tab)

    st.markdown("---")

    # Tab 1: 偏好设置（第一步）
    if selected_tab == tab_labels[0]:
        render_progress_indicator("preferences")
        st.markdown("---")
        if user_id:
            render_preferences(user_id)
        else:
            st.warning(t("please_login"))

    # Tab 2: 单房源分析（第二步）
    elif selected_tab == tab_labels[1]:
        render_progress_indicator("analysis")
        st.markdown("---")

        # 偏好设置提示
        hint = get_preference_hint(user_id)
        if hint:
            st.info(hint)

        text_inputs, image_files = listing_input_block("Single_Listing_A")

        col1, col2 = st.columns([1, 4])
        with col1:
            analyze_btn = st.button(f"🔍 {t('analyze')}", type="primary", key="btn_single")
        with col2:
            if st.button("🗑️ 清除输入", key="btn_clear_single"):
                # 清除所有输入框（包括文本和文件）
                for key in [
                    "Single_Listing_A_listing_text",
                    "Single_Listing_A_chat_text",
                    "Single_Listing_A_note_text",
                    "Single_Listing_A_txt_files",
                    "Single_Listing_A_images"
                ]:
                    if key in st.session_state:
                        del st.session_state[key]
                # 清除分析结果
                if "single_analysis_result" in st.session_state:
                    del st.session_state["single_analysis_result"]
                st.rerun()

        if analyze_btn:
            # 清除旧的分析结果，避免混淆
            if "single_analysis_result" in st.session_state:
                del st.session_state["single_analysis_result"]

            with st.spinner(t("analyzing")):
                try:
                    result = analyze_listing(
                        text_inputs,
                        image_files or [],
                        model_name=model_name,
                        lang=get_language(),
                    )

                    # 计算匹配度
                    if user_id:
                        pm = PreferenceManager(user_id)
                        result.match_score = pm.calculate_match_score(result.listing_info)

                    # 存储分析结果到 session_state
                    st.session_state["single_analysis_result"] = result

                    # 分析成功后清除输入框（可选，让用户决定）
                    # 保持输入以便用户对比修改
                    st.rerun()  # 刷新界面显示新结果
                except Exception as exc:
                    st.error(f"{t('error_analysis')}: {exc}")

        # 显示分析结果（从 session_state 获取）
        if "single_analysis_result" in st.session_state:
            result = st.session_state["single_analysis_result"]
            render_analysis(
                t("analysis_result"),
                result,
                show_save=bool(user_id),
                user_id=user_id,
                model_name=model_name
            )

    # Tab 3: 比较模式
    elif selected_tab == tab_labels[2]:
        render_progress_indicator("compare")
        st.markdown("---")

        # 选项卡：选择比较模式
        compare_mode = st.radio(
            t("compare_mode"),
            [t("select_from_saved"), t("input_new_listings")],
            horizontal=True,
            key="compare_mode"
        )

        if compare_mode == t("select_from_saved"):
            # 多选比较模式
            if not user_id:
                st.warning(t("please_login"))
            else:
                repo = ListingRepository()
                saved_listings = repo.get_user_listings(user_id)

                if not saved_listings:
                    st.info(t("no_saved_listings"))
                else:
                    # 创建选项列表
                    listing_options = {
                        f"{l.name} - {l.listing_info.monthly_rent or 'N/A'}"[:50]: l
                        for l in saved_listings
                    }

                    selected_keys = st.multiselect(
                        t("select_listings_compare"),
                        options=list(listing_options.keys()),
                        max_selections=5,
                    )

                    col_btn1, col_btn2 = st.columns([1, 1])
                    with col_btn1:
                        compare_btn = st.button(f"⚖️ {t('compare_selected')}", type="primary", disabled=len(selected_keys) < 2)
                    with col_btn2:
                        if st.button(t("clear_selection")):
                            st.rerun()

                    if compare_btn and len(selected_keys) >= 2:
                        selected_listings = [listing_options[k] for k in selected_keys]
                        n = len(selected_listings)

                        with st.spinner(t("comparing_listings").format(n=n)):
                            try:
                                from comparer import compare_multiple_listings, summarize_multi_comparison

                                # 准备比较数据
                                comparison_data = []
                                for l in selected_listings:
                                    info = l.listing_info  # l.listing_info 已经是 ListingInfo 对象
                                    comparison_data.append({
                                        "listing_info": info,
                                        "missing_count": len(l.missing_fields or []),
                                        "risk_count": len(l.risks or []),
                                        "match_score": l.match_score or 0,
                                    })

                                # 执行比较
                                result = compare_multiple_listings(comparison_data)

                                # 显示最佳推荐
                                best_idx = result["best_overall_index"]
                                best_name = selected_listings[best_idx].name
                                st.success(f"🏆 {t('best_overall')}: {best_name} ({result['overall_scores'][best_idx]:.1f}分)")

                                # 显示对比表格
                                st.subheader(f"📊 {t('comparison_summary')}")

                                table_data = {t("metric"): []}
                                for i, key in enumerate(selected_keys):
                                    table_data[key[:20]] = []

                                # 月租
                                table_data[t("metric")].append(t("monthly_rent"))
                                for i, l in enumerate(selected_listings):
                                    table_data[list(table_data.keys())[i+1]].append(
                                        l.listing_info.monthly_rent or "N/A"
                                    )

                                # 押金
                                table_data[t("metric")].append(t("deposit"))
                                for i, l in enumerate(selected_listings):
                                    table_data[list(table_data.keys())[i+1]].append(
                                        l.listing_info.deposit or "N/A"
                                    )

                                # 匹配度
                                table_data[t("metric")].append(t("match_score"))
                                for i, l in enumerate(selected_listings):
                                    table_data[list(table_data.keys())[i+1]].append(
                                        f"{l.match_score or 0}%"
                                    )

                                # 缺失字段数
                                table_data[t("metric")].append(t("missing_fields"))
                                for i, l in enumerate(selected_listings):
                                    table_data[list(table_data.keys())[i+1]].append(
                                        len(l.missing_fields or [])
                                    )

                                # 风险数
                                table_data[t("metric")].append(t("risk_count"))
                                for i, l in enumerate(selected_listings):
                                    table_data[list(table_data.keys())[i+1]].append(
                                        len(l.risks or [])
                                    )

                                st.table(table_data)

                                # 显示排名
                                st.subheader(f"📈 {t('overall_rank')}")
                                rank_cols = st.columns(n)
                                for i, (col, name) in enumerate(zip(rank_cols, selected_keys)):
                                    overall_rank = result["rankings"]["price_rankings"][i] + \
                                                   result["rankings"]["risk_rankings"][i] - 2
                                    col.metric(
                                        name[:15],
                                        f"#{result['rankings']['match_rankings'][i]}",
                                        f"Score: {result['overall_scores'][i]:.1f}"
                                    )

                                # LLM总结
                                summary = summarize_multi_comparison(
                                    listings_data=comparison_data,
                                    comparison_result=result,
                                    model=model_name,
                                    lang=get_language()
                                )
                                if summary:
                                    st.info(f"💡 {summary}")

                            except Exception as exc:
                                st.error(f"{t('error_comparison')}: {exc}")

        else:
            # 按需添加房源输入模式
            st.markdown("### 📝 " + t("input_new_listings"))

            # 初始化房源数量
            if "compare_listing_count" not in st.session_state:
                st.session_state["compare_listing_count"] = 1

            # 初始化存储输入的字典
            if "compare_inputs" not in st.session_state:
                st.session_state["compare_inputs"] = {}

            # 渲染房源输入框
            listing_count = st.session_state["compare_listing_count"]
            listing_labels = [t("listing_a"), t("listing_b"), "房源C", "房源D", "房源E"]

            for i in range(listing_count):
                with st.expander(f"🏠 {listing_labels[i]}", expanded=(i == 0)):
                    text_inputs, image_files = listing_input_block(f"Compare_Listing_{i}")
                    st.session_state["compare_inputs"][i] = {
                        "text_inputs": text_inputs,
                        "image_files": image_files
                    }

            # 添加/删除房源按钮
            col_add, col_clear = st.columns([1, 1])
            with col_add:
                if st.button("➕ 添加房源", disabled=listing_count >= 5) and listing_count < 5:
                    st.session_state["compare_listing_count"] = listing_count + 1
                    st.rerun()
            with col_clear:
                if st.button("🗑️ 重置", type="secondary"):
                    st.session_state["compare_listing_count"] = 1
                    st.session_state["compare_inputs"] = {}
                    if "compare_results" in st.session_state:
                        del st.session_state["compare_results"]
                    st.rerun()

            # 比较按钮
            compare_btn_disabled = listing_count < 2
            if st.button(f"⚖️ {t('compare_btn')}", type="primary", disabled=compare_btn_disabled):
                if listing_count < 2:
                    st.warning("请至少输入2个房源进行比较")
                else:
                    with st.spinner(t("analyzing_both")):
                        try:
                            results = []
                            for i in range(listing_count):
                                inputs = st.session_state["compare_inputs"].get(i, {})
                                result = analyze_listing(
                                    inputs.get("text_inputs", {}),
                                    inputs.get("image_files") or [],
                                    model_name=model_name,
                                    lang=get_language(),
                                )
                                if user_id:
                                    pm = PreferenceManager(user_id)
                                    result.match_score = pm.calculate_match_score(result.listing_info)
                                results.append(result)

                            st.session_state["compare_results"] = results

                        except Exception as exc:
                            st.error(f"{t('error_analysis')}: {exc}")

            # 显示比较结果
            if "compare_results" in st.session_state and len(st.session_state["compare_results"]) >= 2:
                results = st.session_state["compare_results"]
                n = len(results)

                st.markdown("---")
                st.subheader(f"📊 {t('comparison_summary')}")

                # 动态构建对比表格
                comp_df = {t("metric"): [t("monthly_rent"), t("deposit"), t("match_score"), t("missing_fields"), t("risk_count")]}
                for i, result in enumerate(results):
                    col_name = listing_labels[i] if i < len(listing_labels) else f"房源{i+1}"
                    comp_df[col_name] = [
                        result.listing_info.monthly_rent or "N/A",
                        result.listing_info.deposit or "N/A",
                        f"{result.match_score or 0}%",
                        len(result.missing_fields),
                        len(result.risks),
                    ]
                st.table(comp_df)

                # 找出最佳匹配
                best_idx = max(range(n), key=lambda i: results[i].match_score or 0)
                best_name = listing_labels[best_idx] if best_idx < len(listing_labels) else f"房源{best_idx+1}"
                best_score = results[best_idx].match_score or 0
                st.success(f"🏆 {best_name} 匹配度最高 ({best_score}%)")

                # 详细分析结果
                st.markdown("---")
                tabs = st.tabs([f"🏠 {listing_labels[i] if i < len(listing_labels) else f'房源{i+1}'}" for i in range(n)])
                for i, (tab, result) in enumerate(zip(tabs, results)):
                    with tab:
                        render_analysis(listing_labels[i] if i < len(listing_labels) else f"房源{i+1}", result, show_save=False)
                    st.info(f"💡 {summary}")

    # Tab 4: 已保存房源
    elif selected_tab == tab_labels[3]:
        render_progress_indicator("saved")
        st.markdown("---")
        if user_id:
            selected = render_saved_listings(user_id)
            if selected:
                st.markdown("---")
                # 显示完整分析
                from models import AnalysisResult
                view_result = AnalysisResult(
                    listing_info=selected.listing_info,
                    missing_fields=selected.missing_fields,
                    risks=selected.risks,
                    suggested_questions=selected.suggested_questions,
                    combined_text="",
                    ocr_texts=[],
                    match_score=selected.match_score,
                )
                render_analysis(f"View: {selected.name}", view_result, show_save=False)
        else:
            st.warning(t("please_login"))


if __name__ == "__main__":
    main()
