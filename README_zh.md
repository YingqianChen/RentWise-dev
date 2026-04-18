# RentWise

RentWise 是一个面向香港租客的候选房源研究工作区。你把 listing（文本、链接、截图）
导入进来，系统会提取字段、按你的条件打分、估算真实门到门通勤时间，并告诉你
下一步该核实什么。

本文件是当前代码库的规范性文档。英文主文档位于 `README.md`，两份文档应保持
同步更新。

- `backend/` — FastAPI + SQLAlchemy + Alembic
- `frontend/` — Next.js 14 + React + TypeScript + Tailwind
- `legacy/` — 已归档的 Streamlit 原型，仅供参考
- `docs/` — 设计说明
- `document/` — benchmark 使用的原始 PDF

## RentWise 做什么

**候选房源池工作流**
- 注册登录、搜房 project（含预算）、项目删除
- 文本 + 多图片混合导入 candidate；OCR 与 assessment 在应用内后台任务中执行
- Dashboard：行动导向的 priority queue + 按 blocker 聚合的 investigation checklist
- Candidate detail：决策快照 + blockers、reassess / shortlist / reject、
  编辑自动重评、删除、按需生成给房东/中介的外联草稿
- 每个 candidate 都有顶层 first-pass recommendation：shortlist / not ready /
  likely reject

**Compare workflow**
- 从 shortlist 手动选择 2 个及以上 candidate
- 使用分组而非伪精确排名：best current option、viable alternatives、
  not ready for fair comparison、likely drop
- 每张卡片解释：为什么被归到此组、主要 tradeoff、未解决 blocker、下一步
- LLM agent briefing（current take / why now / what could change /
  today's move / confidence note），模型失败时有 deterministic fallback

**通勤证据（新功能）**
- 项目级配置单一目的地
- Candidate 位置以 extraction 为主，允许用户校正
- 主 geocoder：香港政府 ALS（免费、无需 key，对中英文 HK 地址都权威）
- 兜底 geocoder 与全部 routing：Amap（需要 `AMAP_API_KEY`）
- 支持 transit / driving / walking 三种出行方式
- 降级友好：解析失败时只隐藏通勤卡片，不阻断其他功能

**UI**
- 所有面向用户的页面（落地页、登录、项目列表、dashboard、candidate detail、
  compare）都共用同一套视觉系统：Sparkles 品牌头、渐变背景、内联
  Button / Badge / Card 原语，纯 Tailwind，无 shadcn runtime。

## 仓库结构

```text
RentWise/
  backend/
    app/
      api/v1/              # auth, projects, candidates, dashboard, comparison, investigation
      core/                # 配置
      db/                  # models, session
      services/            # extraction、assessment、compare、OCR、commute …
      integrations/        # als、amap、llm
      data/                # 版本化 benchmark 数据
    alembic/               # migration
    tests/
  frontend/
    app/                   # Next.js app router 页面
    lib/                   # api client、types、auth helpers
  docs/                    # 设计说明
  document/                # 源 PDF
  legacy/                  # 归档原型
```

### Backend 模块

- `app/main.py` — FastAPI 入口、startup hooks（OCR 预热）
- `app/core/config.py` — 环境变量配置；secret 只从 `.env` 读取
- `app/db/models.py` — users、projects、candidates、assessments、source assets
- `app/api/v1/*.py` — auth、projects、candidates、dashboard、comparison、investigation
- `app/services/extraction_service.py` — 基于 LLM 的结构化提取
- `app/services/cost_assessment_service.py` — 预算匹配与置信度
- `app/services/clause_assessment_service.py` — 租期、维修、入住时机
- `app/services/candidate_assessment_service.py` — 综合推荐
- `app/services/candidate_pipeline_service.py` — 编排 extraction + assessment
- `app/services/candidate_import_service.py` + `candidate_import_background_service.py` —
  导入入口与后台 worker
- `app/services/ocr_service.py` — OCR provider 抽象（rapidocr / paddleocr / mistral）
- `app/services/file_storage_service.py` — 上传存储抽象
- `app/services/dashboard_service.py` + `priority_service.py` +
  `investigation_service.py` — dashboard 组装
