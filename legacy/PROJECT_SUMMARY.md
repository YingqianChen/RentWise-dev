> **DEPRECATED** — 本文档描述的是 RentWise 的 Streamlit 旧版本（v9.0, 2026-03-30）。
> 当前版本使用 FastAPI + Next.js 架构，请参阅项目根目录的 README.md 获取最新信息。
> 文中涉及 EasyOCR、ChromaDB、Streamlit Cloud 等内容仅适用于已归档的旧版本。

---

# RentWise 项目总结文档

**版本**: 9.0
**更新日期**: 2026-03-30
**项目状态**: 已部署到 Streamlit Cloud（部分功能待修复）
**在线地址**: <https://rentwisehk.streamlit.app/>

---

## 1. 项目概述

### 1.1 项目简介

RentWise 是一个面向香港租房市场的智能决策辅助系统，帮助租客分析房源信息、识别潜在风险、并根据个人偏好提供匹配度评分。

### 1.2 核心功能

| 功能             | 描述                             | 状态     |
| ---------------- | -------------------------------- | -------- |
| 混合智能风险分析 | 规则引擎 + LLM深度分析           | ✅ 已完成 |
| 市场价格分析     | 基于政府租金基准数据对比         | ✅ 已完成 |
| RAG语义搜索      | 向量检索区域识别（支持模糊匹配） | ✅ 已完成 |
| 用户偏好系统     | 预算、区域、设施等个性化设置     | ✅ 已完成 |
| 房源持久化       | 保存、查看、编辑、管理房源记录   | ⚠️ 待修复 |
| 用户认证         | 注册、登录、密码管理             | ✅ 已完成 |
| 房源对比         | 并排比较多个房源（支持按需添加） | ✅ 已完成 |
| OCR图片识别      | 从图片提取房源信息               | ✅ 已完成 |
| 智能命名         | LLM生成易识别的房源名称          | ✅ 已完成 |

### 1.3 技术栈

- **前端框架**: Streamlit
- **后端语言**: Python
- **数据库**: SQLAlchemy ORM (PostgreSQL - Neon)
- **LLM**: Groq API (Llama 3.3 70B) / Ollama (本地)
- **OCR**: EasyOCR + OpenCV (headless)
- **认证**: JWT + bcrypt
- **配置管理**: pydantic-settings
- **RAG向量检索**: LangChain + ChromaDB + Ollama Embeddings (nomic-embed-text)

---

## 2. 技术架构

### 2.1 项目结构

```
RentWise/
├── app.py                    # 主应用入口 (Streamlit UI)
├── config.py                 # 统一配置管理 (pydantic-settings)
├── models.py                 # Pydantic 数据模型
├── database.py               # SQLAlchemy ORM 配置 (香港时区)
├── repository.py             # 数据访问层 (Repository Pattern)
├── rules.py                  # 规则引擎 + 混合智能分析 + 价格风险
├── rent_analyzer.py          # 租金分析模块 (市场基准对比 + RAG语义搜索)
├── rag_chain.py              # RAG向量检索链 (语义搜索区域)
├── rent_documents.py         # 租金数据向量化脚本
├── llm_analyzer.py           # LLM深度风险分析
├── llm_provider.py           # LLM提供商抽象层 (Ollama/Groq)
├── llm_utils.py              # LLM调用工具函数
├── extractor.py              # LLM信息提取 + 智能命名
├── prompts.py                # LLM提示词模板
├── comparer.py               # 房源比较逻辑
├── preference_manager.py     # 用户偏好管理
├── auth.py                   # 用户认证系统
├── ocr_utils.py              # OCR图片文字提取
├── utils.py                  # 通用工具函数
├── i18n.py                   # 国际化支持 (简体中文)
├── onboarding.py             # 用户引导和进度指示
├── check_config.py           # 配置检查脚本
├── styles.css                # 自定义CSS样式
├── requirements.txt          # Python依赖
├── .env.example              # 环境变量示例
├── assets/                   # 静态资源目录
│   └── screenshots/          # 应用截图
│       ├── chat_ch_tra.png   # 繁体中文界面截图
│       └── chat_en.png       # 英文界面截图
├── examples/                 # 示例文件目录
│   └── text_upload.txt       # 文本上传示例
├── config/                   # 配置文件目录
│   ├── risk_rules.yaml       # 风险规则配置
│   └── rent_benchmarks.json  # 租金基准数据 (含区域关键词)
├── chroma_db/                # ChromaDB向量存储目录
├── locales/                  # 翻译文件目录
│   └── zh-cn.json            # 简体中文翻译
├── .streamlit/               # Streamlit配置目录
│   └── config.toml           # 部署配置
├── document/                 # 文档资料
│   ├── SDU_median_rents.pdf  # 香港各区租金中位数数据
│   └── AGuideToTenancy_ch.pdf # 香港租房指南
└── .env                      # 环境变量配置（不提交到Git）
```

