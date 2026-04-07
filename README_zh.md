# RentWise

本文件是当前代码库的**规范性项目文档**。

如果旧的笔记、spec 或 refactor 文档与本文件冲突，请以本文件为准。英文主文档位于 `README.md`；本中文版本用于组内 review，两份文档应保持同步更新。

RentWise 正在从一个 Streamlit 原型重构为 monorepo，当前结构为：

- `backend/`: FastAPI + SQLAlchemy + LangGraph
- `frontend/`: Next.js + React + TypeScript
- `legacy/`: 仅供参考的旧版 Streamlit 原型代码

## 当前产品范围

当前重构版已经覆盖了 Phase 1 稳定化内容，以及第一版 Phase 2 compare workflow。

### Candidate-pool workflow

当前产品核心是“候选房源池决策流程”：

- 用户注册与登录
- 搜房 project 创建
- 搜房 project 预算编辑
- 搜房 project 删除
- 文本 + 多图片混合导入 candidate
- 导入后后台执行 OCR / extraction / assessment
- dashboard 提供行动导向的 priority candidates 和 investigation items
- dashboard 中的 investigation checklist 会聚合同类 blocker，而不是对每个 listing 重复提示
- candidate detail 支持 reassess / shortlist / reject
- candidate detail 支持按需生成给房东 / 中介的下一条沟通草稿
- candidate 删除带确认框
- candidate 编辑后自动重新评估
- candidate detail 现在把主界面收敛在 decision snapshot 和 blocker 上，benchmark、OCR evidence 和更深的结构化细节默认作为次级信息按需展开
- candidate detail 现在新增一个克制的 Decision signals 次级区块，用来承接不适合塞进固定字段、但又真正影响决策的证据
- dashboard 会把后台处理中 candidate 显示为 processing work，而不是误渲染成空结果
- dashboard 支持直接删除 candidate
- 预算修改后会触发已有已完成 candidate 的预算相关 reassessment
- 顶层 first-pass recommendation 包括：
  - shortlist recommendation
  - not ready
  - likely reject

### Compare workflow

当前 compare 体验是一个 shortlist 决策工作区，而不是简单字段对照表：

- 在 dashboard 手动选择 candidate
- 对 2 个及以上 candidate 进行 compare
- 使用“分组”而不是伪精确排名：
  - best current option
  - viable alternatives
  - not ready for fair comparison
  - likely drop
- explanation-rich compare cards，说明：
  - 为什么被归到该组
  - 主要 tradeoff
  - 未解决 blocker
  - 下一步行动
- compare set 推荐下一步动作：
  - 先联系谁
  - 接下来该问什么
  - 谁可以去看房
  - 谁可以降优先级
- dashboard 上有 suggested compare preview
- candidate detail 也保留 compare context，保证不同页面决策叙事一致
- compare 页面有 LLM-assisted agent briefing，聚焦：
  - current take
  - why now
  - what could change
  - today's move
  - confidence note
- compare 页面压缩 supporting differences，让主决策流程更聚焦 briefing、grouping 和 next actions

当前不在范围内：

- 基于 RAG 的 district workflow
- commute calculation
- saved compare history
- map-backed commute support

## 产品希望成为什么

RentWise 并不是一个单纯的字段提取器，也不是通用聊天助手。

当前产品方向是：

- 候选房源池决策工作区
- 以 compare 为核心的 shortlist 工具
- agent-assisted explanation layer

期望给用户提供的价值是：

- 帮助用户判断哪些房源值得继续投入注意力
- 让不确定性可见，而不是被掩盖
- 用自然语言解释 tradeoff
- 把“我有几个选择但不知道下一步怎么办”转化为可执行流程

## 仓库结构

```text
RentWise/
  backend/
  frontend/
  legacy/
  docs/
```

关键目录说明：

- `backend/`: API、数据库模型、OCR pipeline、assessment services、Alembic migrations、tests
- `frontend/`: Next.js 页面路由、API client、auth helpers、candidate/project 页面
- `docs/`: 设计说明、presentation notes、roadmap 材料
- `legacy/`: 仅保留作参考的原型代码与文档

## 关键模块与文件

### Backend

- `backend/app/main.py`
  - FastAPI 入口和 startup hooks，包括 OCR 预热
- `backend/app/core/config.py`
  - 环境变量配置；secret 只从 `.env` 或进程环境读取
- `backend/app/db/models.py`
  - users、projects、candidates、assessments、source assets 等 SQLAlchemy 模型
