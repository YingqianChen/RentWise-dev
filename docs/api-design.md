# RentWise API 设计

> 本文档说明项目的 API 设计原则、端点列表和认证机制。

---

## 1. API 设计原则

### 1.1 RESTful 设计

RentWise API 遵循 RESTful 设计原则：

| 原则 | 说明 | 示例 |
|------|------|------|
| **资源导向** | URL 表示资源，HTTP 方法表示操作 | `GET /projects` 获取项目列表 |
| **语义化 HTTP 方法** | 使用标准 HTTP 方法 | `GET` 查询，`POST` 创建，`PUT` 更新，`DELETE` 删除 |
| **状态码** | 使用标准 HTTP 状态码 | `200` 成功，`201` 创建成功，`404` 未找到 |
| **JSON 格式** | 请求和响应均使用 JSON | `Content-Type: application/json` |

### 1.2 URL 结构

```
基础 URL: http://localhost:8000

API 版本前缀: /api/v1

完整示例: http://localhost:8000/api/v1/projects
```

### 1.3 HTTP 方法语义

| 方法 | 语义 | 幂等性 | 示例 |
|------|------|--------|------|
| `GET` | 获取资源 | 是 | `GET /projects` |
| `POST` | 创建资源 | 否 | `POST /projects` |
| `PUT` | 完整更新资源 | 是 | `PUT /projects/{id}` |
| `PATCH` | 部分更新资源 | 否 | `PATCH /projects/{id}` |
| `DELETE` | 删除资源 | 是 | `DELETE /projects/{id}` |

### 1.4 HTTP 状态码使用

| 状态码 | 含义 | 使用场景 |
|--------|------|----------|
| `200 OK` | 成功 | GET、PUT、PATCH 成功 |
| `201 Created` | 创建成功 | POST 创建资源成功 |
| `204 No Content` | 无内容 | DELETE 成功 |
| `400 Bad Request` | 请求错误 | 参数验证失败 |
| `401 Unauthorized` | 未认证 | 缺少或无效的 Token |
| `403 Forbidden` | 禁止访问 | 无权限访问资源 |
| `404 Not Found` | 未找到 | 资源不存在 |
| `422 Unprocessable Entity` | 无法处理 | 请求格式正确但语义错误 |
| `500 Internal Server Error` | 服务器错误 | 服务器内部异常 |

---

## 2. 认证机制

### 2.1 JWT (JSON Web Token) 认证

RentWise 使用 JWT 进行用户认证：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          JWT 认证流程                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. 用户注册/登录                                                          │
│      ┌─────────┐         ┌─────────┐         ┌─────────┐                   │
│      │  Client │ ──────▶ │  Server │ ──────▶ │返回 JWT │                   │
│      └─────────┘         └─────────┘         └─────────┘                   │
│                                                                             │
│   2. 存储 Token                                                             │
│      ┌─────────┐                                                           │
│      │ Browser │ 存储 JWT 到 localStorage                                   │
│      └─────────┘                                                           │
│                                                                             │
│   3. 发送请求                                                               │
│      ┌─────────┐         ┌─────────┐                                       │
│      │  Client │ ──────▶ │  Server │                                       │
│      └─────────┘         └─────────┘                                       │
│      Header: Authorization: Bearer <token>                                 │
│                                                                             │
│   4. 验证 Token                                                             │
│      ┌─────────┐         ┌─────────┐         ┌─────────┐                   │
│      │  Server │ ──────▶ │验证 JWT │ ──────▶ │返回数据 │                   │
│      └─────────┘         └─────────┘         └─────────┘                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Token 结构

JWT Token 包含三部分：

```
Header.Payload.Signature

示例:
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.
eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.
SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
```

**Payload 内容**：
- `sub`: 用户 ID
- `exp`: 过期时间
- `iat`: 签发时间

### 2.3 Token 有效期

```
默认有效期: 7 天 (7 days = 604800 秒)

配置项: ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
```

### 2.4 请求示例

```bash
# 登录获取 Token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'

# 使用 Token 访问受保护资源
curl -X GET http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer <your_token>"
```

---

## 3. API 端点列表

### 3.1 认证 API (`/api/v1/auth`)

| 方法 | 端点 | 描述 | 认证 |
|------|------|------|------|
| `POST` | `/register` | 用户注册 | ❌ |
| `POST` | `/login` | 用户登录 | ❌ |
| `GET` | `/me` | 获取当前用户信息 | ✅ |

#### POST /register

**请求体**：
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**响应** (201):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### POST /login

**请求体**：
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**响应** (200):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### GET /me

**请求头**：
```
Authorization: Bearer <token>
```

**响应** (200):
```json
{
  "id": "uuid-string",
  "email": "user@example.com",
  "created_at": "2026-04-05T12:00:00Z"
}
```

---

### 3.2 项目 API (`/api/v1/projects`)