### 2.2 数据流架构

```
用户输入 (文本/图片)
    ↓
[OCR处理] EasyOCR提取图片文字
    ↓
[LLM提取] Groq/Ollama + Llama 3.3 结构化提取
    ↓
[ListingInfo] 结构化房源信息对象
    ↓
┌─────────────────────────────────────┐
│         混合风险分析                 │
│  ┌─────────────┐  ┌─────────────┐  │
│  │ 规则引擎    │  │ LLM深度分析  │  │
│  │ - 字段缺失  │  │ - 隐性风险   │  │
│  │ - 数值异常  │  │ - 语义分析   │  │
│  └──────┬──────┘  └──────┬──────┘  │
│         └───────┬────────┘         │
│                 ↓                   │
│         结果合并去重                 │
└─────────────────────────────────────┘
    ↓
[AnalysisResult] 分析结果 + 风险项 + 匹配度
    ↓
用户界面展示 / 数据库存储
```

### 2.3 核心数据模型

#### ListingInfo (房源信息)

| 字段                    | 类型 | 说明           |
| ----------------------- | ---- | -------------- |
| monthly_rent            | str  | 月租           |
| deposit                 | str  | 押金           |
| agent_fee               | str  | 中介费         |
| management_fee_included | str  | 管理费是否包含 |
| rates_included          | str  | 差饷是否包含   |
| lease_term              | str  | 租期           |
| move_in_date            | str  | 入住日期       |
| furnished               | str  | 家具家电       |
| repair_responsibility   | str  | 维修责任       |

#### RiskItem (风险项)

| 字段        | 类型 | 说明                       |
| ----------- | ---- | -------------------------- |
| level       | str  | 风险等级 (high/medium/low) |
| title       | str  | 风险标题                   |
| description | str  | 风险描述                   |
| source      | str  | 来源 (rule/llm)            |

---

## 3. 风险检测逻辑详解

### 3.1 混合智能分析流程

**第一层: 规则引擎检测** (`rules.py`)

- 字段缺失检测: 遍历 ListingInfo 所有字段，检查是否为 "unknown"
- 数值验证: 月租范围 ($1,000-$200,000)、押金格式检查
- 风险等级配置:
  - deposit 缺失 → high
  - agent_fee 缺失 → medium
  - repair_responsibility 缺失 → medium

**第二层: LLM深度分析** (`llm_analyzer.py`)

- 调用 Groq/Ollama LLM 分析原文
- 识别类别: 财务风险、实际风险、欺诈信号
- 输出带置信度和证据的风险项

**结果合并**: `_merge_risks()`

- 同标题风险保留更高等级
- 标注来源 (rule/llm)

### 3.2 风险配置 (规划外置到 YAML)

当前硬编码在 `rules.py`:

```python
FIELD_RISK_CONFIG = {
    "deposit": {"level": "high", ...},
    "agent_fee": {"level": "medium", ...},
    ...
}
```

计划外置到 `config/risk_rules.yaml`。

---

## 4. 部署指南

### 4.1 环境配置

**环境变量** (`.env`):