- `backend/app/api/v1/auth.py`
  - 注册与登录接口
- `backend/app/api/v1/projects.py`
  - project 创建 / 更新 / 删除逻辑，包括预算修改
- `backend/app/api/v1/candidates.py`
  - candidate 导入、列表/详情、编辑、删除、重新评估
- `backend/app/api/v1/dashboard.py`
  - project 级 dashboard 的响应组装
- `backend/app/api/v1/comparison.py`
  - compare workflow 接口
- `backend/app/services/candidate_import_background_service.py`
  - 应用内后台 OCR 与 assessment pipeline
- `backend/app/services/ocr_service.py`
  - OCR provider 抽象、结果归一化与后端选择
- `backend/app/services/file_storage_service.py`
  - 上传存储抽象；开发环境当前写入 `backend/storage/`
- `backend/app/services/extraction_service.py`
  - 基于 LLM 的结构化提取
- `backend/app/services/cost_assessment_service.py`
  - 成本相关规则、缺失项与置信度输出
- `backend/app/services/clause_assessment_service.py`
  - 租期 / 维修责任 / 入住时间等条款语义判断
- `backend/app/services/candidate_assessment_service.py`
  - overall recommendation、completeness、next action
- `backend/app/services/comparison_service.py`
  - shortlist grouping 与 compare explanation
- `backend/app/services/comparison_briefing_service.py`
  - compare 页的 LLM briefing 与 fallback
- `backend/app/services/benchmark_service.py`
  - 基于本地结构化数据的 SDU benchmark 查找
- `backend/app/data/benchmark_sdu_rents.json`
  - 版本化的 SDU 中位租金 benchmark 数据
- `backend/alembic/`
  - schema migration 历史
- `backend/tests/`
  - 主要流程的单元与集成测试

### Frontend

- `frontend/app/page.tsx`
  - 落地页
- `frontend/app/login/page.tsx`
  - 登录页
- `frontend/app/projects/page.tsx`
  - project 列表页
- `frontend/app/projects/[id]/page.tsx`
  - project dashboard、candidate queue、预算编辑
- `frontend/app/projects/[id]/import/page.tsx`
  - 文本 + 图片混合导入页与处理状态提示
- `frontend/app/projects/[id]/candidates/[candidateId]/page.tsx`
  - candidate detail、重新评估、OCR evidence、删除
- `frontend/app/projects/[id]/compare/page.tsx`
  - compare 工作区与 LLM briefing
- `frontend/lib/api.ts`
  - 浏览器端 API client 与错误处理
- `frontend/lib/types.ts`
  - 前端共享类型
- `frontend/lib/auth.ts`
  - token 存储辅助

## Backend 启动

```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

如果要在 candidate import 中使用图片 OCR，当前默认 runtime 已切到 `rapidocr_onnxruntime`，它更适合 Windows + CPU 本地开发，也更贴近截图类导入场景。如果你显式把 `OCR_PROVIDER` 改成 `paddleocr`，则需要另外在 `backend\\venv` 中安装 `paddleocr` 与 `paddlepaddle`。

如果你的本地 PostgreSQL 数据库是更早期通过 `create_all()` 启动路径创建的，那么切换到 Alembic 前需要先执行一次：

```bash
alembic stamp head
```

之后持续使用：

```bash
alembic upgrade head
```

`stamp head` 只会对齐 Alembic revision 记录，并不会补建缺失表或列。

Backend API:

- `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

## Frontend 启动

```bash
cd frontend
npm install
copy .env.local.example .env.local
npm run dev
```

Frontend:

- `http://localhost:3000`

## 环境变量

### Backend

必填：

- `SECRET_KEY`
- `DATABASE_URL`
- `LLM_PROVIDER`

可选 provider 设置：

- `GROQ_API_KEY`
- `GROQ_MODEL`
- `OLLAMA_HOST`
- `OLLAMA_API_KEY`
- `OLLAMA_MODEL`
- `BACKEND_CORS_ORIGINS`
- `FILE_STORAGE_PROVIDER`
- `LOCAL_UPLOAD_ROOT`
- `OCR_PROVIDER`
- `PADDLEOCR_LANG`
- `OCR_USE_DOC_ORIENTATION`
- `OCR_USE_DOC_UNWARPING`
- `OCR_USE_TEXTLINE_ORIENTATION`
- `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK`
- `LOW_MEMORY_MODE`
- `OCR_PREWARM_ON_STARTUP`
- `OCR_MAX_IMAGE_DIMENSION`

