# RentWise 数据模型

> 本文档详细说明项目的数据库结构和实体关系。

---

## 1. 实体关系图 (ER Diagram)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                   RentWise 数据模型                                      │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   ┌─────────────────┐                                                                   │
│   │      User       │                                                                   │
│   │─────────────────│                                                                   │
│   │ id (PK)         │                                                                   │
│   │ email           │                                                                   │
│   │ password_hash   │                                                                   │
│   │ created_at      │                                                                   │
│   │ updated_at      │                                                                   │
│   └────────┬────────┘                                                                   │
│            │ 1                                                                          │
│            │                                                                            │
│            │ has many                                                                   │
│            ▼                                                                            │
│   ┌─────────────────┐                    ┌─────────────────────────┐                    │
│   │  SearchProject  │                    │   InvestigationItem     │                    │
│   │─────────────────│                    │─────────────────────────│                    │
│   │ id (PK)         │──────────────────▶│ id (PK)                 │                    │
│   │ user_id (FK)    │      1:N          │ project_id (FK)         │                    │
│   │ title           │                    │ candidate_id (FK)       │                    │
│   │ status          │                    │ category                │                    │
│   │ max_budget      │                    │ title                   │                    │
│   │ preferred_      │                    │ question                │                    │
│   │   districts     │                    │ priority                │                    │
│   │ must_have       │                    │ status                  │                    │
│   │ deal_breakers   │                    └─────────────────────────┘                    │
│   │ move_in_target  │                                                                   │
│   │ notes           │                                                                   │
│   └────────┬────────┘                                                                   │
│            │ 1                                                                          │
│            │                                                                            │
│            │ has many                                                                   │
│            ▼                                                                            │
│   ┌─────────────────────┐          ┌─────────────────────────┐                            │
│   │  CandidateListing   │─────────▶│  CandidateSourceAsset   │                            │
│   │─────────────────────│   1:N    │─────────────────────────│                            │
│   │ id (PK)             │          │ id (PK)                 │                            │
│   │ project_id (FK)     │          │ candidate_id (FK)       │                            │
│   │ name                │          │ storage_provider        │                            │
│   │ source_type         │          │ storage_key             │                            │
│   │ raw_listing_text    │          │ original_filename       │                            │
│   │ raw_chat_text       │          │ content_type            │                            │
│   │ raw_note_text       │          │ ocr_status              │                            │
│   │ combined_text       │          │ ocr_text                │                            │
│   │ status              │          └─────────────────────────┘                            │
│   │ processing_stage    │                                                                   │
│   │ user_decision       │          ┌─────────────────────────┐                            │
│   └─────────┬───────────┘          │ CandidateExtractedInfo  │                            │
│             │ 1                    │─────────────────────────│                            │
│             │                      │ candidate_id (PK, FK)   │                            │
│             ├─────────────────────▶│ monthly_rent            │                            │
│             │        1:1           │ management_fee_amount   │                            │
│             │                      │ deposit                 │                            │
│             │                      │ lease_term              │                            │
│             │                      │ district                │                            │
│             │                      │ size_sqft               │                            │
│             │                      │ ...                     │                            │
│             │                      └─────────────────────────┘                            │
│             │                                                                            │
│             │          ┌─────────────────────────┐                                        │
│             ├─────────▶│     CostAssessment      │                                        │
│             │   1:1    │─────────────────────────│                                        │
│             │          │ candidate_id (PK, FK)   │                                        │
│             │          │ known_monthly_cost      │                                        │
│             │          │ monthly_cost_confidence │                                        │
│             │          │ cost_risk_flag          │                                        │
│             │          │ summary                 │                                        │
│             │          └─────────────────────────┘                                        │
│             │                                                                            │
│             │          ┌─────────────────────────┐                                        │
│             ├─────────▶│    ClauseAssessment     │                                        │
│             │   1:1    │─────────────────────────│                                        │
│             │          │ candidate_id (PK, FK)   │                                        │
│             │          │ repair_responsibility_  │                                        │
│             │          │   level                 │                                        │
│             │          │ lease_term_level        │                                        │
│             │          │ clause_risk_flag        │                                        │
│             │          │ summary                 │                                        │
│             │          └─────────────────────────┘                                        │
│             │                                                                            │
│             │          ┌─────────────────────────┐                                        │
│             └─────────▶│  CandidateAssessment    │                                        │
│                      1:1│─────────────────────────│                                        │
│                         │ candidate_id (PK, FK)   │                                        │
│                         │ potential_value_level   │                                        │
│                         │ completeness_level      │                                        │
│                         │ decision_risk_level     │                                        │
│                         │ next_best_action        │                                        │
│                         │ status                  │                                        │
│                         │ labels                  │                                        │
│                         │ summary                 │                                        │
│                         └─────────────────────────┘                                        │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘

