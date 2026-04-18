# RentWise 技术亮点（简历 / 汇报）

面向 10 分钟左右的技术汇报 —— 4 个独立亮点，每项一张流程图 + "为什么
这么选"的权衡说明。完整架构请参见 README；**每个决策背后的长期原因**
参见 [`design-notes.md`](./design-notes.md)。

| # | 亮点 | 核心价值 |
|---|------|----------|
| 1 | 多模态 OCR 流水线 | 截图 / 照片 / 聊天记录统一入 LLM 提取管线 |
| 2 | LLM tool-use 通勤地址解析 agent | 把 geocoder ladder 的决策权交给模型，三道闸门防幻觉 |
| 3 | 本地 BM25 + LLM rerank 法条 RAG | 中文法律文本不用向量，页码可追 |
| 4 | Eval 质量守护基线 | pytest.mark.eval + field-level floor，阻断 prompt 漂移 |

---

## 1. 多模态 OCR 流水线

房源信息来源极散：中介的图文混贴、用户手机截屏、聊天记录、PDF 扫描
件。统一入口是必须 —— 下游的 LLM 提取器只接受纯文本。

```
┌────────────────────────────────────────────────────────────────┐
│                  OCR 提取流水线                                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│   用户上传 (text + image 多上传)                               │
│         │                                                      │
│         ▼                                                      │
│   ┌──────────────────────────────────────────┐                 │
│   │  OCRService (provider-switchable)        │                 │
│   │  • paddleocr   — 本地、中文优                │                 │
│   │  • rapidocr    — 轻量 onnxruntime         │                 │
│   │  • mistral     — 云端 fallback            │                 │
│   │  • ocr_space   — 保留选项                 │                 │
│   └──────────┬───────────────────────────────┘                 │
│              │ 每张图 → OCRResult(status, text)                │
│              ▼                                                 │
│   ┌──────────────────────────────────────────┐                 │
│   │  合并为 combined_text                     │                 │
│   │  （与用户原文、对话粘贴一起拼接）         │                 │
│   └──────────┬───────────────────────────────┘                 │
│              ▼                                                 │
│   ┌──────────────────────────────────────────┐                 │
│   │  LLM JSON 提取（Groq / Ollama）           │                 │
│   │  → 租金、押金、面积、条款 …              │                 │
│   └──────────────────────────────────────────┘                 │
│                                                                │
│   租务指南 PDF 走独立分支：                                    │
│   PyMuPDF 栅格化 2× → rapidocr → BM25 索引（亮点 3）           │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**为什么这么选**

- **Provider 切换可插拔**。`backend/app/services/ocr_service.py:38-60`
  的 `_shared_engines` 按 `OCR_PROVIDER` lazy load，单线程锁包裹初始化
  —— 同一 engine 在所有请求复用，冷启动只付一次。
- **PaddleOCR 为默认**：中文细笔画（"釐"、"傢俬"、"按揭"）识别率明显
  优于 Tesseract，且完全离线可跑，适配本项目 "课程 Ollama endpoint 已
  停用、要能本地复现" 的约束。
- **为什么还保留 rapidocr / mistral**：低内存部署用 rapidocr，开发调
  试用 mistral 云端做对照。`LOW_MEMORY_MODE` 下 `_release_engine_if_needed`
  会在请求结束后释放 engine，避开 Paddle 的常驻内存占用。
- **warmup API**：`OCRService.warmup()` 在 FastAPI lifespan 里异步调
  一次，第一个真实请求不再承担 ~3s 的模型加载。

---

## 2. LLM tool-use 通勤地址解析 Agent

### 2.1 动机

原方案是硬编码 geocoder ladder：ALS fail 再 Amap geocode，再 Amap POI。
ladder 顺序由工程师拍脑袋订，对所有候选一视同仁 ——
`nearest_station = "Mong Kok East MTR station"` 明明最适合 ALS，却可能
因 ladder 先跑别的 tool 而多走两步弯路。

**把 ladder 换成 LLM tool-use agent，地址解析策略的选择本身交给模型**。

### 2.2 状态机结构

```
┌──────────────────────────────────────────────────────────────┐
│              Commute Resolver Agent 工作流                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   candidate_facts                                            │
│   (address_text, building_name, nearest_station, district)   │
│         │                                                    │
│         ▼                                                    │
│   ┌──────────────┐  tool_call   ┌────────────────────────┐   │
│   │  plan (LLM)  │─────────────▶│  execute               │   │
│   │              │              │  als_geocode /         │   │
│   │              │◀─────────────│  amap_geocode /        │   │
│   │              │ observation  │  amap_poi_search /     │   │
│   └──────┬───────┘              │  mtr_station_lookup    │   │
│          │                      └────────────────────────┘   │
│          │ finish / give_up / max_steps                      │
│          ▼                                                   │
│       END (resolved_coords | give_up_reason)                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

