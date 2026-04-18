# RentWise 设计决策与权衡

记录"读代码读不出来"的决策：产品理念、技术路线分叉的原因、failed
option 被砍掉的理由。代码本身 + `README.md` + Alembic 迁移就是
结构/字段/端点的权威来源；这里只记长期维护者需要知道的 **"当时为什么
这么选"**。

每条沿 **面对的问题 → 选了什么 → 为什么不选另一个** 三段式展开。

---

## 1. 候选池 vs 排名式列表：产品哲学

**问题**：HK 租客的痛点不是"找不到房源"，是"手里已经有几个候选，不
知道下一步怎么办"。传统租房产品把用户当"搜索-点击"的漏斗顶端，但真实
决策发生在漏斗的更下游。

**选了什么**：Candidate-pool decision workspace —— 用户手工维护一个
2–5 条的候选池，系统负责**补全信息、评风险、给行动建议**，而非"给你
推荐第 5 套房"。核心交互是 compare（分组 + briefing），不是 rank。

**为什么不选排名式**：打分排序是"假精确"。把多维偏好塞成单一分数会
丢掉用户实际在意的维度对比（"A 便宜但押金高、B 贵但生约死约稳"—— 排
序后只剩"A 得 7.8 分、B 得 7.6 分"）。决策分组 + 自然语言 briefing
保留了多维张力。

---

## 2. 三层评估体系：为什么拆成 cost → clause → candidate

**问题**：能否用一个 LLM 调用一次性给出"这个候选怎么样"的综合判断？

**选了什么**：拆成三层独立评估。
- `CostAssessment` —— 只看钱（租金、管理费、差饷、押金、代理费、预
  算拟合）
- `ClauseAssessment` —— 只看条款（维修责任、租期、入住时间）
- `CandidateAssessment` —— 综合前两者 + 用户偏好，决定 next action

**为什么不选一次性 LLM 综合评**：
- **可审计性**。现场演示或用户复盘时，"为什么判 needs_info"必须能
  定位到 cost 或 clause 某项；综合评做不到溯源。
- **可替换性**。cost 评估是纯确定性计算（规则引擎），不需要 LLM；
  clause 评估需要 LLM 理解自然语言但只 touch 有限几个字段；candidate
  评估是 LLM 综合判断。三层用不同技术最合适，混一起就只能都走 LLM。
- **回归隔离**。prompt 改动影响范围可控：改 clause prompt 不会污染
  cost 指标。配合第 7 节的 eval harness，field-level floor 才能成立。

---

## 3. 为什么选 LangGraph 做 agent

**问题**：Commute 地址解析需要"让 LLM 在多个 geocoder 里按候选特征
挑工具"。也就是 tool-use loop。最朴素的写法是一个 `while` + `if
tool_call: await execute`。

**选了什么**：LangGraph 两节点 StateGraph（plan / execute），状态是
一个 `TypedDict` 装着 `observations` / `pending_tool_call` /
`steps_taken` / `give_up_reason`。见
`backend/app/agent/commute_resolver_agent.py:226-243`。

**为什么不选裸 while loop**：
- **状态可检查**。单元测试直接断言某一步的 state，不用拆 while 内部
  变量。scripted planner + 固定 observation 链 = 完全确定性测试。
- **exit 路径统一**。LLM 自愿 `finish` / `give_up` 和 `MAX_STEPS` 兜
  底走同一个 END 分支，下游只处理一种结束 shape，而不是在 while 里
  挂多个 break。
- **可无依赖回退**。`_run_fallback_loop` 在 `langgraph` 不可用的环
  境下（如轻量测试镜像）手工跑同样节点转移，依赖缺失不阻断测试。

**权衡**：LangGraph 对这种 2 节点状态机是 overkill —— 但投资在 DX 上
是值得的。等未来加第三个 agent（例如 compare briefing 的 agent 版），
状态机基座已经在。

---

## 4. 为什么用异步后台处理 listing 导入

**问题**：候选导入的全链路是 OCR → LLM 提取 → cost 评估 → clause 评
估 → candidate 评估，典型耗时 **30–90 秒**。同步返回会超过 HTTP 默认
超时，前端也没理由阻塞用户。

**选了什么**：FastAPI BackgroundTasks + DB 状态机。导入请求立刻返回
`202 + candidate.id`，状态机在 DB 上流转：`queued → running_ocr →
extracting → scoring → completed`（失败写 `failed` + error）。前端
轮询 `GET /candidates/{id}`。

**为什么不选**：
- **同步处理**：请求超时、用户体验差。
- **Celery / RQ**：引入 Redis / broker / worker 三件套，对"用户量级
  = 毕设项目 + 少量协作者"过度工程化。BackgroundTasks 跑在同一
  event loop，够用。
- **状态机存内存（字典）**：服务器重启就丢失"在做什么"的信息；状态
  机**必须在 DB**，restart 后能 resume 查询。

**代价**：BackgroundTasks 不跨进程，多 worker 部署时每个 worker 只能
处理自己接收的任务 —— 当前规模完全可接受，未来如果上 k8s 再替换成
Celery 不难（状态机 shape 不变）。

---

## 5. 为什么 JWT 而非 Session

**问题**：用户登录认证方案选型。

**选了什么**：短期 JWT（7 天有效期），前端 localStorage 存储，每次
请求 `Authorization: Bearer <token>`。

**为什么不选 Session**：
- **无需 session store**。Session 需要 Redis / DB 或粘性会话；JWT 无
  状态、签名自验。对一个已经用 Postgres 的项目，多引一个 Redis 只为
  session 不划算。
- **SPA 天然对齐**。Next.js 前端分离部署，JWT 直接塞 Authorization
  header；Session cookie 跨域还要调 CORS + SameSite。
- **微服务友好（未来）**。Auth 逻辑下沉到 signing key，其他服务验签
  即可，不需要反查 session store。

**代价**：JWT 一经签发不能立刻撤销 —— 我们用 7 天 TTL + 重要操作可
强制重登做平衡。生产规模会引入 refresh token + 黑名单，但这超出毕设
范围。

---

## 6. Candidate 状态流转：为什么和 `user_decision` 分离

**问题**：Candidate 既有 AI 评估状态（`new / needs_info / follow_up /
high_risk_pending / recommended_reject / shortlisted`），也有用户的
主观决定（我想要 / 我不要）。两者关系？

**选了什么**：**完全独立字段**。`CandidateListing.status` 由 AI
pipeline 写，`user_decision` 由用户手工写。UI 上两者分两列展示。

状态流转决策逻辑：
```
new ──(AI 评估完)──▶ needs_info ──(用户补信息)──▶ follow_up
                         │                              │
                         │(缺信息 AI 又判定高风险)       │(发现高风险)
                         ▼                              ▼
                             high_risk_pending
                                     │
                      ┌──────────────┴──────────────┐
                      ▼                             ▼
             recommended_reject              shortlisted