说明：

- 当前 backend 运行时依赖 PostgreSQL。
- SQLite 不再是当前 schema 的受支持运行时。
- API key 不再硬编码在 `backend/app/core/config.py` 中；provider secret 必须来自 `backend/.env` 或进程环境。
- 如果使用 Neon 或 Render 托管 Postgres，backend 最理想的 `DATABASE_URL` 形式仍是 `postgresql+asyncpg://...?...ssl=require`。当前配置层也会自动把常见的 `postgres://...` 和 `postgresql://...` 连接串归一化成 `asyncpg` 兼容格式。
- `BACKEND_CORS_ORIGINS` 支持逗号分隔字符串，例如 `http://localhost:3000,http://127.0.0.1:3000`，部署到云端后应改成你的 Vercel 域名。

### Frontend

- `NEXT_PUBLIC_API_URL`

默认值：

- `http://localhost:8000`

注意：

- 在 Vercel 中，这个环境变量的值必须只是纯后端 URL，例如 `https://rentwise-api.onrender.com`
- 不要把 `NEXT_PUBLIC_API_URL=https://rentwise-api.onrender.com` 这种整行赋值文本原样粘进 value 输入框

## 部署说明

当前部署假设：

- database: PostgreSQL，包括 Neon 这类托管数据库
- backend: FastAPI 进程 + 应用内后台 worker
- frontend: Next.js 应用
- OCR runtime: 默认 RapidOCR + ONNX Runtime，可选 PaddleOCR fallback

当前生产 caveat：

- candidate OCR 和 assessment 仍运行在应用内后台 worker 中，还不是外部任务队列
- 本地文件存储只适合开发环境。上传层虽然已经抽象，但线上部署应改为 object storage，而不是依赖 backend 本地文件系统
- OCR 依然会消耗一定 CPU，但默认链路现在优先选择更轻量、启动更快的 RapidOCR。当前代码仍会在 OCR 前做预热和大图缩放；如果你显式改回 PaddleOCR，就是用更高延迟换取另一套识别行为。

推荐的生产方向：

1. 使用 Neon 或其他托管 PostgreSQL
2. 上传截图走独立 object storage
3. backend 通过正式环境变量部署
4. frontend 部署到兼容 Next.js 的平台
5. 当导入量变大后，再从应用内后台任务升级到外部队列

当前代码库更推荐的托管组合：

1. frontend 部署到 Vercel，项目根目录设为 `frontend/`
2. backend 部署到 Render，Python Web Service 根目录设为 `backend/`
3. database 使用 Neon，并保持 `asyncpg` 连接串
4. 在 Vercel 中把 `NEXT_PUBLIC_API_URL` 指向 Render 的后端域名
5. 在 Render 中把 `BACKEND_CORS_ORIGINS` 设置为你的 Vercel 正式域名，必要时再补 preview 域名
6. 把 Render 的 Python runtime 固定到 3.11，避免 `pydantic-core` 在 Python 3.14 下回退到 Rust 源码编译

推荐的 Render backend 命令：

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

推荐的 Render Python runtime：

```text
3.11
```

仓库现在改为在根目录提供 `.python-version`，内容为 `3.11.11`，这更符合 Render 的仓库级 Python 版本声明方式。如果某个 Render 服务仍未正确识别，就在 Render 环境变量里显式补上 `PYTHON_VERSION=3.11.11` 作为最终覆盖。

建议的云端环境变量：

- Vercel: `NEXT_PUBLIC_API_URL=https://<your-render-service>.onrender.com`
- Render: `APP_ENV=production`
- Render: `BACKEND_CORS_ORIGINS=https://<your-vercel-app>.vercel.app`
- Render: `DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>/<db>?ssl=require`
- Render: `SECRET_KEY=<strong-random-secret>`
- Render: `LLM_PROVIDER=groq`
- Render: `GROQ_API_KEY=<your-groq-key>`
- Render: `OCR_PROVIDER=rapidocr`
- Render: `LOW_MEMORY_MODE=true`

当前云端存储 caveat：

- 现在的本地存储适合短周期 demo，因为上传后会立刻进入 OCR，但在 Render 这类临时文件系统上并不提供稳定持久化。
- 如果你需要跨重启或跨部署保留原始截图，就应该把 candidate uploads 迁移到 object storage，再把这套部署当作正式生产环境。