两节点 LangGraph StateGraph（`commute_resolver_agent.py:226-243`）。
Agent 每步只做一件事：`plan` 让 LLM 看历史 observation、产出**一个**
tool_call；`execute` 跑 tool、把结果追加到 observation 历史。循环到
`finish` / `give_up` / `MAX_STEPS` 任一触发为止。

### 2.3 五个工具

| 工具 | 作用 | LLM 何时选它 |
|------|------|--------------|
| `als_geocode` | HK 政府 ALS | 英文 HK 地名、屋苑、MTR 站 |
| `amap_geocode` | 高德 geocoding | 中文 HK 地址、街号 |
| `amap_poi_search` | 高德 POI 关键词 | 楼宇 / 地标名无标准地址 |
| `mtr_station_lookup` | 本地 MTR 站台坐标查表 | `nearest_station` 明确是地铁站 |
| `finish` / `give_up` | 终止 | 成功拿到坐标 / 无解 |

### 2.4 防幻觉的三道闸门

1. **HK bbox 闸门** — `commute_tools.py:60-83` 的 `_observation()` 里
   每个工具返回前过 `in_hk(coords)`，越界坐标直接标记 `accepted: false,
   reason: "out_of_hk_bbox"`。LLM 从头到尾**看不到越界坐标**，无法误
   引用到 finish 里。
2. **finish 反幻觉校验** — `commute_resolver_agent.py:260-271` 的
   `_coords_from_observations`：LLM 调 `finish([lng, lat])` 时，agent
   比对这对坐标**是否真的出现在过往 accepted observation 里**（`1e-4`
   容差 ≈ 10m 量级）。失败则写 `give_up_reason =
   "finish_coords_not_from_observation"` 退出。
3. **MAX_STEPS 兜底** — 防跑偏无限循环。

### 2.5 `mtr_station_lookup`：一次真实 bug 复盘

**症状**：候选 `nearest_station = "Sha Tin MTR station"`，UI 却显示
"大围 → 金钟"。

**根因**：ALS 对 "Sha Tin" 这类宽泛词返回了附近 POI（沙田新城市广
场），坐标物理上反而更贴近**大围站**，Amap 路径规划把起点 snap 到了
大围。

**修复**：加一个**本地确定性查表工具** —— `backend/app/data/
mtr_stations.json` 存了 ~95 站的**站台中心坐标**（非出入口 / 非商场），
由 `scripts/build_mtr_stations.py` 对每条坐标用 Amap POI
(`types=150500` 地铁站) 做 build-time 距离校验，漂移 > 400m 直接报
错。

**关键设计取舍**：

- **为什么不在 runtime 再查一次 API** — API 回来的坐标会 drift（ALS
  偶尔返回楼宇出入口），我们要的是站台**唯一**坐标。查表还省 300-800ms
  网络调用。
- **为什么查表必须带站点标记** — 沙田 / 湾仔 / 观塘 同时是站名和**区
  名**。若查表接受裸 `"沙田"`，agent 会把 `district` 字段误塞进来当
  站名用 —— 错得更离谱。service 层拒绝裸名、prompt 明令
  `NEVER pass district into mtr_station_lookup`，双保险。
- **为什么不引 opencc** — 90 站手工列简体 alias 更稳、可审计，避免
  版本依赖 + 转换边界 case（部分字在特定上下文不该转）。

### 2.6 对照组保留

旧的确定性 ladder 留在 `CommuteService._deterministic_resolve`，通过
`COMMUTE_AGENT_ENABLED=false` 回退。eval 里可以直接对比 "agent 选工
具" vs "工程师写死 ladder" 的 origin-station 命中率差异。

---

## 3. 本地 BM25 + LLM rerank 法条 RAG

