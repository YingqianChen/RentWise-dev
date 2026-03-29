# RentWise 项目文档

**版本**: 2.0
**更新日期**: 2026-03-27
**作者**: Claude Code Assistant

---

## 1. 项目概述

### 1.1 项目简介
RentWise 是一个面向香港租房市场的智能决策辅助系统，帮助租客分析房源信息、识别潜在风险、并根据个人偏好提供匹配度评分。

### 1.2 核心功能
- **混合智能风险分析**: 结合规则引擎和LLM深度分析
- **用户偏好系统**: 支持预算、区域、设施等个性化设置
- **房源持久化**: 保存、查看、管理多个房源记录
- **多语言支持**: 英文、简体中文、繁体中文
- **用户认证**: 注册、登录、密码管理
- **房源对比**: 并排比较多个房源

---

## 2. 项目结构

```
RentWise/
├── app.py                    # 主应用入口 (Streamlit UI)
├── models.py                 # Pydantic 数据模型
├── database.py               # SQLAlchemy ORM 配置
├── repository.py             # 数据访问层 (Repository Pattern)
├── rules.py                  # 规则引擎 + 混合智能分析
├── llm_analyzer.py           # LLM深度风险分析
├── extractor.py              # LLM信息提取
├── prompts.py                # LLM提示词模板
├── comparer.py               # 房源比较逻辑
├── preference_manager.py     # 用户偏好管理
├── auth.py                   # 用户认证系统
├── ocr_utils.py              # OCR图片文字提取
├── utils.py                  # 通用工具函数
├── i18n.py                   # 国际化/多语言支持
├── requirements.txt          # Python依赖
├── README.md                 # 项目说明
└── PROJECT_DOCUMENTATION.md  # 本文档
```

---

## 3. 各模块详细说明

### 3.1 app.py - 主应用入口
**作用**: Streamlit Web界面主程序

**主要功能**:
- 4个Tab界面: 单一分析、对比、偏好设置、已存房源
- 用户登录/注册界面集成
- 分析结果可视化展示
- 房源保存/加载功能

**关键函数**:
- `analyze_listing()`: 执行房源分析流程
- `render_analysis()`: 渲染分析结果
- `render_preferences()`: 偏好设置界面
- `render_saved_listings()`: 已保存房源列表

### 3.2 models.py - 数据模型
**作用**: 定义所有Pydantic数据模型

**核心模型**:
| 模型 | 说明 |
|------|------|
| `ListingInfo` | 房源信息 (8个核心字段) |
| `RiskItem` | 风险项 (级别、标题、描述、来源) |
| `AnalysisResult` | 分析结果 (包含匹配度评分) |
| `UserPreference` | 用户偏好设置 |
| `ListingRecord` | 数据库房源记录 |
| `User` | 用户模型 |

### 3.3 database.py - 数据库配置
**作用**: SQLAlchemy ORM配置和模型定义

**数据库表**:
- `users`: 用户信息
- `user_preferences`: 用户偏好
- `listing_records`: 房源记录

**特点**:
- 支持SQLite (开发) 和 PostgreSQL (生产)
- 通过环境变量 `DATABASE_URL` 切换

### 3.4 repository.py - 数据访问层
**作用**: 封装所有数据库操作

**Repository类**:
- `UserRepository`: 用户CRUD
- `PreferenceRepository`: 偏好CRUD
- `ListingRepository`: 房源CRUD

### 3.5 rules.py - 规则引擎
**作用**: 风险检测核心模块

**功能**:
- `detect_missing_fields()`: 检测缺失字段
- `detect_risks_by_rules()`: 基于规则的风险检测
- `run_hybrid_analysis()`: 混合智能分析 (规则+LLM)

**混合智能策略**:
1. 规则引擎检测确定性高的风险 (如押金缺失)
2. LLM分析文本中的隐含风险 (如异常条款)
3. 合并去重后输出

### 3.6 llm_analyzer.py - LLM深度分析
**作用**: 调用LLM进行深度风险分析

**功能**:
- `analyze_deep_risks()`: 分析文本中的隐含风险
- `analyze_price_reasonableness()`: 价格合理性分析 (轻量级)