```

**为什么不合并**：
- **避免 AI 盖过用户意图**。用户可能在 `recommended_reject` 上仍选
  "shortlist 保留"（例如有熟人推荐、AI 看不到的外部信息）；合成一列
  就会让 AI 重跑时把用户选择抹掉。
- **独立回滚**。调整 clause 评估规则导致一批 candidate 被重判
  `high_risk_pending`，不会影响"用户已决定保留"的条目。

---

## 7. HK bbox 是全系统 invariant：一个 Shenzhen 坐标的故事

**问题**：地址解析偶尔会把 HK 候选解析到**深圳**（`lat > 22.56`，如
罗湖口岸北侧）。路径规划跑下去就是一条跨境路线，estimated_minutes 显
示 90 分钟。这不是"估算偏差"，是**彻底错**。

**选了什么**：把 HK bounding box `(113.80, 22.15, 114.45, 22.56)`
做成**任何坐标的必经闸门**。`backend/app/integrations/geocoding/
hk_bbox.py::in_hk` 是唯一实现，通过以下位置强制：

- `commute_tools.py:60-83` `_observation()` —— agent 每个工具的返回
  值都过这一步；越界坐标 LLM 根本看不到。
- `CommuteService._deterministic_resolve` —— 兜底 ladder 同样过
  bbox。
- `CommuteService._get_destination_coords` —— **缓存的目的地坐标也
  要重检**（旧数据里可能有 ALS 接入前的非 HK 坐标）。

**为什么不选"运行时校验 + 打 warning log"**：
- warning log 在实际生产不会有人看。错一次就错到用户面前。
- 闸门提前到数据流入口（observation 层），下游完全不需要再防御；
  "所有坐标必过 bbox" 是可形式化验证的单一属性，心智负担极低。

**代价**：万一未来产品扩到深圳 / 广州，bbox 需改成可配置 —— 目前
RentWise 定位明确是 HK only，这个代价不存在。

---

## 附：决策之间的横向约束

这些决策不是彼此独立的。几组关键耦合：

- **三层评估**（§2）与 **eval harness field-level floor** 是配套设
  计 —— 不拆层就没有 field 级 floor 可言。
- **LangGraph 状态机**（§3）与 **HK bbox invariant**（§7）是配套设
  计 —— agent 给 LLM 展示的每条 observation 都过 bbox，LLM 就算想幻
  觉越界坐标也看不到。
- **后台状态机在 DB**（§4）与 **candidate status vs user_decision 分
  离**（§6）是配套设计 —— DB 是 source of truth，AI 改 AI 的状态、
  用户改用户的状态，互不踩脚。

---

## 相关文档

- [`resume-highlights.md`](./resume-highlights.md) — 4 项技术亮点的
  面向汇报版本（含流程图、参数取舍）
- [`../README.md`](../README.md) — 仓库结构、跑起来、部署