```bash
# LLM 提供商选择
LLM_PROVIDER=groq

# Groq API 配置 (推荐，免费)
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile

# Ollama 配置 (需要校园网访问)
OLLAMA_HOST=your-server-address
OLLAMA_API_KEY=your-api-key
OLLAMA_MODEL=llama3.3:is6620

# 认证密钥
SECRET_KEY=your-secret-key

# 数据库 (PostgreSQL 推荐)
DATABASE_URL=postgresql://user:password@host:5432/dbname?sslmode=require
```

### 4.2 本地运行

```bash
# 克隆仓库
git clone https://github.com/YingqianChen/RentWise.git
cd RentWise

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入实际值

# 初始化数据库
python -c "from database import init_db; init_db()"

# 运行应用
streamlit run app.py
```

### 4.3 部署选项对比

| 平台                       | 成本     | 难度 | 适用场景         |
| -------------------------- | -------- | ---- | ---------------- |
| **Streamlit Cloud (推荐)** | 免费     | 低   | 原型/小规模用户  |
| PythonAnywhere             | 免费档   | 低   | 个人项目         |
| Railway/Render             | 免费档   | 中   | 需要数据库持久化 |
| VPS (阿里云/腾讯云)        | ~50元/月 | 中   | 生产环境         |

### 4.4 Streamlit Cloud 部署步骤

**步骤 1: 推送代码到 GitHub**

```bash
git remote add origin https://github.com/YingqianChen/RentWise.git
git push -u origin main
```

**步骤 2: 登录 Streamlit Cloud**

1. 访问 <https://share.streamlit.io/>
2. 点击 "Sign in with GitHub"

**步骤 3: 部署应用**

1. 点击 "New app"
2. 选择仓库：`YingqianChen/RentWise`
3. Main file path: `app.py`
4. 点击 "Advanced settings"

**步骤 4: 配置 Secrets（环境变量）**

```toml
LLM_PROVIDER = "groq"
GROQ_API_KEY = "your-groq-api-key"
GROQ_MODEL = "llama-3.3-70b-versatile"
SECRET_KEY = "your-secret-key"
##### 步骤 5: 点击 Deploy
```

**步骤 5: 点击 Deploy**

**生成随机密钥**:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**安全注意事项**:

- `.env` 文件已通过 `.gitignore` 排除，不会提交到 Git
- Secrets 在 Streamlit Cloud 中加密存储
- 课程材料 (`lab material/`) 已排除，避免泄露敏感信息

---

## 5. 开发历史

### 5.1 已完成阶段

#### Phase 1: 核心功能开发 ✅

- 混合智能风险分析
- 用户偏好系统
- 房源持久化
- 用户认证
- 多语言支持

#### Phase 2: 环境配置优化 ✅ (2026-03-27)

- 环境变量管理 (移除硬编码)
- 多语言完整集成
- 部署指导编写

#### Phase 3: 功能修复 ✅ (2026-03-27)

- 删除合同相关功能 (法律风险)
- 修复 Save listing 存储功能
- 多语言一致性修复

#### Phase 4: Bug修复 ✅ (2026-03-28)

- 修复对比功能 bug (`app.py:596`)
- 创建项目总结文档

#### Phase 5: 功能优化 ✅ (2026-03-29 上午)

- **修复时间问题**: 将 `repository.py` 中的 `datetime.utcnow()` 替换为 `get_hk_now()`，确保存储香港时区时间
- **改进房源命名**:
  - 重构 `LISTING_NAME_PROMPT`，使用中文提示词
  - LLM 根据原始文本智能生成名称，不再使用固定格式
  - 添加智能回退策略，根据区域、价格、房型生成名称
- **移除多语言支持**: 删除英文和繁体中文，只保留简体中文
  - 删除 `locales/en.json`、`locales/zh-hk.json`
  - 简化 `i18n.py`，移除语言选择器
- **改进比较界面**:
  - 初始只显示房源A输入框
  - 添加"添加房源"按钮，支持动态添加最多5个房源
  - 添加"重置"按钮，清除所有输入