**提示词**: `DEEP_ANALYSIS_PROMPT` - 指导LLM识别四类风险:
1. 财务风险
2. 合同风险
3. 实用风险
4. 法律/欺诈风险

### 3.7 preference_manager.py - 偏好管理
**作用**: 用户偏好管理和匹配度计算

**功能**:
- `calculate_match_score()`: 计算房源匹配度 (0-100分)
- `get_preference_warnings()`: 生成个性化警告

**匹配度计算维度**:
| 维度 | 权重 |
|------|------|
| 价格匹配 | 30% |
| 区域匹配 | 25% |
| 设施匹配 | 20% |
| 排除项检查 | 25% |

### 3.8 auth.py - 用户认证
**作用**: 完整的用户认证系统

**功能**:
- 用户注册/登录/登出
- JWT令牌管理
- 密码哈希 (bcrypt)
- Streamlit会话集成

**安全特性**:
- 密码强度验证 (8位+字母+数字)
- JWT令牌过期 (7天)
- 密码bcrypt哈希

### 3.9 i18n.py - 多语言支持
**作用**: 国际化支持

**支持语言**:
- `en`: English
- `zh-cn`: 简体中文
- `zh-hk`: 繁體中文

**使用方法**:
```python
from i18n import t, language_selector

# 在UI中使用
title = t("app_title")  # 根据当前语言返回对应文本
```

---

## 4. 部署方案评估

### 4.1 推荐部署方案 (低成本/免费)

| 方案 | 成本 | 难度 | 适用场景 |
|------|------|------|----------|
| **Streamlit Cloud (推荐)** | 免费 | 低 | 原型/小规模用户 |
| **PythonAnywhere** | 免费档 | 低 | 个人项目 |
| **Railway/Render** | 免费档 | 中 | 需要数据库持久化 |
| **VPS (阿里云/腾讯云)** | ~50元/月 | 中 | 生产环境 |

### 4.2 Streamlit Cloud 部署 (推荐)

**优点**:
- 完全免费 (公开仓库)
- GitHub集成，自动部署
- 无需服务器管理
- 自带HTTPS

**限制**:
- 需要公开GitHub仓库 (或付费私有)
- 1GB内存限制
- 计算资源有限

**部署步骤**:
1. 推送代码到GitHub公开仓库
2. 访问 https://share.streamlit.io/
3. 连接GitHub仓库
4. 选择 `app.py` 作为主文件
5. 添加环境变量 (如需要)

**环境变量配置**:
```bash
DATABASE_URL=sqlite:///./rentwise.db  # 或使用PostgreSQL
SECRET_KEY=your-secret-key-here       # JWT密钥
```

### 4.3 生产环境数据库迁移

**从SQLite迁移到PostgreSQL**:
```python
# 设置环境变量
DATABASE_URL=postgresql://user:pass@host:5432/rentwise

# 应用会自动切换，无需修改代码
```

**推荐的免费PostgreSQL托管**:
- **Supabase**: 免费档500MB
- **Railway**: 免费档每月$5额度
- **Render**: 免费档90天有效期

---

## 5. UI美化评估与建议

### 5.1 当前状态评估

**现状**:
- 基于Streamlit原生组件
- 布局简单直接
- 功能性优先，美观性一般

**优点**:
- 开发速度快
- 无需前端技能
- 响应式布局

**不足**:
- 视觉效果单一
- 缺乏品牌识别
- 交互体验有限

### 5.2 建议时机

**推荐策略: 分阶段实施**

```
Phase 1 (当前) -> Phase 2 -> Phase 3
 功能优先      ->  优化    ->  美化
```

**理由**:
1. **功能验证优先**: 先确认核心功能满足用户需求
2. **快速迭代**: 功能变化可能导致UI重构
3. **资源分配**: 将时间投入核心功能更划算

### 5.3 UI美化方案对比

| 方案 | 工作量 | 效果 | 技术栈 |
|------|--------|------|--------|
| **A. Streamlit美化** | 1-2天 | 中等 | Streamlit原生 |
| **B. 自定义CSS** | 2-3天 | 较好 | CSS + Streamlit |
| **C. 独立前端** | 2-3周 | 优秀 | React/Vue + FastAPI |

