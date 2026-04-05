# RentWise AI 功能实现

> 本文档详细说明项目中 AI 相关功能的实现原理，是技术汇报的核心亮点。

---

## 1. AI 功能概览

RentWise 整合了多种 AI 技术来实现端到端的租房决策支持：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          RentWise AI 技术栈                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   输入层                    处理层                      输出层              │
│   ──────                    ──────                      ──────              │
│                                                                             │
│   ┌─────────┐         ┌─────────────────┐         ┌─────────────────┐     │
│   │ 文本输入 │ ──────▶ │                 │ ──────▶ │ 结构化提取信息  │     │
│   │ (listing│         │                 │         │ • 租金、押金    │     │
│   │  text)  │         │    LLM 提取     │         │ • 面积、位置    │     │
│   └─────────┘         │   (LangChain)   │         │ • 条款信息      │     │
│                       │                 │         └─────────────────┘     │
│   ┌─────────┐         │                 │                                   │
│   │ 图片输入 │ ──────▶ │                 │                                   │
│   │ (images)│         └─────────────────┘                                   │
│   └────┬────┘               │                                             │
│        │                    │                                             │
│        ▼                    │                                             │
│   ┌─────────┐               │                                             │
│   │  OCR    │               │                                             │
│   │(PaddleOCR)             │                                             │
│   │ 文字识别│               │                                             │
│   └────┬────┘               │                                             │
│        │                    ▼                                             │
│        └────────────▶ ┌─────────────────┐         ┌─────────────────┐     │
│                       │   评估流水线     │ ──────▶ │ 决策建议        │     │
│                       │ • Cost Assess   │         │ • 行动建议      │     │
│                       │ • Clause Assess │         │ • 风险提示      │     │
│                       │ • Candidate     │         │ • 对比分组      │     │
│                       └─────────────────┘         └─────────────────┘     │
│                                                                             │
│                       ┌─────────────────┐                                   │
│                       │ LangGraph Agent │                                   │
│                       │ 工作流编排      │                                   │
│                       └─────────────────┘                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. OCR 文字识别

### 2.1 技术选型：PaddleOCR

**为什么选择 PaddleOCR？**

| 特性 | PaddleOCR | Tesseract | Google Cloud Vision |
|------|-----------|-----------|---------------------|
| 中文支持 | ✅ 优秀 | ⚠️ 一般 | ✅ 优秀 |
| 开源免费 | ✅ 是 | ✅ 是 | ❌ 付费 |
| 离线使用 | ✅ 支持 | ✅ 支持 | ❌ 需联网 |
| 手写体识别 | ✅ 支持 | ⚠️ 一般 | ✅ 支持 |
| 部署难度 | 中等 | 低 | 低 |

**PaddleOCR 优势**：
- 针对中文场景优化
- 支持多种文档场景（截图、照片、扫描件）
- 提供方向校正、文档展平等高级功能

### 2.2 OCR 处理流程

```
┌──────────────────────────────────────────────────────────────────┐
│                      OCR 处理流程                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   用户上传图片                                                   │
│        │                                                         │
│        ▼                                                         │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  PaddleOCR 初始化                                        │   │
│   │  • 语言设置: ch (中英文混合)                             │   │
│   │  • 文档方向校正: 可选                                     │   │
│   │  • 文档展平: 可选                                         │   │
│   │  • 文本行方向: 可选                                       │   │
│   └─────────────────────────────────────────────────────────┘   │
│        │                                                         │
│        ▼                                                         │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  predict() 方法执行                                       │   │
│   │  • 检测文本区域                                           │   │
│   │  • 识别文本内容                                           │   │
│   │  • 返回结构化结果                                         │   │
│   └─────────────────────────────────────────────────────────┘   │
│        │                                                         │
│        ▼                                                         │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  结果提取                                                 │   │
│   │  • 从嵌套结构中提取文本                                   │   │
│   │  • 去重、合并                                             │   │
│   │  • 返回纯文本字符串                                       │   │
│   └─────────────────────────────────────────────────────────┘   │
│        │                                                         │
│        ▼                                                         │
│   合并到 combined_text                                           │
│   (与其他文本一起送入 LLM 处理)                                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.3 代码实现要点

```python
# OCR 服务初始化
class PaddleOCRService:
    def _get_engine(self):
        self._engine = PaddleOCR(
            lang=settings.PADDLEOCR_LANG,  # 默认 "ch" (中英文)
            use_doc_orientation_classify=settings.OCR_USE_DOC_ORIENTATION,
            use_doc_unwarping=settings.OCR_USE_DOC_UNWARPING,
            use_textline_orientation=settings.OCR_USE_TEXTLINE_ORIENTATION,
        )