## 发布前与数据安全检查清单

推送到 GitHub 前必须确认：

- `backend/.env`、`frontend/.env.local` 以及任何根目录 `.env` 文件都被忽略且未被 track
- `backend/storage/` 已被忽略
- 不提交模型缓存、日志、虚拟环境、构建产物
- 不提交导出的课程 HTML 或本地 scratch 文件
- 任何曾出现在聊天、文档、截图、终端里的 credential 都应视为已暴露并完成轮换
- `.env.example` 中只保留占位符，不保留真实值
- 每次 push 前都检查 `git status`

必须保持在 git 之外的敏感本地文件：

- `backend/.env`
- `frontend/.env.local`
- `backend/storage/`
- `frontend/node_modules/`
- `frontend/.next/`
- 本地日志、缓存和生成产物

## 产品说明

- `legacy/streamlit_app/` 不是当前产品入口。
- 数据库 schema 由 Alembic 管理。
- 在新环境中启动 backend 前，需要先执行 `alembic upgrade head`。
- 如果你之前已有旧版启动路径创建的表，需要先执行一次 `alembic stamp head` 让 Alembic 对齐，再持续使用 `alembic upgrade head`。
- 如果看到 `column candidate_extracted_info.suspected_sdu does not exist` 这类错误，说明代码已经领先于本地数据库 schema，请在 `backend/` 中执行 `alembic upgrade head`。
- Project 删除通过数据库 cascade rules 同时清理相关 candidates、assessments 和 investigation items。
- Candidate 编辑当前在 candidate detail 页面提供。
- Compare 结果当前按需生成，不做持久化。
- Dashboard 可以根据 shortlist 形态给出 suggested compare set。
- Candidate detail 可以直接打开围绕该 candidate 的 compare workspace。
- Compare 页面包含 LLM-assisted briefing，并在模型失败时有 deterministic fallback。
- Candidate detail 把结构化字段和 source text 放在 supporting sections，让决策阅读优先。
- Dashboard 将 open questions 聚合为 grouped investigation checklist，而不是对每个 listing 反复警告。
- Frontend API 错误处理会区分真实后端错误和真实网络错误，因此 candidate edit/save 的报错更可操作。
- Repair responsibility assessment 现在采用 “LLM 先归一化 + 保守规则语义判断” 的方式；像 agency-supported repairs 这类信号会被视为正向但仍未确认，而不是被压扁成 generic unknown。
- Lease term 和 move-in timing 也采用相同模式：LLM 先归一化文本，再由保守规则判断它更像是 standard、rigid、unstable、fit、uncertain 还是 mismatched。
- extraction 现在会把 listing、聊天、备注和 OCR 当成一个带来源标签的证据包来综合判断。后续聊天或备注中的补充信息可以修正当前可用结论，而不是因为不在原始 listing 里就被忽略。
- candidate extraction 现在新增了轻量的 `decision_signals` 层，用来保留 commute 优势、信任风险、信息冲突、共用卫浴、楼宇配套等不适合做固定 canonical 字段、但对决策有价值的信号。
- 像“开学时入住”这类相对时间，或“学校宿舍，包维修”这类明确备注，现在会被视为可用决策证据，而不是一律退回成 generic unknown 提示。
- Candidate detail 现在会把内部 clause state 翻译成用户能读懂的解释，而不是直接暴露 `rigid`、`uncertain` 这类内部标签。
- Candidate import 支持在同一张表单中混合提交文本和多张图片。上传截图会先经过存储抽象层，在开发环境中落到本地，然后 OCR 文本会并入正常的 `combined_text` 分析链路。
- 开发环境下上传文件保存在 `backend/storage/`，该目录必须排除在 git 外。
- OCR import 会单独保存 source-asset metadata，而不是把所有 OCR 结果直接塞回 extracted fields，这样异步 candidate pipeline 就能复用 OCR evidence，同时避免 import 过程中的 lazy-load 问题。
- 如果 image-only import 得到空 extraction 结果，先确认 `backend\\venv` 中安装了当前配置对应的 OCR runtime。默认配置需要 `rapidocr_onnxruntime`；如果使用 Paddle fallback，则还需要 `paddleocr` 与 `paddlepaddle`。后台导入失败现在会把真实错误写回 candidate，detail 页面可以直接显示真实 OCR failure reason，而不是伪装成网络错误。
- Candidate import 现在改为应用内后台任务处理，而不是把整条 OCR + assessment 链路阻塞在一个请求里。导入页会快速返回，跳到 candidate detail，detail 页面轮询后台进度。
- Candidate import 现在会在启动后台 OCR 任务前先提交 queued candidate，这样可以避免云端环境里新 session 还看不到刚创建 candidate 记录而导致后台任务假性卡住。
- 初次 queued import 响应会返回一个占位 candidate 状态，而不是强行加载 assessment 关系，因此不会再在 response serialization 时因 lazy-load 崩掉。
- Project dashboard 在任一 candidate 仍处于 processing 时也会轮询，所以 OCR 完成后 candidate 可以自动进入 priority queue，而不需要手动刷新。
- 仍在 processing 的 candidates 会被明确显示为后台工作，而不是空白低信息卡片；在 assessment 完成之前，它们也会暂时排除在 compare selection 外。
- OCR 默认会在 backend startup 时预热，因此无论使用哪种受支持的 provider，第一个用户导入都不必完整承担冷启动成本。
- 上传截图在 OCR 前会缩放到可配置的最大尺寸，这对超大手机截图能明显降低 CPU 延迟，同时不改变混合文本 + 图片工作流。
- 如果你用的是小规格云实例，比如低配 Render 服务，可以把 `LOW_MEMORY_MODE=true` 打开。它会关闭 OCR 预热、进一步收紧 OCR 前缩放，并在每次 OCR 完成后释放共享 OCR engine，尽量减轻空闲 RAM 压力。
- `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK` 仍保留给可选的 Paddle fallback 使用，并会在 `paddleocr` import 之前写入 `os.environ`，因此把它写进 `backend/.env` 就能真正抑制 model-hoster connectivity check，不需要每次手动在终端 export。
- Candidate processing stages 当前包括：
  - `queued`
  - `running_ocr`
  - `extracting`
  - `completed`
  - `failed`