- **PDF资料分析**:
  - 分析 `SDU_median_rents.pdf`（香港各区租金中位数数据）
  - 确认可用于价格分析参考

#### Phase 6: 安全配置加固 ✅ (2026-03-29 下午)

- **创建统一配置模块** (`config.py`):
  - 使用 `pydantic-settings` 管理配置
  - 启动时验证 `SECRET_KEY` 必须存在且>=16字符
  - 验证 `DATABASE_URL` 格式
- **移除硬编码密钥**:
  - 修改 `auth.py`，不再有默认密钥
  - 修改 `database.py`，使用配置模块
- **添加启动验证**:
  - `app.py` 启动时验证配置
  - 配置错误时显示友好提示

#### Phase 7: 功能增强 ✅ (2026-03-29 下午)

- **修复分析结果残留问题**:
  - 新分析前清除旧的 `session_state`
  - 添加 `st.rerun()` 刷新界面
- **已存房源编辑功能**:
  - 在 `render_saved_listings()` 添加编辑按钮
  - 支持修改房源名称和基本信息
  - 调用 `repository.update_listing()` 更新数据库
- **RAG价格分析增强**:
  - 创建 `config/rent_benchmarks.json` 租金基准数据
  - 创建 `rent_analyzer.py` 租金分析模块
  - 集成到 `rules.py` 风险检测流程
  - 支持有面积/无面积两种分析模式
  - 自动检测区域并对比市场价

#### Phase 8: RAG语义搜索实现 ✅ (2026-03-29)

- **关键词匹配改进**:
  - 添加模糊匹配 (`difflib.SequenceMatcher`)
  - 扩展区域别名（英文拼写变体、地标名）
- **向量检索实现**:
  - 新增 `rag_chain.py` - RAG检索接口
  - 新增 `rent_documents.py` - 数据向量化脚本
  - 使用 `langchain-ollama` + `langchain-chroma`
  - 嵌入模型: `nomic-embed-text` (Ollama)
- **集成到 rent_analyzer.py**:
  - `detect_district()` 优先使用语义搜索
  - 回退到关键词匹配和模糊匹配
  - 支持置信度过滤 (≥50%)

#### Phase 9: UI改进与部署准备 ✅ (2026-03-29)

- **保存偏好加载状态**:
  - 保存时显示 `st.spinner()` 加载提示
  - 按钮禁用防止重复点击
  - 添加 try/catch 错误处理
- **导航系统重构**:
  - 从 `st.tabs` 重构为 `st.radio`
  - 保存偏好后自动跳转到房源分析页
  - 支持通过 `session_state["active_tab"]` 编程控制
- **修复Widget Key冲突**:
  - 修复"加载示例"按钮的 textarea key 冲突
  - 移除重复的 `value` 参数，仅使用 `key`
- **清除输入功能完善**:
  - 清除按钮现在包含文件上传器 (`txt_files`, `images`)
- **编辑字段扩展**:
  - 从5个字段扩展到全部9个 ListingInfo 字段
  - 使用3列布局：月租/管理费/入住日期、押金/差饷/家具、中介费/租期/维修责任
- **自定义CSS样式**:
  - 新增 `styles.css` 文件
  - 中文字体优化 (Noto Sans SC, PingFang SC)
  - 文本溢出处理
  - 导航按钮样式美化
- **Streamlit Cloud部署配置**:
  - 新增 `.streamlit/config.toml`
  - 更新 `.gitignore` 排除敏感文件

#### Phase 10: 部署与安全加固 ✅ (2026-03-29)

- **Git历史安全清理**:
  - 使用 `git-filter-repo` 从历史中删除包含敏感信息的 `.env.example`
  - 生成新的 `SECRET_KEY` 并更新本地 `.env`
  - 清理 `PROJECT_SUMMARY.md` 中的服务器 IP 地址
- **创建安全的 `.env.example`**:
  - 仅包含占位符，不包含真实密钥