```

**配置项说明**：

| 配置项 | 作用 | 建议 |
|--------|------|------|
| `PADDLEOCR_LANG` | 识别语言 | `ch` 支持中英文混合 |
| `OCR_USE_DOC_ORIENTATION` | 文档方向校正 | 截图类可关闭以提速 |
| `OCR_USE_DOC_UNWARPING` | 文档展平 | 拍照文档可开启 |
| `OCR_USE_TEXTLINE_ORIENTATION` | 文本行方向 | 竖排文字可开启 |

---

## 3. LLM 信息提取

### 3.1 从非结构化文本到结构化数据

**核心挑战**：
- 房源信息格式不统一（中介发布、个人发布、聊天记录）
- 中英文混合
- 信息不完整或模糊

**解决方案**：使用 LLM 进行智能提取

```
输入 (非结构化文本)                    输出 (结构化 JSON)
────────────────────                  ───────────────────

"旺角地铁附近，$8000月租，           {
500呎，一房一厅，有傢俬，              "monthly_rent": "$8000",
管理费$500，两按一上，                 "size_sqft": "500",
随时入住，业主负责大维修"              "bedrooms": "1",
                                      "furnished": "furnished",
                                      "management_fee_amount": "$500",
                                      "deposit": "2 months",
                                      "move_in_date": "available now",
                                      "repair_responsibility": "landlord major repairs",
                                      ...
                                    }
```

### 3.2 Prompt 设计

**提取 Prompt 模板**：

```
Extract the key rental fields from the Hong Kong listing text below.
If a field is missing, ambiguous, or not mentioned, return "unknown".

Text:
{text}

Return JSON only with these fields:
{
    "monthly_rent": "Monthly rent including currency symbol",
    "management_fee_amount": "Management fee amount",
    "management_fee_included": true/false/unknown,
    "rates_amount": "Government rates amount",
    "rates_included": true/false/unknown,
    "deposit": "Deposit amount or months of rent",
    "agent_fee": "Agent fee amount",
    "lease_term": "A short normalized lease note",
    "move_in_date": "A short normalized availability note",
    "repair_responsibility": "Who handles repairs",
    "district": "District or area name",
    "furnished": "Furniture and appliance status",
    "size_sqft": "Size in square feet",
    "bedrooms": "Number of bedrooms or room type",
    "suspected_sdu": true/false/unknown,
    "sdu_detection_reason": "Short reason"
}
```

**设计要点**：

1. **明确输出格式**：要求 JSON 格式，便于程序解析
2. **处理未知值**：明确要求返回 "unknown" 而非猜测
3. **字段说明**：每个字段都有清晰的说明
4. **香港本地化**：针对香港租房市场特点设计字段

### 3.3 提取字段清单

| 字段 | 描述 | 示例值 |
|------|------|--------|
| `monthly_rent` | 月租金 | `$15000`, `HKD 15,000` |
| `management_fee_amount` | 管理费金额 | `$500` |
| `management_fee_included` | 管理费是否包含在租金内 | `true/false/unknown` |
| `rates_amount` | 差饷金额 | `$300` |
| `deposit` | 押金 | `2 months`, `$30000` |
| `agent_fee` | 代理费 | `half month`, `$7500` |
| `lease_term` | 租约期限 | `2 years`, `1 year fixed` |
| `move_in_date` | 入住时间 | `available now`, `May 2026` |
| `repair_responsibility` | 维修责任 | `landlord handles major` |
| `district` | 区域 | `Mong Kok`, `旺角` |
| `furnished` | 家具状况 | `fully furnished`, `unfurnished` |
| `size_sqft` | 面积 | `500` |
| `bedrooms` | 房间数 | `1`, `studio` |
| `suspected_sdu` | 是否疑似分间楼宇单位 | `true/false/unknown` |

---

## 4. 评估算法详解 ⭐

### 4.1 评估体系架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            三层评估体系                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                     Cost Assessment (成本评估)                       │  │
│   │                                                                     │  │
│   │   输入: 租金、管理费、差饷、押金、代理费、预算                       │  │
│   │                                                                     │  │
│   │   输出:                                                             │  │
│   │   • known_monthly_cost (已知月成本)                                 │  │
│   │   • monthly_cost_confidence (置信度: high/medium/low)               │  │
│   │   • cost_risk_flag (风险标记)                                       │  │
│   │   • summary (评估摘要)                                              │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                       │
│                                    ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                   Clause Assessment (条款评估)                       │  │
│   │                                                                     │  │
│   │   输入: 维修责任、租期、入住时间                                     │  │
│   │                                                                     │  │
│   │   输出:                                                             │  │
│   │   • repair_responsibility_level (维修责任等级)                       │  │
│   │   • lease_term_level (租期等级)                                     │  │
│   │   • move_in_date_level (入住时间匹配度)                             │  │
│   │   • clause_risk_flag (条款风险标记)                                  │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                       │
│                                    ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                 Candidate Assessment (整体评估)                      │  │
│   │                                                                     │  │
│   │   输入: 提取信息、成本评估、条款评估、用户偏好                       │  │
│   │                                                                     │  │
│   │   输出:                                                             │  │
│   │   • potential_value_level (潜在价值)                                │  │
│   │   • completeness_level (信息完整度)                                 │  │
│   │   • decision_risk_level (决策风险)                                  │  │
│   │   • next_best_action (下一步行动)                                   │  │
│   │   • status (候选状态)                                               │  │
│   │   • labels (标签列表)                                               │  │
│   │   • summary (评估摘要)                                              │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Cost Assessment (成本评估)

**评估维度**：

| 维度 | 描述 | 可能值 |
|------|------|--------|
| `known_monthly_cost` | 计算得出的月总成本 | 数字或 null |
| `monthly_cost_confidence` | 成本信息的置信度 | `high/medium/low` |
| `cost_risk_flag` | 成本风险标记 | 见下表 |

**cost_risk_flag 含义**：

| 标记 | 含义 | 示例场景 |
|------|------|----------|
| `none` | 无明显风险 | 所有费用明确，在预算内 |
| `possible_additional_cost` | 可能有额外费用 | 管理费、差饷是否包含不明确 |
| `hidden_cost_risk` | 隐性成本风险 | 多项费用缺失 |
| `over_budget` | 超出预算 | 月成本超过用户设定的预算上限 |

**评估逻辑**（简化版）：

```
如果 租金未知:
    confidence = low
    risk_flag = hidden_cost_risk