- 当前后台任务是有意设计成“应用内后台 worker”，不是外部队列。它已经显著改善体感速度，但任务仍然依附于正在运行的 backend 进程。
- Candidate detail 支持带确认框的永久删除，project workspace 支持 inline budget updates。
- Candidate 删除既可以在 candidate detail 中完成，也可以直接在 dashboard 的 candidate list 中删除。
- 修改 project budget 后，会刷新已有已完成 candidate 的预算相关 assessment，保证 dashboard 和 candidate recommendation 与新预算上限一致。
- Candidate detail 会展示每个上传文件的 OCR evidence，便于直接检查 OCR 实际读到了什么，而不是先怀疑下游 extraction。
- Candidate detail 现在新增了一个按需触发的 LLM outreach draft，会把当前 blocker 转成 2 到 3 个适合发给房东 / 中介的问题，并附上一条简短英文消息草稿。它默认不常驻展开，避免对只比较少量房源的用户造成额外信息负担。
- Candidate detail 现在采用更轻的 decision workspace 组织方式：主界面聚焦当前决策，benchmark note 和更深的 evidence panel 默认折叠，只有在需要核查时再展开。
- Import 页面使用自定义上传按钮，而不是浏览器原生文件按钮标签，从而避免在英文界面中夹杂系统原生其他语言文案。
- 如果 PaddleOCR 启动时仍看到 Windows shell 报告某个 pattern 或 file not found，那不是 RentWise 应用本身输出的日志，而更像是本地 shell 或更底层依赖层发出的消息。
- Extraction 归一化已做类型兼容：`normalize_value` / `normalize_optional_value` / `parse_bool_value` 现在可以接受任意 LLM 返回类型（字符串、整数、浮点、布尔、null），像 `size_sqft: 500` 这种数值返回不再会让 reassess 报 `'int' object has no attribute 'lower'`。
- 修改 project 预算时，会在 pipeline reassessment 之前先 eager-load 每个 candidate 的 `source_assets`、`extracted_info` 以及各项 assessment 关系，避免异步 lazy-load 触发 `MissingGreenlet` 并让整笔事务回滚导致预算改动丢失。
- Compare 的 key differences 概述现在会把当前 leader 从 “仍有不确定性 / 仍不稳定 / 仍需更多证据” 的列表里剔除，避免出现“A 是最清晰的 …… A 仍有隐藏成本风险”这种自相矛盾的文案。
- `POST /api/v1/auth/login` 同时接受 `application/json`（前端使用）与 `application/x-www-form-urlencoded`（字段名 `username` 或 `email`），因此 Swagger 的 “Authorize” 按钮以及标准 OAuth2 客户端都能直接工作，不再被 Pydantic 当成非法 body 拒掉。