- **Streamlit Cloud 部署**:
  - 推送代码到 GitHub (`YingqianChen/RentWise`)
  - 配置 Streamlit Cloud Secrets
- **依赖兼容性修复**:
  - 使用 `opencv-python-headless` 替代 `opencv-python`（无需系统依赖）
  - 分离 `bcrypt` 为独立依赖（Python 3.14 兼容）
  - 移除 `packages.txt`（headless 版本不需要）
- **添加项目截图**:
  - `chat_ch_tra.png` - 繁体中文聊天界面截图
  - `chat_en.png` - 英文聊天界面截图
- **添加文档资料**:
  - `document/AGuideToTenancy_ch.pdf` - 香港租房指南
  - `document/SDU_median_rents.pdf` - 香港各区租金中位数

#### Phase 11: LLM 提供商切换 ✅ (2026-03-30)

- **问题背景**:
  - Ollama 服务器只能在校园网内访问
  - Streamlit Cloud 无法连接校园网内的服务器
  - 导致 connection timeout 错误
- **解决方案**:
  - 使用免费的 Groq API 替代 Ollama
  - Groq 提供免费额度（每分钟 30 次请求）
- **代码重构**:
  - 新增 `llm_provider.py` - LLM 提供商抽象层
  - 重构 `llm_utils.py` - 使用提供商模式
  - 支持 Ollama 和 Groq 两种提供商
  - 保持现有接口不变，无需修改其他代码
- **配置更新**:
  - 添加 `LLM_PROVIDER` 配置项（"groq" 或 "ollama"）
  - 添加 `GROQ_API_KEY` 和 `GROQ_MODEL` 配置项
  - 更新 `.env.example` 和 `requirements.txt`

#### Phase 12: PostgreSQL 数据库支持 ✅ (2026-03-30)

- **问题背景**:
  - Streamlit Cloud 重启后 SQLite 数据丢失
  - 需要云端数据库持久化存储
- **解决方案**:
  - 使用 Neon PostgreSQL 免费数据库
  - 5GB 免费存储，支持自动扩容
- **代码更新**:
  - 添加 `psycopg2-binary` 依赖
  - 更新配置支持 PostgreSQL 连接字符串
- **配置更新**:
  - 更新 `.env.example` 添加 PostgreSQL 配置说明

### 5.2 待完成阶段

#### Phase 13: Bug修复 (进行中)

- [ ] 清除输入功能异常
- [ ] 保存房源功能异常

#### Phase 14: 功能增强 (规划中)

- [ ] 通勤计算 (地图API集成)
- [ ] 价格趋势分析
- [ ] 移动端优化

---

## 6. 已知问题与解决方案

### 6.1 当前限制

| 限制      | 说明                      | 解决方案              |
| --------- | ------------------------- | --------------------- |
| OCR准确性 | EasyOCR对复杂排版识别有限 | 考虑集成更多OCR引擎   |
| 租房指南  | PDF为扫描件，未处理       | Phase 8 OCR + RAG     |
| 通勤计算  | 暂未实现                  | 规划中（地图API集成） |

### 6.2 待修复问题

| 问题         | 状态     | 说明                       |
| ------------ | -------- | -------------------------- |
| 清除输入功能 | 🔴 待修复 | 点击后报错或无反应         |
| 保存房源功能 | 🔴 待修复 | 点击后页面刷新但数据未保存 |

### 6.3 已修复问题

