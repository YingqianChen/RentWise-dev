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

## 8. Landing 单 CTA + 反向 redirect：消除未登录态的选择困难

**问题**：早期 landing (`frontend/app/page.tsx`) 同时暴露三个 CTA —— 顶部
nav 的 `Sign in` 与 `Open workspace`、hero 的 `Get started` 与
`Open existing workspace`、footer 又重复一遍 dual link。但
`app/projects/page.tsx:143-151` 在没有 token 时直接 `router.push("/login")`，
这意味着对一个未登录访客来说，"Open workspace" 和 "Sign in" **功能上完全
等价**。视觉上却把最显眼的 dark primary 给了"无差异化价值"的入口，三选
一变成 choice overload。

**选了什么**：landing 收敛到每个视觉区域只有一个主要 CTA —— nav 仅留
"Sign in →"、hero 仅留 "Get started →"、footer 删除 dual-link 条。**反向
对称**：在 `/login` 加挂载期 `getToken()` 检查，已登录访客直接
`router.replace("/projects")` 兜底（用 `replace` 而非 `push`，否则浏览器
back 键会在 `/login` 与 `/projects` 之间反弹）。Landing 始终渲染未登录
变体，保持 server component。

**为什么不选 client-side 条件渲染**：
- **Hydration mismatch**。`getToken()` 在 SSR 时拿不到 `localStorage`
  返回 null，hydration 阶段如果按客户端 token 渲染不同 nav，React 会
  报 "did not match" warning，要么得 `suppressHydrationWarning`、要么
  得整页 `"use client"` 染色——成本不对称。
- **复杂度对称**。"已登录访客点了 Sign in" 是一条几乎不会走的边缘路径，
  代价是多一次 redirect；这跟现有 `app/projects/page.tsx` 的
  redirect-on-missing-token 是同一条对称的兜底模式。
- **redirect loop 安全**。stale token 由 `app/projects/page.tsx:160`
  的 `clearToken()` 自愈，新 effect 在每次 mount 时重检，token 已清空
  则什么都不做。

**代价**：landing 永远以未登录形态呈现，已登录用户必须经过 login 跳一
下。可接受 —— 收益是零 hydration 风险 + 单一可读的入口语义。

---

## 9. Commute evidence 持久化：用 config-signature 替代 TTL

**问题**：commute 之前是 derived-at-response —— 每次进 candidate detail /
compare / dashboard 都重新跑 ALS+Amap 路径规划。Amap 配额有限、LLM
resolver agent 也不便宜，体验上还有 1–2 秒延迟。但缓存有个老问题：
**什么时候让缓存失效**？常见答案是 TTL（比如 24 小时），但 TTL 在两端
都不对：(1) 用户改了项目通勤目的地、24 小时内还看到旧分钟数；(2) 配置
没变但定时刷新浪费配额。

**选了什么**：**config-signature 缓存**。每行 `candidate_commute_evidence`
带一个 `config_signature`（sha256 前缀），它是项目通勤配置 + 候选位置
信号的拼接 hash。读时重新计算预期 signature，匹配才命中。配置一旦变化，
signature 跟着变，旧行自动失效。**叠加 eager delete**：项目 PUT
endpoint 在 commute 字段变更时直接 `DELETE FROM candidate_commute_evidence
WHERE candidate_id IN (...)`，下一次读甚至连 stale 行都不会加载。

`peak_morning` / `peak_evening` 不把"具体哪一天"写进 signature —— HK
工作日早高峰 08:30 的通勤模式是稳定的，让缓存跨日复用；用户真要刷新只
需切一次窗口再切回来。

**为什么不选 TTL**：
- TTL 和"用户改配置"是正交事件。TTL 撑不到对配置变化的及时响应，又
  在配置稳定时浪费 API。
- signature 是数据源真实变化的代理，更精确。
- 失效逻辑可形式化验证（"signature 一致 ⇒ 输入未变"），TTL 没有这个
  性质。

**为什么不选 trigger-based 失效（DB trigger 自动 cascade delete）**：
- 失效来自 *project* 字段变化、*candidate.extracted_info* 字段变化、
  甚至 ALS 重 geocode 后 lat/lng 抖动。trigger 写不全这些路径。
- 应用层的 eager delete + signature mismatch 双闸门更清晰，故障域只
  在 Python，不要把一致性绑到 Postgres trigger 上。

**代价**：`now` 窗口也走 signature 缓存，意味着第一次算的"now"会一直
返回 —— 实际上并不"now"。当前阶段可接受（用户决策周期是周/月，不是
分钟）；未来若要"now 真的实时"，可以给 `now` 单独加短 TTL（比如 1 小
时），保留其他窗口的 signature 缓存。