图例:
PK = Primary Key (主键)
FK = Foreign Key (外键)
1:1 = One-to-One relationship (一对一关系)
1:N = One-to-Many relationship (一对多关系)
```

---

## 2. 核心实体说明

### 2.1 User (用户)

**用途**：存储用户账户信息

| 字段 | 类型 | 描述 |
|------|------|------|
| `id` | UUID | 主键 |
| `email` | String(255) | 邮箱，唯一 |
| `password_hash` | String(255) | 密码哈希 |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |

**关系**：
- 一个用户可以有多个 SearchProject (1:N)

---

### 2.2 SearchProject (搜索项目)

**用途**：组织用户的租房搜索任务

| 字段 | 类型 | 描述 |
|------|------|------|
| `id` | UUID | 主键 |
| `user_id` | UUID | 外键 → User.id |
| `title` | String(255) | 项目标题 |
| `status` | String(50) | 项目状态: `active` / `archived` / `completed` |
| `max_budget` | Integer | 预算上限（可选） |
| `preferred_districts` | Array[String] | 偏好区域列表 |
| `must_have` | Array[String] | 必须条件列表 |
| `deal_breakers` | Array[String] | 排除条件列表 |
| `move_in_target` | Date | 期望入住日期（可选） |
| `notes` | Text | 备注（可选） |

**关系**：
- 属于一个 User (N:1)
- 可以有多个 CandidateListing (1:N)
- 可以有多个 InvestigationItem (1:N)

**示例数据**：

```json
{
  "title": "九龙租房搜索",
  "status": "active",
  "max_budget": 15000,
  "preferred_districts": ["Mong Kok", "Prince Edward"],
  "must_have": ["furnished"],
  "deal_breakers": ["shared bathroom"],
  "move_in_target": "2026-05-01"
}
```

---

### 2.3 CandidateListing (候选房源)

**用途**：存储用户导入的租房候选

| 字段 | 类型 | 描述 |
|------|------|------|
| `id` | UUID | 主键 |
| `project_id` | UUID | 外键 → SearchProject.id |
| `name` | String(255) | 房源名称（AI 生成或手动设置） |
| `source_type` | String(50) | 来源类型: `manual_text` / `chat_log` / `mixed` |
| `raw_listing_text` | Text | 原始房源描述文本 |
| `raw_chat_text` | Text | 原始聊天记录文本 |
| `raw_note_text` | Text | 用户备注 |
| `combined_text` | Text | 合并后的文本（用于 AI 分析） |
| `status` | String(50) | 评估状态 |
| `processing_stage` | String(50) | 处理阶段 |
| `processing_error` | Text | 处理错误信息 |
| `user_decision` | String(50) | 用户决策: `undecided` / `shortlisted` / `rejected` |

**status 状态值**：

| 状态 | 含义 |
|------|------|
| `new` | 新导入，尚未评估 |
| `needs_info` | 信息不足，需要核实 |
| `follow_up` | 需要跟进 |
| `high_risk_pending` | 高风险待确认 |
| `recommended_reject` | AI 建议拒绝 |
| `shortlisted` | 已进入短名单 |

**processing_stage 状态值**：

| 阶段 | 含义 |
|------|------|
| `queued` | 已排队等待处理 |
| `running_ocr` | 正在 OCR 处理 |
| `extracting` | 正在提取信息 |
| `completed` | 处理完成 |
| `failed` | 处理失败 |

**关系**：
- 属于一个 SearchProject (N:1)
- 有一个 CandidateExtractedInfo (1:1)
- 有一个 CostAssessment (1:1)
- 有一个 ClauseAssessment (1:1)
- 有一个 CandidateAssessment (1:1)
- 可以有多个 CandidateSourceAsset (1:N)
- 可以有多个 InvestigationItem (1:N)

---

### 2.4 CandidateSourceAsset (源文件资源)

**用途**：存储上传的图片文件信息

| 字段 | 类型 | 描述 |
|------|------|------|
| `id` | UUID | 主键 |
| `candidate_id` | UUID | 外键 → CandidateListing.id |
| `storage_provider` | String(50) | 存储提供商: `local` |
| `storage_key` | String(500) | 存储路径/键 |
| `original_filename` | String(255) | 原始文件名 |
| `content_type` | String(100) | MIME 类型 |
| `file_size` | Integer | 文件大小（字节） |
| `ocr_status` | String(50) | OCR 状态 |
| `ocr_text` | Text | OCR 识别文本 |

**ocr_status 状态值**：

| 状态 | 含义 |
|------|------|
| `pending` | 等待处理 |
| `succeeded` | 处理成功 |
| `failed` | 处理失败 |
| `skipped` | 跳过（非图片） |

---

### 2.5 CandidateExtractedInfo (提取信息)

**用途**：存储 AI 从房源文本中提取的结构化信息

| 字段 | 类型 | 描述 |
|------|------|------|
| `candidate_id` | UUID | 主键 + 外键 → CandidateListing.id |
| `monthly_rent` | String(100) | 月租金 |
| `management_fee_amount` | String(100) | 管理费金额 |
| `management_fee_included` | Boolean | 管理费是否包含在租金内 |
| `rates_amount` | String(100) | 差饷金额 |
| `rates_included` | Boolean | 差饷是否包含在租金内 |
| `deposit` | String(100) | 押金 |
| `agent_fee` | String(100) | 代理费 |
| `lease_term` | String(100) | 租期 |
| `move_in_date` | String(100) | 入住时间 |
| `repair_responsibility` | String(255) | 维修责任 |
| `district` | String(100) | 区域 |
| `furnished` | String(255) | 家具状况 |
| `size_sqft` | String(50) | 面积（平方英尺） |
| `bedrooms` | String(50) | 房间数 |
| `suspected_sdu` | Boolean | 是否疑似分间楼宇单位 |
| `sdu_detection_reason` | String(100) | SDU 判断原因 |
| `ocr_texts` | Array[String] | OCR 文本列表 |

---

### 2.6 CostAssessment (成本评估)

**用途**：存储 AI 对房源成本的评估

| 字段 | 类型 | 描述 |
|------|------|------|
| `candidate_id` | UUID | 主键 + 外键 |
| `known_monthly_cost` | Float | 已知月成本 |
| `monthly_cost_confidence` | String(50) | 置信度: `high` / `medium` / `low` |
| `monthly_cost_missing_items` | Array[String] | 缺失的成本项 |
| `move_in_cost_known_part` | Float | 已知入住成本 |
| `move_in_cost_confidence` | String(50) | 入住成本置信度 |
| `cost_risk_flag` | String(50) | 成本风险标记 |
| `summary` | Text | 评估摘要 |

**cost_risk_flag 值**：

| 值 | 含义 |
|------|------|
| `none` | 无明显风险 |
| `possible_additional_cost` | 可能有额外费用 |
| `hidden_cost_risk` | 隐性成本风险 |
| `over_budget` | 超出预算 |

---

### 2.7 ClauseAssessment (条款评估)

**用途**：存储 AI 对租约条款的评估

| 字段 | 类型 | 描述 |
|------|------|------|
| `candidate_id` | UUID | 主键 + 外键 |
| `repair_responsibility_level` | String(50) | 维修责任等级 |
| `lease_term_level` | String(50) | 租期等级 |
| `move_in_date_level` | String(50) | 入住时间匹配度 |
| `clause_confidence` | String(50) | 条款置信度 |
| `clause_risk_flag` | String(50) | 条款风险标记 |
| `summary` | Text | 评估摘要 |

**repair_responsibility_level 值**：

| 值 | 含义 |
|------|------|
| `clear` | 责任明确 |
| `supported_but_unconfirmed` | 声称支持但未确认 |
| `unclear` | 不明确 |
| `tenant_heavy` | 租客承担较多 |
| `unknown` | 未知 |

**lease_term_level 值**：

| 值 | 含义 |
|------|------|
| `standard` | 标准租期 |
| `rigid` | 僵化租期 |
| `unstable` | 不稳定租期 |
| `unknown` | 未知 |

---

### 2.8 CandidateAssessment (整体评估)

**用途**：存储 AI 对房源的综合评估

| 字段 | 类型 | 描述 |
|------|------|------|
| `candidate_id` | UUID | 主键 + 外键 |
| `potential_value_level` | String(50) | 潜在价值 |
| `completeness_level` | String(50) | 信息完整度 |
| `critical_uncertainty_level` | String(50) | 关键不确定性 |
| `decision_risk_level` | String(50) | 决策风险 |
| `information_gain_level` | String(50) | 信息增益 |
| `recommendation_confidence` | String(50) | 推荐置信度 |
| `next_best_action` | String(50) | 下一步行动 |
| `status` | String(50) | 候选状态 |
| `labels` | Array[String] | 标签列表 |
| `summary` | Text | 评估摘要 |

**next_best_action 值**：

| 值 | 含义 |
|------|------|
| `verify_cost` | 核实成本 |
| `verify_clause` | 核实条款 |
| `schedule_viewing` | 安排看房 |
| `keep_warm` | 保持关注 |
| `reject` | 建议拒绝 |

---

### 2.9 InvestigationItem (调查项)

**用途**：存储需要用户跟进的调查问题

| 字段 | 类型 | 描述 |
|------|------|------|
| `id` | UUID | 主键 |
| `project_id` | UUID | 外键 → SearchProject.id |
| `candidate_id` | UUID | 外键 → CandidateListing.id（可选） |
| `category` | String(50) | 类别: `cost` / `clause` / `timing` / `match` |
| `title` | String(255) | 标题 |
| `question` | Text | 问题内容 |
| `priority` | String(50) | 优先级: `high` / `medium` / `low` |
| `status` | String(50) | 状态: `open` / `resolved` / `dismissed` |

---

## 3. 候选状态流转图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          候选房源状态流转                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │                                                                      │ │
│   │                        导入房源                                      │ │
│   │                           │                                         │ │
│   │                           ▼                                         │ │
│   │   ┌─────────┐    AI 评估    ┌─────────────┐                         │ │
│   │   │   new   │ ───────────▶ │  needs_info │                         │ │
│   │   └─────────┘              └──────┬──────┘                         │ │
│   │        │                          │                                 │ │
│   │        │                          │ 用户核实信息                    │ │
│   │        │ AI 评估完成              │                                 │ │
│   │        │                          ▼                                 │ │
│   │        │                   ┌─────────────┐                          │ │
│   │        │                   │  follow_up  │                          │ │
│   │        │                   └──────┬──────┘                          │ │
│   │        │                          │                                 │ │
│   │        │                          │ 发现高风险                      │ │
│   │        │                          ▼                                 │ │
│   │        │                   ┌───────────────────┐                    │ │
│   │        └──────────────────▶│ high_risk_pending │                    │ │
│   │                            └─────────┬─────────┘                    │ │
│   │                                      │                              │ │
│   │                    ┌─────────────────┴─────────────────┐            │ │
│   │                    │                                   │            │ │
│   │                    ▼                                   ▼            │ │
│   │            ┌───────────────────┐             ┌───────────────────┐   │ │
│   │            │recommended_reject │             │    shortlisted    │   │ │
│   │            └───────────────────┘             └───────────────────┘   │ │
│   │                                                                      │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│   用户决策层（独立于 AI 评估状态）                                          │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │                                                                      │ │
│   │   user_decision: undecided ──────▶ shortlisted                      │ │
│   │                           │                                        │ │
│   │                           └──────▶ rejected                         │ │
│   │                                                                      │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 数据库索引

为了优化查询性能，系统创建了以下索引：

```sql
-- 用户查询
CREATE INDEX ix_search_projects_user_id ON search_projects(user_id);
CREATE INDEX ix_search_projects_status ON search_projects(status);