| 问题                     | 修复日期   | 解决方案                                     |
| ------------------------ | ---------- | -------------------------------------------- |
| API Key 硬编码           | 2026-03-27 | 使用环境变量                                 |
| 对比功能报错             | 2026-03-28 | 修复 ListingInfo 重复构造                    |
| Save listing 失败        | 2026-03-27 | 添加 combined_text 字段                      |
| 时间显示不正确           | 2026-03-29 | 使用 `get_hk_now()` 替代 `datetime.utcnow()` |
| 房源命名易读性差         | 2026-03-29 | 重构命名逻辑，LLM智能生成中文名称            |
| 云端 LLM 连接超时        | 2026-03-30 | 切换到 Groq API 替代校园网 Ollama            |
| 比较界面默认显示两房源   | 2026-03-29 | 改为按需添加模式                             |
| SECRET_KEY 硬编码        | 2026-03-29 | 创建 config.py 统一管理                      |
| 分析结果残留             | 2026-03-29 | 分析前清除旧 session_state                   |
| 已存房源无法编辑         | 2026-03-29 | 添加编辑功能                                 |
| 价格分析无数据支撑       | 2026-03-29 | 集成政府租金基准数据                         |
| 保存偏好无加载提示       | 2026-03-29 | 添加 spinner 和按钮禁用状态                  |
| 导航需手动切换           | 2026-03-29 | 重构为 radio 导航，自动跳转                  |
| 加载示例按钮报错         | 2026-03-29 | 修复 widget key 冲突                         |
| 清除输入未清除文件       | 2026-03-29 | 添加文件上传器 key 到清除列表                |
| 编辑字段不全             | 2026-03-29 | 扩展到全部9个字段                            |
| 中文字体显示问题         | 2026-03-29 | 添加自定义 CSS 样式                          |
| Git历史泄露敏感信息      | 2026-03-29 | 使用 git-filter-repo 清理历史                |
| Streamlit Cloud依赖冲突  | 2026-03-29 | 使用 opencv-python-headless                  |
| bcrypt Python 3.14不兼容 | 2026-03-29 | 直接使用 bcrypt 替代 passlib                 |
| 云端数据不持久化         | 2026-03-30 | 切换到 Neon PostgreSQL                       |

### 6.4 数据文件说明

| 文件                              | 内容                           | 用途                      |
| --------------------------------- | ------------------------------ | ------------------------- |
| `config/rent_benchmarks.json`     | 香港各区租金中位数（结构化）   | 价格分析基准 + 区域关键词 |
| `chroma_db/`                      | ChromaDB向量存储               | RAG语义搜索索引           |
| `document/SDU_median_rents.pdf`   | 香港分间单位租金中位数（原始） | 数据来源                  |
| `document/AGuideToTenancy_ch.pdf` | 香港租房指南（扫描件）         | RAG知识库（待处理）       |

**租金基准数据** (rent_benchmarks.json):

- 港岛：中西区、东区、南区、湾仔
- 九龙：九龙城、观塘、深水埗、黄大仙、油尖旺
- 新界：沙田、荃湾、屯门、元朗等
- 指标：月租中位数、每平方米月租
- 区域关键词：中英文别名、地标名、地铁站名

### 6.5 RAG使用说明

**首次使用需构建向量索引**:

```bash
# 1. 确保Ollama已安装嵌入模型
ollama pull nomic-embed-text

# 2. 构建向量索引
python rent_documents.py --build

# 3. 验证索引
python rent_documents.py --info
```

**RAG工作流程**:

1. `detect_district()` 优先使用向量语义搜索
2. 置信度 ≥ 50% 则返回语义匹配结果
3. 回退到精确关键词匹配
4. 最后尝试模糊匹配 (Levenshtein距离)

---

## 7. 协作者指南

### 7.1 快速开始

**前置要求**:

- Python 3.9+
- Git
- Groq API Key（免费）或 Ollama 服务器访问权限

**克隆并运行**:

```bash
# 1. 克隆仓库
git clone https://github.com/YingqianChen/RentWise.git
cd RentWise

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入实际值

# 5. 初始化数据库
python -c "from database import init_db; init_db()"

# 6. 运行应用
streamlit run app.py
```

### 7.2 环境变量说明