否则如果 管理费或差饷不明确:
    confidence = medium
    risk_flag = possible_additional_cost
否则如果 月总成本 > 预算:
    confidence = high
    risk_flag = over_budget
否则:
    confidence = high
    risk_flag = none
```

### 4.3 Clause Assessment (条款评估)

**评估维度**：

| 维度 | 描述 | 可能值 |
|------|------|--------|
| `repair_responsibility_level` | 维修责任清晰度 | `clear/unclear/tenant_heavy/unknown` |
| `lease_term_level` | 租期稳定性 | `standard/rigid/unstable/unknown` |
| `move_in_date_level` | 入住时间匹配度 | `fit/mismatch/uncertain/unknown` |
| `clause_risk_flag` | 条款风险标记 | `none/needs_confirmation/high_risk` |

**条款风险判断示例**：

| 场景 | lease_term_level | clause_risk_flag |
|------|------------------|------------------|
| 标准 2 年死约生约 | `standard` | `none` |
| 月租、随时退租 | `unstable` | `needs_confirmation` |
| 条款模糊不清 | `unknown` | `needs_confirmation` |
| 租客承担所有维修 | `tenant_heavy` | `high_risk` |

### 4.4 Candidate Assessment (整体评估)

**这是最核心的评估模块**，综合所有信息给出最终建议。

**评估维度**：

| 维度 | 描述 | 可能值 |
|------|------|--------|
| `potential_value_level` | 潜在价值 | `high/medium/low` |
| `completeness_level` | 信息完整度 | `high/medium/low` |
| `critical_uncertainty_level` | 关键不确定性 | `high/medium/low` |
| `decision_risk_level` | 决策风险 | `high/medium/low` |
| `recommendation_confidence` | 推荐置信度 | `high/medium/low` |
| `next_best_action` | 下一步行动 | 见下表 |
| `status` | 候选状态 | `new/needs_info/follow_up/...` |

**next_best_action 含义**：

| 行动 | 含义 | 触发条件 |
|------|------|----------|
| `reject` | 建议放弃 | 硬性冲突或高风险低价值 |
| `verify_cost` | 核实成本 | 成本信息不完整或低置信度 |
| `verify_clause` | 核实条款 | 条款信息不完整或有风险 |
| `schedule_viewing` | 安排看房 | 信息完整且推荐置信度高 |
| `keep_warm` | 保持关注 | 有潜力但不是当前优先 |

**评估决策树**（简化版）：

```
                        ┌─────────────────┐
                        │  有硬性冲突？    │
                        └────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    │ Yes                     │ No
                    ▼                         ▼
           ┌─────────────┐          ┌─────────────────┐
           │ action=reject│          │ 成本信息完整？  │
           │ status=reject│          └────────┬────────┘
           └─────────────┘                   │
                                    ┌───────┴───────┐
                                    │ No            │ Yes
                                    ▼               ▼
                           ┌─────────────┐  ┌─────────────────┐
                           │verify_cost  │  │ 条款信息完整？  │
                           └─────────────┘  └────────┬────────┘
                                                     │
                                              ┌──────┴──────┐
                                              │ No          │ Yes
                                              ▼             ▼
                                     ┌─────────────┐ ┌─────────────────┐
                                     │verify_clause│ │ 高推荐置信度？  │
                                     └─────────────┘ └────────┬────────┘
                                                              │
                                                       ┌──────┴──────┐
                                                       │ Yes         │ No
                                                       ▼             ▼
                                              ┌───────────────┐ ┌───────────┐
                                              │schedule_viewing│ │keep_warm │
                                              └───────────────┘ └───────────┘