-- 候选房源查询
CREATE INDEX ix_candidate_listings_project_id ON candidate_listings(project_id);
CREATE INDEX ix_candidate_listings_status ON candidate_listings(status);
CREATE INDEX ix_candidate_listings_user_decision ON candidate_listings(user_decision);

-- 源文件查询
CREATE INDEX ix_candidate_source_assets_candidate_id ON candidate_source_assets(candidate_id);

-- 调查项查询
CREATE INDEX ix_investigation_items_project_id ON investigation_items(project_id);
CREATE INDEX ix_investigation_items_candidate_id ON investigation_items(candidate_id);
CREATE INDEX ix_investigation_items_status ON investigation_items(status);
```

---

## 5. 级联删除规则

当删除父实体时，子实体会被自动删除：

```
User 删除
    └── SearchProject 删除
            ├── CandidateListing 删除
            │       ├── CandidateExtractedInfo 删除
            │       ├── CostAssessment 删除
            │       ├── ClauseAssessment 删除
            │       ├── CandidateAssessment 删除
            │       ├── CandidateSourceAsset 删除
            │       └── InvestigationItem 删除
            └── InvestigationItem 删除
```

---

## 相关文档

- [项目概述](./overview.md) — 产品介绍和功能说明
- [技术架构](./architecture.md) — 系统设计和技术选型
- [AI 功能实现](./ai-features.md) — OCR、LLM、评估算法详解
- [API 设计](./api-design.md) — 接口设计说明