| 变量             | 必需         | 说明                                          |
| ---------------- | ------------ | --------------------------------------------- |
| `LLM_PROVIDER`   | 是           | LLM提供商 ("groq" 或 "ollama")                |
| `GROQ_API_KEY`   | Groq时必需   | Groq API 密钥                                 |
| `GROQ_MODEL`     | 否           | Groq 模型名称（默认 llama-3.3-70b-versatile） |
| `OLLAMA_HOST`    | Ollama时必需 | Ollama 服务器地址                             |
| `OLLAMA_API_KEY` | Ollama时必需 | Ollama API 认证密钥                           |
| `SECRET_KEY`     | 是           | JWT 密钥（至少16字符）                        |
| `DATABASE_URL`   | 否           | 数据库连接串（默认 SQLite）                   |

**生成 SECRET_KEY**:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**获取 Groq API Key**:

1. 访问 <https://console.groq.com/>
2. 使用 Google/GitHub 账号登录
3. 创建 API Key

**获取 Neon PostgreSQL**:

1. 访问 <https://neon.tech/>
2. 创建项目
3. 复制连接字符串

### 7.3 项目文件说明

| 文件/目录          | 用途                           |
| ------------------ | ------------------------------ |
| `app.py`           | 主应用入口，所有 UI 逻辑       |
| `config.py`        | 配置管理，启动时验证环境变量   |
| `auth.py`          | 用户认证（注册、登录、JWT）    |
| `rules.py`         | 风险检测规则引擎               |
| `llm_analyzer.py`  | LLM 深度分析                   |
| `llm_provider.py`  | LLM 提供商抽象层               |
| `llm_utils.py`     | LLM 调用工具函数               |
| `rent_analyzer.py` | 租金价格分析                   |
| `rag_chain.py`     | RAG 向量检索                   |
| `extractor.py`     | LLM 信息提取                   |
| `repository.py`    | 数据库操作                     |
| `models.py`        | 数据模型定义                   |
| `config/`          | 配置文件（风险规则、租金基准） |
| `locales/`         | 翻译文件                       |
| `document/`        | 参考文档（PDF）                |

### 7.4 开发工作流

**创建新功能**:

1. 从 `main` 创建新分支
2. 编写代码
3. 测试功能
4. 更新 `PROJECT_SUMMARY.md`（如有必要）
5. 提交并推送

**提交信息规范**:

```
<type>: <subject>

<body>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

**类型 (type)**:

- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `chore`: 构建/配置变更
- `refactor`: 代码重构

### 7.5 常见问题排查

**Q: 启动时报数据库错误**

```bash
python -c "from database import init_db; init_db()"
```

**Q: LLM分析无响应**

- 检查 `LLM_PROVIDER` 配置是否正确
- Groq: 验证 `GROQ_API_KEY` 是否有效
- Ollama: 检查服务器是否运行，网络是否通畅

**Q: OCR中文识别不准确**

- 确保图片清晰，文字对比度高
- 尝试手动输入文本

**Q: 时间显示不正确**

- 确保使用 `get_hk_now()` 而非 `datetime.utcnow()`

**Q: 配置验证失败**

- 检查 `.env` 文件是否存在
- 确认所有必需变量已设置
- 运行 `python check_config.py` 检查配置

### 7.6 添加新翻译

1. 编辑 `locales/zh-cn.json`
2. 添加对应的 key-value

### 7.7 添加新风险规则

1. 编辑 `rules.py` 中的 `FIELD_RISK_CONFIG`
2. 添加对应的翻译键到 `locales/zh-cn.json`

---

## 8. 文档索引

| 文档                     | 用途              |
| ------------------------ | ----------------- |
| PROJECT_SUMMARY.md       | 项目总览 (本文档) |
| PROJECT_DOCUMENTATION.md | 详细技术文档      |
| .env.example             | 环境变量示例      |

---

## 附录: 技术栈版本

```
Python >= 3.9
Streamlit >= 1.32.0
SQLAlchemy >= 2.0.0
Pydantic >= 2.7.0
groq >= 0.4.0
ollama >= 0.1.0
EasyOCR >= 1.7.0
opencv-python-headless >= 4.8.0
bcrypt >= 4.0.0
psycopg2-binary >= 2.9.0
langchain-ollama >= 0.1.0
langchain-chroma >= 0.2.0
chromadb >= 0.4.0
```