```

---

## 5. LangGraph Agent 工作流 ⭐ 创新点

### 5.1 为什么需要 Agent 模式？

**问题**：简单的 LLM API 调用无法处理复杂的多步骤流程。

**示例场景**：
1. 生成调查问题需要先分析缺失字段
2. 根据风险评估结果调整问题优先级
3. 如果用户有特定偏好，需要定制问题
4. 每一步可能需要访问数据库或调用其他服务

**LangGraph 解决方案**：

```
简单 LLM 调用                    LangGraph Agent
─────────────────                ─────────────────────
单次请求-响应                     多步骤状态机
无法记忆上下文                    内置状态管理
难以处理分支逻辑                  可视化流程图
无法中途干预                      支持人工干预
难以调试                          支持断点、重试
```

### 5.2 Investigation Graph 结构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Investigation Graph 工作流                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────┐                                                               │
│   │  START  │                                                               │
│   └────┬────┘                                                               │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    analyze_candidates 节点                          │  │
│   │                                                                     │  │
│   │   任务:                                                             │  │
│   │   • 获取所有候选房源信息                                            │  │
│   │   • 识别信息缺失项                                                  │  │
│   │   • 识别风险项                                                      │  │
│   │   • 生成初步调查问题列表                                            │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    prioritize_questions 节点                        │  │
│   │                                                                     │  │
│   │   任务:                                                             │  │
│   │   • 根据风险评估优先排序问题                                        │  │
│   │   • 合并相似问题                                                    │  │
│   │   • 生成问题分组                                                    │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    generate_output 节点                              │  │
│   │                                                                     │  │
│   │   任务:                                                             │  │
│   │   • 格式化输出                                                      │  │
│   │   • 添加用户友好的解释                                              │  │
│   │   • 返回调查清单                                                    │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────┐                                                               │
│   │   END   │                                                               │
│   └─────────┘                                                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 状态管理

**状态 (State) 是 LangGraph 的核心概念**：

```python
class InvestigationState(TypedDict):
    # 输入状态
    project_id: int
    candidates: List[CandidateInfo]

    # 中间状态
    missing_fields: List[str]
    risk_items: List[str]
    raw_questions: List[str]

    # 输出状态
    prioritized_questions: List[Question]
    question_groups: List[QuestionGroup]
```

**状态流转**：

```
节点 1 执行                    节点 2 执行                    节点 3 执行
─────────────                  ─────────────                  ─────────────
读取: project_id               读取: missing_fields           读取: raw_questions
      candidates                     risk_items                    prioritized_questions

写入: missing_fields           写入: raw_questions           写入: question_groups
      risk_items                     prioritized_questions