---

## 10. Transit 多路线：primary + labeled alternatives

**问题**：Amap transit API 单次请求会返回 3–5 条候选方案；早期实现
只取 `transits[0]` 当 best route 直接渲染，剩下的整段丢弃。结果是用户
偶尔会撞到看着不靠谱的路线（比如凌晨调用时跑出 N 字头通宵巴士），却没
有"那其他几条呢"的入口——只能去地图软件自己查，产品的"已经为你算好
多个候选"价值随之消失。

**选了什么**：在 `route_transit` 里 parse 全部 `transits[]`，做两步处理：
- **去重**：用 `(mode, line_name, from_station, to_station)` 序列做
  signature；Amap 经常返回 walking 距离差 1m 但其余完全相同的"假备
  选"，signature 把它们折成一条。
- **打标签**：fastest 永远是 primary。从剩余 distinct 路线里挑最多两
  条做 alternatives —— "Fewer transfers"（非步行段数 < primary）、
  "Less walking"（步行总距离 < primary）。两者命中同一条则只展示一次；
  都不命中但确实有第二条不同路线时，挂一个 generic "Alternative" 标
  签兜底，避免用户永远只看到一个选项。

前端 Compare 的 commute panel 把 routes 渲染成 horizontal tab，点击
切换 RouteStrip 内容；只有 1 条时退化为现有的单条形态，UI 不增加。

**为什么不选服务端硬过滤特定线路**（如 N-prefix 通宵巴士）：
- "深夜巴士"在凌晨查询是合理结果，硬过滤会让真深夜用户拿不到任何路
  线。
- 给用户多条有标签的选项，由用户自己决定取哪条，比让产品当裁判更
  稳健 —— 错杀的成本（用户怀疑数据完整性）大于看到一条不太相关方案
  的成本（用户切到下一个 tab 即可）。

**为什么 alternatives 写进 cache 表新加一列而不是塞进 segments JSONB**：
- Segments 字段语义是"primary route 的腿"。把 alternatives 强行嵌进
  去要么改 segments 的 shape（破坏 0009 的兼容性），要么造一个嵌套
  里有嵌套的怪结构。
- 单独一列 `alternatives JSONB` 让两个概念正交；migration 0010 加列
  即可，0009 写过的旧行 alternatives 默认 NULL，读时回落为"只有
  primary"，自然向下兼容。

**代价**：cache 行体积变大（多一个 JSONB 字段）。每行预计加 1–3 KB，
对 100 candidates 量级的项目完全可忽略。

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
- **HK bbox invariant**（§7）与 **commute 持久化**（§9）是配套设计
  —— 缓存只在坐标过 bbox 后写入，cached 行永远 in-bbox；万一未来 bbox
  调整，老的 cached 行会因为坐标不在新 bbox 内被 `_get_destination_coords`
  / `_observation` 拒绝，缓存自然失效。

---

## 附：定位演进路线图

产品定位演进顺序（forward-looking，记录在此而非 README，因为 README 只
描述已 shipped 状态）：

1. **先做 Option B —— commute-first positioning**。Commute 证据已
   shipped 且差异化最强：HK Gov ALS + Amap 整合、LangGraph resolver
   agent、bbox 守门构成的端到端 evidence，是非 HK 本地团队不易复制的
   工程护城河。下一步把 commute 抬升为 landing / dashboard 的头部叙
   事，让 "Set destination, get real evidence" 成为 RentWise 的第一
   印象。
2. **再做 Option A —— tenancy-risk auditor positioning**。当前
   tenancy RAG 仅依赖《租住物业指南》22 个 chunk，且只在 risk flag 触
   发时被动展示原文引用；要变成头部叙事还需要：扩充语料（《条例》正
   文、民政事务总署示范租约、常见 FAQ）、把输出从被动 quote 升级为
   `{ what_to_change, suggested_clause_text }` 形式的可操作建议、引入
   "Ask your lease" 主动问答入口、以及把 risk 触发器从 keyword regex
   迁移到 extraction 阶段直接产 `clause_concerns`。工程量更大，但护
   城河最深 —— 因为 ChatGPT 不会内置 HK 法规结构化知识。

A 与 B 不是替代，是叙事优先级。结构上两者并存，先把 B 这条已经做完的
路径变成头部讲法，A 的素材沉淀好了再上推。

---

## 相关文档

- [`resume-highlights.md`](./resume-highlights.md) — 4 项技术亮点的
  面向汇报版本（含流程图、参数取舍）
- [`../README.md`](../README.md) — 仓库结构、跑起来、部署