### 3.1 为什么要做 RAG

RentWise 的 clause assessment 会标出"需要核实 / 高风险"条款（租客承
担所有维修、生约死约不明、入住时间冲突），但**只告诉用户"需要核
实"是不够的** —— 用户需要知道：

- 条例到底怎么写？
- 我这种情况，法律是站我这边吗？

"让 LLM 凭训练数据复述《业主与租客（综合）条例》"不靠谱：HK 法条训练
语料稀疏、LLM 容易幻觉，而条例原文和页码是可引用证据，改写一次就失
去了权威性。

→ 用 RAG 把条例原文按页码引用回来，**不改写、只引用**。

### 3.2 为什么不用向量检索

源文档 `document/AGuideToTenancy_ch.pdf` 是中文法律文本，关键词密度
非常高（"維修"、"押金"、"生約"、"死約"、"打釐印"）。

| 检索策略 | 优点 | 在本场景的问题 |
|---------|------|---------------|
| 向量 (dense) | 捕捉语义近似 | 需要中文 embedding 服务；22 chunk 用不上语义召回优势；依赖 Ollama / 云 API |
| BM25 (sparse) | 无外部依赖、纯本地 | 对同义词不敏感（但法律术语有固定用词，反而是优势） |

课程 Ollama endpoint 已经停用，项目定位是"本地可跑、无云依赖"。
BM25 + jieba 就能吃下需求。

### 3.3 两阶段流水线

```
┌──────────────────────────────────────────────────────────────┐
│  离线 (build-time)                                           │
│  ───────────────                                             │
│  AGuideToTenancy_ch.pdf                                      │
│        │                                                     │
│        ▼   CID 编码扫描件无法直接抽文本层                    │
│  PyMuPDF render 2× (≈300dpi)                                 │
│        │                                                     │
│        ▼                                                     │
│  rapidocr_onnxruntime（复用亮点 1 的 OCR 引擎）              │
│        │                                                     │
│        ▼                                                     │
│  ~400 字 chunking + 80 字 overlap（按段落 / 标点对齐）       │
│        │                                                     │
│        ▼                                                     │
│  jieba cut_for_search → BM25Okapi tokenise                   │
│        │                                                     │
│        ▼                                                     │
│  tenancy_index.json (22 chunks, ~10KB, 入 git)               │
│                                                              │
│                                                              │
│  在线 (request-time)                                         │
│  ──────────────────                                          │
│  clause_risk_flag != "none"                                  │
│        │                                                     │
│        ▼                                                     │
│  话题 → seed query 映射                                      │
│     repair_tenant_heavy                                      │
│        → "維修 責任 業主 租客 損壞 維護"                     │
│        │                                                     │
│        ▼                                                     │
│  BM25 top-5 召回                                             │
│        │                                                     │
│        ▼                                                     │
│  LLM rerank → top-2 （失败回退 raw BM25 top-2）              │
│        │                                                     │
│        ▼                                                     │
│  ClauseAssessment.legal_references                           │
│  [{quote, source_page, chunk_id}, ...]                       │
└──────────────────────────────────────────────────────────────┘
```

### 3.4 关键参数的取舍

| 参数 | 选值 | 为什么 |
|------|------|--------|
| render dpi | 2× (≈300dpi) | 1× 下 CJK 细笔画漏字率明显上升；4× 边际收益小、文件膨胀 |
| chunk size | ~400 字 | 下限：BM25 IDF 在短 chunk 上分辨力差；上限：单条引用塞前端卡片会溢出、LLM rerank 被无关段落稀释 |
| overlap | ~80 字 | 约一句中文长度；避免关键句被切在两 chunk 边界双双排不上 |
| BM25 top-k | 5 | rerank 成本与召回余量的折中；3 漏召、10 prompt 太长 |
| rerank top-n | 2 | 前端紫色卡片最多显示两段 |

### 3.5 Rerank 与失败回退

Rerank 的作用是从 BM25 召回的 top-5 里挑出**和具体风险类型最相关**
的两段。例如"维修责任"召回的 5 段里有两段其实是押金章节，BM25 因共
享 "租客" 被召进来 —— 让 LLM 扫一眼就能筛掉。