```

### 5.4 LangGraph vs 传统方法对比

| 特性 | 传统函数调用 | LangGraph Agent |
|------|-------------|-----------------|
| **代码结构** | 线性，难以维护复杂逻辑 | 图结构，清晰可视化 |
| **状态管理** | 手动传递参数 | 自动管理 |
| **错误处理** | try-catch 层层嵌套 | 节点级别处理 |
| **调试** | 难以追踪中间状态 | 可检查每步状态 |
| **可扩展性** | 修改函数调用链 | 添加/修改节点 |
| **可测试性** | 测试整个流程 | 可单独测试每个节点 |

---

## 6. 对比决策系统

### 6.1 对比功能设计理念

**核心问题**：如何帮助用户在多个候选中做出选择？

**传统方法**：
- 表格对比（字段并列）
- 评分排序（假精确）

**RentWise 方法**：
- **决策分组**：将候选分成有意义的类别
- **解释驱动**：说明为什么这样分组
- **行动导向**：给出具体的下一步建议

### 6.2 决策分组逻辑

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          决策分组                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   输入: 2-5 个候选房源                                                      │
│                                                                             │
│   输出: 四个分组                                                            │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  🏆 Best Current Option (当前最佳选择)                               │  │
│   │                                                                     │  │
│   │  条件: 信息完整 + 低风险 + 高潜在价值                                │  │
│   │  行动: 建议优先联系、安排看房                                        │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  🔄 Viable Alternatives (可行备选)                                   │  │
│   │                                                                     │  │
│   │  条件: 信息基本完整 + 中等风险 + 有一定价值                          │  │
│   │  行动: 保持关注，作为备选                                            │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  ❓ Not Ready for Comparison (信息不足)                              │  │
│   │                                                                     │  │
│   │  条件: 关键信息缺失，无法公平比较                                    │  │
│   │  行动: 先核实关键信息                                                │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  ❌ Likely Drop (建议放弃)                                           │  │
│   │                                                                     │  │
│   │  条件: 硬性冲突或高风险低价值                                        │  │
│   │  行动: 建议从候选池中移除                                            │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Agent Briefing (智能简报)

**这是对比功能的核心亮点**——用自然语言解释决策。

**Briefing 结构**：

| 字段 | 内容 | 示例 |
|------|------|------|
| `current_take` | 当前判断 | "Candidate A is the current lead..." |
| `why_now` | 判断依据 | "It has the clearest cost structure and fits your budget..." |
| `what_could_change` | 可能改变判断的因素 | "If Candidate B's management fee is included, it could become competitive..." |
| `today_s_move` | 今天的行动建议 | "Contact Candidate A's agent first to confirm viewing availability..." |
| `confidence_note` | 置信度说明 | "The comparison is moderately stable, but one key question remains..." |

**Prompt 设计**：

```
You are helping a renter compare a shortlist of Hong Kong rental candidates.

You will receive a structured comparison result. Do not invent facts.
Your job is to turn the structured result into a short, practical briefing.

Return JSON only:
{
    "current_take": "One or two sentences explaining the current lead",
    "why_now": "Explain why this is the current judgment",
    "what_could_change": "What missing information could change the outcome",
    "today_s_move": "The most useful next move today",
    "confidence_note": "How stable the current judgment is"
}
```

---

## 7. LLM 提供商配置

### 7.1 支持的提供商

| 提供商 | 类型 | 模型 | 特点 |
|--------|------|------|------|
| **Groq** | 云服务 | `llama-3.3-70b-versatile` | 快速响应、API 简单 |
| **Ollama** | 本地 | `llama3.3` | 隐私保护、无需 API Key |

### 7.2 配置方式

```bash
# 使用 Groq (推荐)
LLM_PROVIDER=groq
GROQ_API_KEY=your-api-key
GROQ_MODEL=llama-3.3-70b-versatile

# 使用 Ollama (本地)
LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.3
```

### 7.3 模型选择考量

| 因素 | Groq | Ollama |
|------|------|--------|
| **响应速度** | 快 (~1-3秒) | 取决于本地硬件 |
| **成本** | 有免费额度 | 免费 |
| **隐私** | 数据上传云端 | 数据保留本地 |
| **可用性** | 需联网 | 离线可用 |
| **部署难度** | 低 | 需要本地 GPU |

---

## 8. 技术亮点总结

### 8.1 创新点

| 创新点 | 描述 |
|--------|------|
| **多模态输入处理** | 文本 + 图片 OCR 的统一处理流程 |
| **三层评估体系** | 成本 → 条款 → 整体的递进式评估 |
| **LangGraph Agent** | 用状态机模式处理复杂决策流程 |
| **决策分组** | 替代传统排序的分组式对比 |
| **行动导向** | 从分析到具体行动建议的闭环 |

### 8.2 技术挑战与解决方案

| 挑战 | 解决方案 |
|------|----------|
| OCR 处理耗时长 | 异步后台任务 |
| 信息不完整 | 置信度评估 + 调查清单 |
| 决策逻辑复杂 | LangGraph 状态机 |
| 多候选对比困难 | 分组 + 解释 + 行动建议 |

---

## 相关文档

- [项目概述](./overview.md) — 产品介绍和功能说明
- [技术架构](./architecture.md) — 系统设计和技术选型
- [数据模型](./data-model.md) — 数据库结构说明
- [API 设计](./api-design.md) — 接口设计说明