- `app/services/comparison_service.py` + `comparison_briefing_service.py` —
  compare grouping 与 LLM briefing
- `app/services/benchmark_service.py` — SDU 中位租金 benchmark 查找
- `app/services/commute_service.py` — 先解析 candidate 与目的地，再做路径规划
- `app/services/candidate_contact_plan_service.py` — 外联草稿
- `app/integrations/als/client.py` — 香港政府 ALS 地址查询服务客户端
- `app/integrations/amap/client.py` — 高德 geocode / POI / 路径规划客户端

### Frontend 页面

- `app/page.tsx` — 落地页
- `app/login/page.tsx` — 登录 / 注册
- `app/projects/page.tsx` — 项目列表 + 新建
- `app/projects/[id]/page.tsx` — dashboard、priority queue、investigation checklist
- `app/projects/[id]/import/page.tsx` — 文本 + 图片混合导入
- `app/projects/[id]/candidates/[candidateId]/page.tsx` — candidate detail
- `app/projects/[id]/compare/page.tsx` — compare 工作区 + briefing
- `lib/api.ts` / `lib/types.ts` / `lib/auth.ts`

## 启动

### Backend

```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

API：`http://localhost:8000`，Swagger：`/docs`。

OCR 默认使用 `rapidocr_onnxruntime`（轻量、Windows 友好）。内存受限的
云环境（例如 Render 免费 512MB）应改为 `OCR_PROVIDER=mistral` 并配置
`MISTRAL_API_KEY`。Paddle 仍保留作显式 fallback，切换时需要自行安装
`paddleocr` 与 `paddlepaddle`。

如果你的本地 Postgres 是早期通过 `create_all()` 启动路径创建的，在切到
常规 `alembic upgrade head` 流程之前需要先执行一次 `alembic stamp head`
对齐 Alembic revision。

### Frontend

```bash
cd frontend
npm install
copy .env.local.example .env.local
npm run dev
```

Frontend：`http://localhost:3000`。

## 环境变量

### Backend（必填）

- `SECRET_KEY`
- `DATABASE_URL` — 推荐 `postgresql+asyncpg://...?ssl=require`。常见的
  `postgres://` 与 `postgresql://` 串会被自动规范化为 asyncpg 格式。
- `LLM_PROVIDER` — `groq` 或 `ollama`

### Backend（可选）

- `GROQ_API_KEY`、`GROQ_MODEL`
- `OLLAMA_HOST`、`OLLAMA_API_KEY`、`OLLAMA_MODEL`
- `BACKEND_CORS_ORIGINS` — 逗号分隔的多个 origin
- `AMAP_API_KEY` — 启用通勤路径规划；没有时通勤卡片会显示
  "Map service not configured"，其他功能正常
- `FILE_STORAGE_PROVIDER`、`LOCAL_UPLOAD_ROOT`
- `OCR_PROVIDER`（`rapidocr` | `paddleocr` | `mistral` | `ocr_space`）
- `MISTRAL_API_KEY`（当 `OCR_PROVIDER=mistral` 时必填）、`MISTRAL_OCR_MODEL`
- `OCR_MAX_IMAGE_DIMENSION`、`OCR_PREWARM_ON_STARTUP`、`LOW_MEMORY_MODE`
- `PADDLEOCR_LANG`、`OCR_USE_DOC_ORIENTATION`、`OCR_USE_DOC_UNWARPING`、
  `OCR_USE_TEXTLINE_ORIENTATION`、`PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK`

香港政府 ALS geocoder 不需要 key，也不需要任何配置。

### Frontend

- `NEXT_PUBLIC_API_URL` — 必须是纯后端 URL，例如
  `https://rentwise-api.onrender.com`。**不要**把
  `NEXT_PUBLIC_API_URL=...` 这种完整赋值语句贴进 Vercel 的 value 输入框。

## 部署

推荐的托管组合：

1. **Frontend** — Vercel，项目根目录 `frontend/`
2. **Backend** — Render Python web service，根目录 `backend/`，Python runtime
   固定到 3.11（仓库根目录已提供 `.python-version = 3.11.11`；若 Render 未识别，
   在环境变量里补上 `PYTHON_VERSION=3.11.11` 强制覆盖）