## UX 现实检查

当前产品最大的风险之一仍然是信息过载。

代码现在已经能够生成：

- structured extraction
- cost assessment
- clause assessment
- candidate assessment
- compare grouping
- compare explanation
- next-step guidance

这些能力有价值，但也带来风险：

- 输出过多结构化信息
- 不同 section 重复解释
- 页面上太多内容同时争抢注意力

因此当前方向是：

- 保持决策路径清晰可见
- 把 supporting details 往下放
- 减少跨 section 的重复解释
- 让 explanation 服务于决策，而不是淹没决策

## Phase 状态

### Phase 1

Phase 1 基本完成：

- auth
- projects
- candidate import and reassessment
- dashboard
- candidate detail
- project deletion
- candidate editing
- candidate deletion
- project budget editing
- Alembic migrations
- 主 backend 流程的测试覆盖

### Phase 2

Phase 2 compare MVP 已激活：

- 手动选择 compare set
- grouped shortlist comparison
- compare explanation 与 tradeoff 输出
- dashboard 与 candidate detail 的 compare context
- LLM-assisted compare briefing

### Phase 2.5

Phase 2.5 部分激活：

- compare 页面已有 agent-style briefing layer
- 这一阶段的下一步更可能是更强的 guidance 和 evidence-backed explanation

## Evidence、Benchmark 与 Commute Roadmap

下一阶段的 evidence work 不应被简单当成一个笼统的 “RAG 项目”。

它应拆成三条线。

### 1. Benchmark Layer

来源：

- `document/SDU_median_rents.pdf`

当前结论：

- 该 PDF 可以提取出文本
- 但内容特指 subdivided units
- 并且文档本身也声明它只适合作 general reference

这意味着：

- 它**不能**被当成通用市场租金真值
- 它应当成为一个**结构化 benchmark layer**，而不是 generic vector RAG
- 它只适合作为狭义的 SDU benchmark，而不是所有 listing 的普适 district rent benchmark

推荐用途：

- candidate detail 中的 cost context
- compare 中的 support note
- dashboard 中轻量 benchmark hint

推荐顺序：

1. 提取 district-level benchmark data
2. 以 structured data 存储
3. 构建 `BenchmarkService`
4. 用“规则优先、LLM 支持”为 candidate 判断是否 likely SDU
5. 仅在 candidate type 和上下文适合时使用 benchmark

当前实现状态：

- benchmark evidence MVP 已在 candidate detail 和 compare 中启用
- benchmark 数据当前来自版本化本地结构化文件，而不是数据库表
- likely SDU 的判断已采用规则 + extraction 支持

推荐 benchmark 规则：

- 第一版可以先用 district 级别匹配
- 只有 candidate 有 district 时才显示 benchmark
- 只有 candidate likely SDU 时才显示 benchmark
- benchmark 必须带明确 disclaimer：
  - 仅针对 subdivided units
  - 仅作 general reference
  - 不代表 property-specific truth

不要做的事：

- 不要把这个 benchmark lookup 路径做成 RAG
- 不要默认对每个 listing 都展示 benchmark
- 不要把 benchmark 数据直接喂进主 assessment 或隐藏 compare score

### 2. Tenancy Evidence Layer

来源：

- `document/AGuideToTenancy_ch.pdf`

当前结论：

- 简单 PDF 提取拿不到可用文本
- 这强烈说明该 PDF 主要是扫描图像或图文混排

这意味着：

- 该来源**暂时不适合**直接做 text RAG
- OCR 是前置条件
- 即使 OCR 后，也更适合作 narrow explanation-support retrieval，而不是 main scoring engine

OCR 后的推荐用途：

- candidate detail 的 clause explanation
- compare briefing 的 evidence note
- 未来的 agent guidance support

推荐顺序：

1. 先加 OCR
2. 手动检查 OCR 质量
3. 文本质量足够后再 chunk
4. 只做窄范围 explanation-support retrieval

当前 OCR 集成形态：

