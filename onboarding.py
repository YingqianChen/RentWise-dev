"""用户引导模块 - 首次访问引导和进度指示

功能:
1. 欢迎弹窗（首次访问）
2. 步骤进度指示器
3. 引导提示
"""

import streamlit as st
from typing import Optional


# 步骤定义
STEPS = [
    {"key": "preferences", "label": "偏好设置", "icon": "⚙️", "desc": "设置你的租房预算和区域偏好"},
    {"key": "analysis", "label": "房源分析", "icon": "📊", "desc": "粘贴房源信息，获取风险分析"},
    {"key": "compare", "label": "房源对比", "icon": "⚖️", "desc": "对比多个房源，做出最佳选择"},
    {"key": "saved", "label": "已存房源", "icon": "💾", "desc": "管理你保存的房源记录"},
]


def is_first_visit() -> bool:
    """检查是否是首次访问"""
    return "onboarding_completed" not in st.session_state


def show_welcome_dialog() -> bool:
    """
    显示欢迎弹窗

    Returns:
        True 如果用户点击了"开始使用"
    """
    # 使用 Streamlit 原生组件渲染欢迎信息
    st.markdown("### 🏠 欢迎使用慧租")
    st.markdown("**香港租房智能决策助手，帮你识别风险，找到理想居所**")
    st.markdown("")

    # 使用容器显示步骤
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        st.info("1️⃣ **设置偏好**\n\n设置你的租房预算和区域偏好")

    with col2:
        st.info("2️⃣ **分析房源**\n\n粘贴房源信息，获取风险分析")

    with col3:
        st.info("3️⃣ **对比选择**\n\n对比多个房源，做出最佳选择")

    st.markdown("")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 开始使用", type="primary", use_container_width=True, key="btn_start"):
            st.session_state["onboarding_completed"] = True
            return True

    return False


def render_progress_indicator(current_step: str) -> None:
    """
    渲染进度指示器

    Args:
        current_step: 当前步骤的key (preferences, analysis, compare, saved)
    """
    # 找到当前步骤的索引
    current_idx = 0
    for i, step in enumerate(STEPS):
        if step["key"] == current_step:
            current_idx = i
            break

    # 渲染进度条
    cols = st.columns(len(STEPS))

    for i, (col, step) in enumerate(zip(cols, STEPS)):
        with col:
            if i < current_idx:
                # 已完成
                st.markdown(f"<div style='text-align:center; color:#4CAF50;'>{step['icon']}<br>{step['label']}</div>", unsafe_allow_html=True)
            elif i == current_idx:
                # 当前
                st.markdown(f"<div style='text-align:center; color:#2196F3; font-weight:bold;'>{step['icon']}<br>{step['label']}</div>", unsafe_allow_html=True)
            else:
                # 未到达
                st.markdown(f"<div style='text-align:center; color:#9E9E9E;'>{step['icon']}<br>{step['label']}</div>", unsafe_allow_html=True)


def get_preference_hint(user_id: Optional[str]) -> Optional[str]:
    """
    获取偏好设置提示

    Returns:
        如果用户未设置偏好，返回提示信息
    """
    if not user_id:
        return None

    from preference_manager import PreferenceManager
    pm = PreferenceManager(user_id)
    pref = pm.get_or_create_preferences()

    # 检查是否有有效的偏好设置
    if pref.max_budget is None and not pref.preferred_areas:
        return "💡 提示：建议先在「偏好设置」中设置你的租房需求，这样我们可以为你计算匹配度"

    return None