| 方法 | 端点 | 描述 | 认证 |
|------|------|------|------|
| `GET` | `/` | 获取用户项目列表 | ✅ |
| `POST` | `/` | 创建新项目 | ✅ |
| `GET` | `/{project_id}` | 获取项目详情 | ✅ |
| `PUT` | `/{project_id}` | 更新项目 | ✅ |
| `DELETE` | `/{project_id}` | 删除项目 | ✅ |

#### POST /projects

**请求体**：
```json
{
  "title": "九龙租房搜索",
  "max_budget": 15000,
  "preferred_districts": ["Mong Kok", "Prince Edward"],
  "must_have": ["furnished"],
  "deal_breakers": ["shared bathroom"],
  "move_in_target": "2026-05-01"
}
```

**响应** (201):
```json
{
  "id": "uuid-string",
  "title": "九龙租房搜索",
  "status": "active",
  "max_budget": 15000,
  "preferred_districts": ["Mong Kok", "Prince Edward"],
  "created_at": "2026-04-05T12:00:00Z"
}
```

---

### 3.3 候选房源 API (`/api/v1/projects/{project_id}/candidates`)

| 方法 | 端点 | 描述 | 认证 |
|------|------|------|------|
| `POST` | `/import` | 导入候选房源 | ✅ |
| `GET` | `/` | 获取候选列表 | ✅ |
| `GET` | `/{candidate_id}` | 获取候选详情 | ✅ |
| `PUT` | `/{candidate_id}` | 更新候选 | ✅ |
| `DELETE` | `/{candidate_id}` | 删除候选 | ✅ |
| `POST` | `/{candidate_id}/reassess` | 重新评估 | ✅ |
| `POST` | `/{candidate_id}/shortlist` | 加入短名单 | ✅ |
| `POST` | `/{candidate_id}/reject` | 拒绝候选 | ✅ |

#### POST /import

**请求体** (multipart/form-data):
```
listing_text: "房源描述文本..."
chat_text: "聊天记录..."
notes: "用户备注..."
images: [File1, File2, ...]
```

**响应** (201):
```json
{
  "id": "uuid-string",
  "name": "Mong Kok $8000",
  "status": "new",
  "processing_stage": "queued",
  "processing_error": null
}
```

#### GET /{candidate_id}

**响应** (200):
```json
{
  "id": "uuid-string",
  "name": "Mong Kok $8000",
  "status": "follow_up",
  "user_decision": "undecided",
  "extracted_info": {
    "monthly_rent": "$8000",
    "district": "Mong Kok",
    "size_sqft": "500",
    "bedrooms": "1",
    ...
  },
  "cost_assessment": {
    "known_monthly_cost": 8500,
    "monthly_cost_confidence": "high",
    "cost_risk_flag": "none",
    ...
  },
  "clause_assessment": {
    "repair_responsibility_level": "clear",
    "lease_term_level": "standard",
    ...
  },
  "candidate_assessment": {
    "potential_value_level": "high",
    "next_best_action": "schedule_viewing",
    "status": "follow_up",
    "labels": ["Mong Kok", "Low price"],
    "summary": "This candidate has strong upside..."
  }
}
```

---

### 3.4 仪表盘 API (`/api/v1/projects/{project_id}/dashboard`)

| 方法 | 端点 | 描述 | 认证 |
|------|------|------|------|
| `GET` | `/` | 获取仪表盘数据 | ✅ |

#### GET /dashboard

**响应** (200):
```json
{
  "statistics": {
    "total": 10,
    "new": 2,
    "needs_info": 3,
    "follow_up": 3,
    "shortlisted": 1,
    "rejected": 1
  },
  "current_advice": "You have 2 candidates ready for comparison...",
  "priority_candidates": [
    {
      "id": "uuid-string",
      "name": "Mong Kok $8000",
      "next_action": "schedule_viewing",
      "summary": "Ready for viewing..."
    }
  ],
  "investigation_items": [
    {
      "category": "cost",
      "title": "Verify management fee",
      "question": "Is the management fee included in the rent?",
      "priority": "high",
      "candidate_names": ["Mong Kok $8000", "Prince Edward $10000"]
    }
  ]
}
```

---

### 3.5 调查 API (`/api/v1/projects/{project_id}/investigation`)

| 方法 | 端点 | 描述 | 认证 |
|------|------|------|------|
| `POST` | `/run` | 运行调查工作流 | ✅ |
| `GET` | `/current` | 获取当前调查状态 | ✅ |

---

### 3.6 对比 API (`/api/v1/projects/{project_id}/compare`)

| 方法 | 端点 | 描述 | 认证 |
|------|------|------|------|
| `POST` | `/` | 对比选中的候选房源 | ✅ |

#### POST /compare

**请求体**：
```json
{
  "candidate_ids": ["uuid-1", "uuid-2", "uuid-3"]
}
```