- OCR 属于 candidate import 流程的一部分，而不是独立工具
- 用户可以一次上传多张 listing/chat/contract screenshot
- OCR 输出既会作为 source evidence 保存，也会并入 extraction 与 assessment 共用的文本 bundle
- 文件存储已经做了抽象，因此开发环境可以继续用本地文件系统，未来要迁移到 object storage 时无需重写分析主链路
- 当前 backend 通过统一的 OCR service 抽象路由 OCR，因此可以把 `rapidocr` 作为默认快速路径，同时保留 `paddleocr` 作为显式 fallback，而不需要改 import pipeline
- 默认 OCR 设置已经偏向“截图场景下的速度优先”，会关闭 document orientation、unwarping、textline-orientation，除非你在 backend 环境变量中重新打开
- Import 不再等待 OCR 与 LLM assessment 在一个请求里完成。系统会先创建 candidate，再由应用内后台任务继续 OCR 与 assessment，detail 页面轮询显示进度
- 当前 OCR 性能现在主要通过三种方式改善：默认 provider 改为基于 ONNX Runtime 的 RapidOCR、backend startup 时预热 OCR engine，以及在 OCR 前缩放大图。
- 如果你仍使用可选的 Paddle fallback，且启动时看到 Windows shell 报某个 pattern 或 file not found，那并不是 RentWise 代码本身发出的日志，更可能来自 Windows shell 或底层依赖层

RAG 在这里可能的价值：

- 解释为什么某个 clause 或 tenancy issue 重要
- 为 candidate detail 提供 evidence note
- 支撑 compare briefing 的 rationale

RAG 在这里不太擅长的事：

- 替代 structured extraction
- 提供稳定法律结论
- 成为所有住房问题的通用问答引擎

### 3. Commute Support Layer

当前方向：

- 已批准的第一形态是 single-destination commute support
- commute 仍然应是 support evidence，而不是隐藏 scoring engine

Project 级需要的模型：

- commute enabled flag
- destination label
- destination query
- commute mode
- max commute minutes

Candidate 级需要的模型：

- address text
- building name
- nearest station
- location confidence
- location source

推荐交互：

- project commute setup 应该是 optional，而不是 project 创建时强制要求
- candidate location 应该先由 extraction 生成草稿，再允许用户校正
- 只有 destination 和 location 输入足够可靠时，candidate detail 和 compare 才展示 commute evidence

推荐顺序：

1. 增加 project-level commute configuration
2. 增加 candidate-level location evidence
3. 更新 extraction 以草拟 location evidence
4. 允许用户在 candidate editing 中修正 location evidence
5. 增加窄范围 map-backed `CommuteService`
6. 在 candidate detail 与 compare 中展示 commute evidence

不要做的事：

- 不要把 district-only data 当作 commute estimation 的充分输入
- location model 还没建立前，不要急着接地图能力
- 第一版不要把 commute minutes 直接计入主 compare score

## 当前最推荐的团队顺序

如果团队希望在不把产品做臃肿的前提下继续推进，最合适的顺序是：

1. 继续减少当前 UI 中的信息重复
2. 把中位租金 PDF 做成结构化 SDU benchmark layer
3. 决定 tenancy guide 的 OCR 是否值得依赖成本；只有 OCR 质量足够时才做窄范围 retrieval
4. 先补齐 project 与 candidate 的 location model，再上 commute

这是目前最诚实的推进顺序。

它能让决策工作流保持稳定，同时只在真正有价值的地方增加 evidence。

## 测试

本地快速测试：

```bash
cd backend
python -m unittest discover -s tests -p "test_*.py"
```

基于真实 PostgreSQL 的集成流：

```bash
cd backend
set RUN_DB_INTEGRATION=1
.\venv\Scripts\python.exe -m unittest tests.integration.test_db_flow
```

该 DB 集成测试覆盖：

- register
- create project
- import candidate
- fetch dashboard

当前测试集也覆盖：

- 行动导向的 priority ranking
- investigation checklist generation
- 顶层 candidate recommendation
- compare grouping 与 compare explanation 输出
- compare route response shape
- compare briefing fallback behavior
- grouped investigation checklist behavior
- OCR service parsing
- benchmark lookup behavior

## 组内 Review 备注

目前有两条产品层面的事实值得在 review 时持续记住：

1. 输出更多分析结果，不等于决策一定更好。
   - 产品最强的时刻，是用户在几秒内就能知道下一步应该做什么。

2. 外部 evidence 应该支撑信任，而不是制造虚假的精确感。
   - benchmark 必须保持范围克制
   - tenancy guide support 应等待 OCR 质量达标
   - commute 应等待真实 location model 建立后再做