### 5.4 推荐的Phase 2美化 (Streamlit优化)

**立即可做的改进**:
1. **自定义CSS**: 注入CSS美化按钮、卡片
2. **图标优化**: 使用emoji和Streamlit图标
3. **布局优化**: 更好的列宽分配
4. **颜色主题**: 品牌色系

**示例代码** (自定义CSS):
```python
import streamlit as st

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .risk-card {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)
```

### 5.5 Phase 3独立前端 (如需要)

**何时考虑**:
- 用户量增长，需要更好性能
- 需要复杂交互 (如地图集成)
- 品牌商业化需求

**技术栈建议**:
- **前端**: Next.js + Tailwind CSS
- **后端**: FastAPI (Python)
- **部署**: Vercel (前端) + Railway (后端)

---

## 6. 已知限制与待改进项

### 6.1 当前实现限制

| 限制 | 说明 | 改进建议 |
|------|------|----------|
| **LLM依赖** | 需要Ollama服务器 | 支持OpenAI/Anthropic作为备选 |
| **OCR准确性** | EasyOCR对复杂排版识别有限 | 考虑集成更多OCR引擎 |
| **价格分析** | 仅基于LLM知识，非实时数据 | 接入房产API获取市场价 |
| **通勤计算** | 未实现 | Phase 4添加Google Maps API |
| **RAG知识库** | 未实现 | Phase 3添加LangChain RAG |

### 6.2 硬编码内容

**当前硬编码**:
- `rules.py`: `FIELD_RISK_CONFIG` - 字段风险配置 (可接受)
- `auth.py`: `SECRET_KEY` - 需改为环境变量
- `llm_utils.py`: Ollama服务器地址

**建议**:
- 将配置移至 `.env` 文件
- 添加配置管理页面

### 6.3 测试覆盖

**当前状态**: 无自动化测试

**建议添加**:
```
tests/
├── test_rules.py
├── test_preference_manager.py
├── test_repository.py
└── test_auth.py
```

---

## 7. 后续开发路线图

### Phase 1 (已完成) ✅
- [x] 混合智能风险分析
- [x] 用户偏好系统
- [x] 房源持久化
- [x] 用户认证
- [x] 多语言支持 (基础)

### Phase 2 (建议) 📋
- [ ] 部署到Streamlit Cloud
- [ ] UI美化 (CSS优化)
- [ ] 完整多语言集成
- [ ] 单元测试
- [ ] 配置外部化

### Phase 3 (可选) 📋
- [ ] RAG知识库 (LangChain)
- [ ] 租房指南文档集成
- [ ] 智能问答功能
- [ ] 房源分享功能

### Phase 4 (未来) 📋
- [ ] 通勤计算 (Google Maps API)
- [ ] 价格趋势分析
- [ ] 邮件提醒功能
- [ ] 移动端优化

---

## 8. 使用说明

### 8.1 本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 初始化数据库
python -c "from database import init_db; init_db()"

# 3. 运行应用
streamlit run app.py
```

### 8.2 配置Ollama服务器

确保Ollama服务器可访问，或在 `llm_utils.py` 中修改配置:
```python
DEFAULT_BASE_URL = "http://your-ollama-server:11434"
```

### 8.3 环境变量

```bash
# .env 文件
DATABASE_URL=sqlite:///./rentwise.db
SECRET_KEY=your-secret-key-change-in-production
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 9. 故障排除

### 常见问题

**Q: 启动时报数据库错误**
A: 运行 `python -c "from database import init_db; init_db()"` 初始化数据库

**Q: LLM分析无响应**
A: 检查Ollama服务器是否运行，模型是否正确加载

**Q: OCR中文识别不准确**
A: 确保图片清晰，文字对比度高

---

## 10. 贡献与反馈

如有问题或建议，请通过以下方式反馈:
- 提交GitHub Issue
- 联系项目维护者

---

## 附录: 技术栈版本

```
Python >= 3.9
Streamlit >= 1.32.0
SQLAlchemy >= 2.0.0
Pydantic >= 2.7.0
Ollama >= 0.1.0
```