3. **Database** — Neon，asyncpg 连接串
4. Vercel 的 `NEXT_PUBLIC_API_URL` 指向 Render 后端域名
5. Render 的 `BACKEND_CORS_ORIGINS` 包含你的 Vercel 正式（与 preview）域名

Render 启动命令：

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Render 关键环境变量：

- `APP_ENV=production`
- `DATABASE_URL=postgresql+asyncpg://<user>:<pw>@<host>/<db>?ssl=require`
- `SECRET_KEY=<strong-random-secret>`
- `LLM_PROVIDER=groq` + `GROQ_API_KEY=<...>`
- `AMAP_API_KEY=<...>`（开启通勤）
- 免费 512MB：`OCR_PROVIDER=mistral` + `MISTRAL_API_KEY`、
  `OCR_PREWARM_ON_STARTUP=false`、`LOW_MEMORY_MODE=true`
- 更大规格：`OCR_PROVIDER=rapidocr`

存储 caveat：本地存储适合短周期 demo，但 Render 文件系统是临时的。
真正进入生产前要把 candidate uploads 迁到 object storage。

## 测试

```bash
cd backend
python -m unittest discover -s tests -p "test_*.py"
```

真实 Postgres 集成流：

```bash
cd backend
set RUN_DB_INTEGRATION=1
.\venv\Scripts\python.exe -m unittest tests.integration.test_db_flow
```

测试覆盖 priority ranking、investigation checklist、candidate recommendation、
compare grouping + explanation + briefing fallback、OCR parsing、benchmark
lookup。

## 数据安全清单

推送到 GitHub 前确认：

- `backend/.env`、`frontend/.env.local`、任何根目录 `.env` 都被 git 忽略
- `backend/storage/` 被 git 忽略
- 不提交模型缓存、日志、虚拟环境、构建产物
- 任何曾出现在聊天、终端、截图中的 credential 都视作已暴露，立刻轮换
- `.env.example` 只保留占位符
- 每次 push 前都检查 `git status`

## Evidence 层

RentWise 使用三条独立的 evidence 层。三者都不直接进入主 candidate score，
只作为帮助用户判断的支撑证据。

**1. SDU benchmark**（已上线）
- 来源：`document/SDU_median_rents.pdf`，抽取到
  `backend/app/data/benchmark_sdu_rents.json`
- 只有当 candidate 被判定为 likely SDU、并且有 district 时才展示。
  卡片始终带明显的 "仅针对 subdivided units、仅作 general reference"
  免责说明。

**2. 通勤**（已上线）
- 项目级配置：enabled flag、destination label、destination query、
  mode（transit/driving/walking）、max minutes
- Candidate 级位置：address、building name、nearest station、district、
  location confidence
- 解析阶梯：HK Gov ALS → Amap /geocode → Amap POI
- 路径规划：Amap transit / driving / walking
- 所有 geocoder 都失败时会显示 "Location not precise enough" 并附带
  具体 confidence_note，而不是掩盖失败原因。

**3. Tenancy guide RAG**（未实现）
- `document/AGuideToTenancy_ch.pdf` 是扫描件；全文 OCR 与窄范围
  explanation-support retrieval 要等 OCR 质量达标后再做，目前不在
  短期 roadmap 内。

## 阶段状态

- **Phase 1**（auth、projects、candidate import、dashboard、detail、
  编辑、删除、预算、migration、测试）— 已完成
- **Phase 2**（compare MVP：grouping + briefing）— 已完成
- **Phase 2.5**（agent-style explanation、decision signals）— 进行中
- **Phase 3**（通勤证据 + 统一 UI 改版）— 已完成

## 产品哲学

当前方向的两条核心事实：

1. 更多分析输出并不会自动带来更好决策。产品最强的时刻，是用户在几秒内
   就能看到下一步该做什么。
2. 外部 evidence 应该支撑信任，而不是制造虚假精确感。Benchmark 保持范围
   克制；commute 永远是支撑证据，不进入隐藏打分；tenancy RAG 要等源质量
   就绪再做。