```
You are filtering legal-text snippets for a Hong Kong rental risk.
Risk type: {risk_flag} / {level_label}
Here are 5 candidate paragraphs from the official tenancy guide:
...
Return JSON:
{
  "top_2": [
    {"chunk_id": "...", "quote": "...原文裁剪，最多 180 字..."},
    ...
  ]
}
```

**失败回退至关重要**：LLM 超时 / 非 JSON / 空 chunks 时，**不把整
个 clause_assessment 拖垮** —— 直接取 BM25 top-2 原文前 180 字兜底。
RAG 是加分项，不是必要条件。

### 3.6 前端落点

candidate detail 页面 `frontend/app/projects/[id]/candidates/
[candidateId]/page.tsx:1245` 渲染为紫色 "Ordinance reference" 卡片，
条件：`clause_risk_flag != "none"` 且 `legal_references` 非空。每条
引用附 `—《业主与租客（综合）条例》指南 p.{page}` 页码尾标。

---

## 4. Eval 质量守护基线

### 4.1 动机

所有 LLM 流水线都默认 **"跑得通 = 跑得对"**。但 prompt 微改、LLM 提
供商切换、golden fixture 新增，都会让提取结果悄悄漂移。unit test 验
证代码正确，**eval 验证模型表现**。

### 4.2 测试分层

位置：`backend/tests/evals/`。通过 `pytest.mark.eval` 门控，默认 skip。

| 测试 | 黄金集 | 守护什么 | 门控条件 |
|------|--------|---------|----------|
| `test_extraction_eval.py` | `golden_listings.jsonl` | 字段级提取准确率 | 需 `GROQ_API_KEY` |
| `test_commute_agent_eval.py` | `golden_commutes.jsonl` | agent 选工具、origin 命中 | 需 `GROQ_API_KEY` + `AMAP_API_KEY` |
| `test_tenancy_rag_eval.py` | 硬编码 8 条中文法律 query | BM25 top-3 页码召回 | **无需 key**，纯本地 |

**分层的意义**：tenancy RAG eval 不需要任何外部 key，CI / fork 都能
跑，索引产物损坏或 chunking 逻辑改动破坏召回会第一时间报警 ——
这是持续守护的"底座层"。需要 LLM 的两条更重但更昂贵，手动触发。

### 4.3 字段级 floor

每个测试脚本都带 `_FLOORS` 表，具体字段有自己的下限：

```python
# test_extraction_eval.py
_FLOORS = {
    "monthly_rent": 0.70,   # must-have, 格式规整
    "district":     0.70,   # must-have
    "deposit":      0.50,   # 多格式 ("2 months" vs "$30000")，宽容
    "lease_term":   0.50,
}
_OVERALL_FLOOR = 0.60
```

**Floor 不是 target，是 red line**。跌破 floor 意味着真实回归，必须
排查；调高 floor 表示质量提升。每次 eval 跑完 JSON 报告写入
`backend/tests/evals/reports/`，commit-to-commit diff 这些报告就是
**质量漂移曲线**。

### 4.4 Skip 规则

不是每条 eval 都需要 LLM：

```python
# conftest.py
_LLM_DEPENDENT_EVAL_MODULES = {
    "test_extraction_eval",
    "test_commute_agent_eval",
}
```

没有 `GROQ_API_KEY` 时，只 skip 需要 LLM 的测试；tenancy RAG 的 BM25
recall 测试仍然跑。

### 4.5 如何跑

```bash
cd backend
GROQ_API_KEY=... AMAP_API_KEY=... pytest -m eval -q
```

---

## 技术栈一览

| 层 | 技术 | 定位 |
|----|------|------|
| LLM | Groq `llama-3.3-70b-versatile` | 推理主力（Ollama 课程端点已停） |
| Agent | LangGraph StateGraph | tool-use 两节点状态机 |
| OCR | PaddleOCR / rapidocr_onnxruntime | 本地、中文优先 |
| 检索 | BM25Okapi + jieba | 法条 RAG 无云依赖 |
| 地图 | 香港 ALS + 高德 | HK bbox gate 兜底 |
| Eval | pytest.mark.eval + field floor | 防 prompt 漂移 |

---

## 相关文档

- [`design-notes.md`](./design-notes.md) — 设计决策与权衡（长期维护）
- [`../README.md`](../README.md) — 仓库结构、跑起来、部署