**响应** (200):
```json
{
  "groups": {
    "best_option": [
      {
        "candidate_id": "uuid-1",
        "reason": "Most complete information and lowest risk"
      }
    ],
    "viable_alternatives": [
      {
        "candidate_id": "uuid-2",
        "reason": "Good value but needs clause verification"
      }
    ],
    "not_ready": [],
    "likely_drop": [
      {
        "candidate_id": "uuid-3",
        "reason": "Over budget and missing key information"
      }
    ]
  },
  "briefing": {
    "current_take": "Candidate A is the current lead...",
    "why_now": "It has the clearest cost structure...",
    "what_could_change": "If Candidate B's management fee is included...",
    "today_s_move": "Contact Candidate A's agent first...",
    "confidence_note": "Moderately stable comparison..."
  },
  "explanations": [
    {
      "candidate_id": "uuid-1",
      "why_in_group": "Best combination of cost clarity and fit",
      "main_tradeoff": "Slightly smaller than average",
      "open_blocker": "None critical",
      "next_action": "Schedule viewing this week"
    }
  ]
}
```

---

## 4. 后台处理模式

### 4.1 异步处理流程

候选房源导入采用异步后台处理，避免长时间阻塞请求：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          后台处理流程                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Client                    Server                    Background            │
│     │                         │                           │                 │
│     │  POST /import           │                           │                 │
│     │ ──────────────────────▶ │                           │                 │
│     │                         │ 创建 Candidate            │                 │
│     │                         │ 状态: queued              │                 │
│     │                         │                           │                 │
│     │  返回 201 Created       │                           │                 │
│     │ ◀────────────────────── │                           │                 │
│     │                         │                           │                 │
│     │                         │ 启动后台任务 ───────────▶ │                 │
│     │                         │                           │                 │
│     │                         │                  OCR 处理 │                 │
│     │                         │                  提取信息 │                 │
│     │                         │                  评估分析 │                 │
│     │                         │                           │                 │
│     │  GET /candidates/{id}   │                           │                 │
│     │ ──────────────────────▶ │                           │                 │
│     │                         │ 返回当前状态              │                 │
│     │ ◀────────────────────── │ processing_stage: running │                 │
│     │                         │                           │                 │
│     │  (轮询直到完成)          │                           │                 │
│     │                         │                           │                 │
│     │  GET /candidates/{id}   │                           │                 │
│     │ ──────────────────────▶ │                           │                 │
│     │                         │ 返回完成状态              │                 │
│     │ ◀────────────────────── │ processing_stage: completed                │
│     │                         │                           │                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 处理状态机

```
┌─────────┐     开始处理      ┌─────────────┐     OCR 完成     ┌────────────┐
│ queued  │ ───────────────▶ │ running_ocr │ ───────────────▶ │ extracting │
└─────────┘                  └─────────────┘                  └────────────┘
                                    │                               │
                                    │ OCR 失败                      │ 提取失败
                                    ▼                               ▼
                              ┌───────────┐                   ┌───────────┐
                              │  failed   │ ◀─────────────────│  failed   │
                              └───────────┘                   └───────────┘
                                                                    │
                                                                    │ 提取成功
                                                                    ▼
                                                              ┌───────────┐
                                                              │ completed │
                                                              └───────────┘
```

### 4.3 轮询机制

前端使用轮询检查处理状态：

```javascript
// 前端轮询逻辑 (简化版)
async function pollCandidateStatus(candidateId) {
  const response = await fetch(`/api/v1/projects/${projectId}/candidates/${candidateId}`);
  const candidate = await response.json();

  if (candidate.processing_stage === 'completed') {
    return candidate; // 处理完成
  }

  if (candidate.processing_stage === 'failed') {
    throw new Error(candidate.processing_error);
  }

  // 继续等待
  await new Promise(resolve => setTimeout(resolve, 2000));
  return pollCandidateStatus(candidateId);
}
```

---

## 5. 错误处理

### 5.1 错误响应格式

所有错误使用统一格式：

```json
{
  "detail": "Error message describing what went wrong"
}
```

### 5.2 常见错误示例

**认证错误** (401):
```json
{
  "detail": "Invalid or expired token"
}
```

**权限错误** (403):
```json
{
  "detail": "You do not have permission to access this resource"
}
```

**资源不存在** (404):
```json
{
  "detail": "Project not found"
}
```

**验证错误** (422):
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "Invalid email format",
      "type": "value_error.email"
    }
  ]
}
```

---

## 6. API 文档

FastAPI 自动生成交互式 API 文档：

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

## 相关文档

- [项目概述](./overview.md) — 产品介绍和功能说明
- [技术架构](./architecture.md) — 系统设计和技术选型
- [AI 功能实现](./ai-features.md) — OCR、LLM、评估算法详解
- [数据模型](./data-model.md) — 数据库结构说明
