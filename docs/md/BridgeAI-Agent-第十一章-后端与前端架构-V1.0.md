---
title: BridgeAI-Agent 第十一章 后端与前端架构
version: V1.0
status: 正式版
updated: 2026-07-30
---

# 第十一章 后端与前端架构

| 项目 | 内容 |
|---|---|
| 文档编号 | BridgeAI-Agent-docs-11 |
| 章节 | 第十一章 后端与前端架构 |
| 版本 | V1.0 |
| 日期 | 2026-07-30 |
| 适用范围 | 桥梁与道路巡检 AI Agent 第一阶段 |
| 后端基线 | FastAPI + PostgreSQL/PostGIS + Redis + MinIO + Qdrant + LangGraph |
| 前端基线 | Vue Web 工作台 + TypeScript + 组件化任务界面 |
| 前置章节 | 第二章总体架构、第三章 Agent、第四章 Tool SDK、第五章 Workflow、第八章数据与数据库、第九章 MCP、第十章 Prompt 与结构化输出 |

## 11.1 本章目标

本章定义 BridgeAI-Agent 的后端与前端架构，使前十章定义的 Agent、Workflow、Tool、RAG、Memory、数据库、MCP 和结构化输出能力，能够通过稳定的应用服务和可用的巡检工作台交付给工程人员。

第十一章关注的是“系统如何被使用、服务如何承载业务闭环、前后端如何共同维护证据链”，而不是简单罗列后端接口或前端页面。桥梁与道路巡检系统的难点在于：任务时间长、文件体积大、影像与地图并存、AI 结果需要人工复核、报告草稿需要证据引用、正式签发必须可审计。因此，后端和前端必须围绕任务、证据、复核和报告四个核心对象设计。

本章交付以下内容：

- 后端总体分层、服务模块、API 边界和运行拓扑；
- API Gateway、认证授权、组织/项目上下文、RLS 透传和服务身份；
- FastAPI 应用服务、OpenAPI 契约、WebSocket/SSE 实时状态和后台任务边界；
- Workflow、Agent、Tool、RAG、Memory、MCP、Artifact、Report 和 Audit 服务集成；
- Vue 前端工作台的信息架构、路由、状态管理和关键页面；
- 影像/视频/地图/病害图层、证据引用、人工复核和报告草稿交互；
- 文件上传下载、大对象访问、安全、可观测性、测试和发布要求；
- 第一阶段实施里程碑和 ADR。

## 11.2 总体架构定位

BridgeAI-Agent 的后端不是一个通用 AI 聊天服务，前端也不是一个普通文件管理器。二者共同组成面向桥梁与道路巡检的工程作业平台。

```text
用户 / 工程师 / 管理员
        │
        ▼
Vue Web 工作台
任务创建 / 影像查看 / 病害复核 / 证据引用 / 报告草稿 / 签发下载
        │
        ▼
API Gateway + FastAPI Application Services
认证 / 权限 / 组织项目上下文 / API 契约 / 实时事件
        │
        ▼
Domain Services
Task / Workflow / Agent / Tool / RAG / Memory / Report / Artifact / Audit
        │
        ▼
Infrastructure
PostgreSQL + PostGIS / Redis / MinIO / Qdrant / MLX / YOLO / LangGraph Checkpoint
```

后端负责维护事实、状态、权限、副作用和审计；前端负责把复杂巡检任务呈现为可操作、可复核、可解释的工作台。任何业务事实都不能只存在于浏览器状态中，任何正式业务动作都必须经过后端权限、状态机和审计校验。

## 11.3 后端架构原则

后端遵循以下原则：

1. **应用服务承接请求，领域服务承载规则。** FastAPI 路由层只负责协议适配、参数校验和请求上下文注入，不堆积复杂业务规则。
2. **Workflow 是长任务主线。** 任务创建、节点执行、人工复核、报告草稿和签发状态都要落在 Workflow 可见状态中。
3. **PostgreSQL 是业务事实权威源。** 前端展示、RAG、Memory、报告和审计均从权威记录或其派生引用恢复。
4. **Artifact 以引用流转。** 原始影像、视频、点云、覆盖图、报告文件和模型产物以对象存储版本和数据库元数据共同表达。
5. **RLS 上下文由后端注入。** 前端传来的组织、项目和角色只作为路由意图，不能作为授权事实。
6. **副作用必须幂等。** 文件上传、任务创建、Tool 调用、报告渲染、复核提交和签发必须使用幂等键或数据库唯一约束。
7. **实时状态可恢复。** WebSocket 或 SSE 只用于推送增量，断线后通过 REST 拉取当前状态。
8. **错误可解释。** API 错误必须包含错误码、用户可读信息、可恢复动作和审计关联 ID。

## 11.4 前端架构原则

前端遵循以下原则：

1. **任务工作台优先。** 用户的主要入口不是聊天框，而是可查看任务状态、影像、病害、证据和报告的工作台。
2. **AI 输出必须可追溯。** 前端展示每个 AI 结论时，应能展开来源 Tool、RAG Evidence、Memory Context、人工复核记录和报告引用。
3. **复核动作显式化。** 确认、驳回、要求补充证据、修改草稿和签发下载均为清晰按钮和表单，不隐藏在自然语言对话里。
4. **大对象懒加载。** 影像、视频、点云和报告预览按需加载，列表页只展示缩略图、摘要和状态。
5. **权限驱动 UI。** 用户看不到或不可操作的功能必须由后端权限返回，前端只做展示裁剪，不作为安全边界。
6. **实时与可恢复并存。** 进度条和事件流提升体验，刷新页面仍能恢复同一任务状态。
7. **工程表达优先。** 病害、构件、路线、桩号、单位、报告章节和证据引用优先服务工程人员，而非展示模型炫技。

## 11.5 后端分层与模块划分

后端采用六层结构：

| 层级 | 模块 | 职责 |
|---|---|---|
| Gateway | API Gateway、认证、限流、CORS、审计入口 | 接收请求、校验身份、建立请求上下文 |
| Application | FastAPI Routers、DTO、OpenAPI、WebSocket/SSE | 协议适配、参数校验、响应格式 |
| Domain | Task、Workflow、Review、Report、Artifact、RAG、Memory、Tool | 业务规则和领域用例 |
| Orchestration | LangGraph Runtime、Agent Runner、Tool Router | 长任务编排、节点执行和恢复 |
| Repository | PostgreSQL Repository、Object Store Client、Qdrant Client | 持久化访问和事务边界 |
| Infrastructure | Redis、MinIO、MLX/YOLO、日志、指标、追踪 | 运行支撑和外部资源 |

建议目录结构：

```text
backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── v1/
│   │   │   ├── tasks.py
│   │   │   ├── inspections.py
│   │   │   ├── artifacts.py
│   │   │   ├── reviews.py
│   │   │   ├── reports.py
│   │   │   ├── rag.py
│   │   │   ├── memory.py
│   │   │   └── admin.py
│   │   └── ws/
│   │       └── task_events.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── request_context.py
│   │   ├── errors.py
│   │   └── observability.py
│   ├── domains/
│   │   ├── task/
│   │   ├── workflow/
│   │   ├── inspection/
│   │   ├── review/
│   │   ├── report/
│   │   ├── artifact/
│   │   ├── rag/
│   │   └── memory/
│   ├── orchestration/
│   │   ├── agent_runner.py
│   │   ├── workflow_runtime.py
│   │   └── tool_router.py
│   └── repositories/
│       ├── postgres/
│       ├── object_store/
│       └── vector_store/
```

路由层不得直接调用底层数据库客户端。所有写操作必须进入领域服务，由领域服务建立事务、调用 Repository、写审计和发布 Outbox。

## 11.6 API Gateway 与请求上下文

API Gateway 是前端和外部系统进入 BridgeAI-Agent 的统一入口。第一阶段可以作为 FastAPI 前置中间件或独立网关部署；生产部署时建议与反向代理、TLS、限流和认证服务配合。

### 11.6.1 请求上下文

每个请求必须生成 `RequestContext`：

```json
{
  "request_id": "req_20260730_001",
  "trace_id": "trace_8af2",
  "actor_id": "user_023",
  "actor_type": "human_user",
  "organization_id": "org_001",
  "project_scope": ["project_g104_bridge_03"],
  "roles": ["bridge_engineer", "report_reviewer"],
  "auth_method": "session_token",
  "ip_address": "10.0.0.18",
  "user_agent": "BridgeAI-Web/1.0"
}
```

`organization_id`、`project_scope` 和 `roles` 来自认证与授权服务，不从前端请求体直接采信。进入 PostgreSQL 事务前，后端将这些值写入受控 session context，用于 RLS 和审计。

### 11.6.2 Gateway 职责

| 职责 | 说明 |
|---|---|
| TLS 终止 | 生产环境必须使用 HTTPS |
| 身份校验 | 验证 session、JWT、OIDC 或内网服务令牌 |
| 组织/项目解析 | 根据用户身份和路由资源计算 scope |
| 限流 | 按用户、项目、接口和风险等级限制 |
| 请求体大小控制 | 上传接口与普通 JSON 接口分开限制 |
| 审计关联 | 生成 request_id、trace_id |
| 安全头 | 设置 CSP、下载保护、跨域策略 |
| 路由分发 | 分发到 API、WebSocket、MCP 或静态资源 |

## 11.7 认证、授权与 RLS 透传

BridgeAI-Agent 的权限模型至少包含四个维度：

| 维度 | 示例 | 控制点 |
|---|---|---|
| 组织 | 检测单位、业主单位 | API Gateway、RLS |
| 项目 | 某桥梁定检项目、某道路巡检项目 | 应用服务、RLS |
| 角色 | 采集员、检测工程师、报告审核人、管理员 | Policy Engine |
| 动作 | 上传、查看、复核、签发、删除、导出 | Domain Service |

后端授权采用“粗粒度路由权限 + 领域策略 + RLS”的组合：

1. Gateway 校验用户是否登录和组织有效；
2. API 层校验接口所需 scope；
3. Domain Service 校验资源状态和动作权限；
4. Repository 在事务中设置 RLS 上下文；
5. PostgreSQL 强制行级隔离；
6. 审计记录最终决策。

前端可根据后端返回的 `allowed_actions` 控制按钮可见性，但安全边界必须由后端执行。

## 11.8 FastAPI 应用服务架构

FastAPI 适合作为第一阶段应用服务承载，因为它可以基于 Python 类型声明生成 OpenAPI 文档，支持依赖注入、安全依赖、异步接口、WebSocket 和后台任务。BridgeAI-Agent 使用这些能力时必须保持边界清晰。

### 11.8.1 路由分组

| 路由组 | 前缀 | 职责 |
|---|---|---|
| Task API | `/api/v1/tasks` | 创建、查询、取消、恢复任务 |
| Inspection API | `/api/v1/inspections` | 影像批次、病害候选、量测结果 |
| Artifact API | `/api/v1/artifacts` | 上传、下载、预览、签名访问 |
| Review API | `/api/v1/reviews` | 领取、提交、驳回复核项 |
| Report API | `/api/v1/reports` | 草稿、引用、渲染、签发、下载 |
| Knowledge API | `/api/v1/rag` | 检索、证据包、引用校验 |
| Memory API | `/api/v1/memory` | Context Manifest、候选记忆、反馈 |
| Admin API | `/api/v1/admin` | 健康、版本、配置、审计查询 |
| Event API | `/api/v1/events` | SSE 或 WebSocket 任务事件 |

### 11.8.2 依赖注入边界

FastAPI 依赖注入用于：

- 注入 `RequestContext`；
- 注入数据库事务或 Unit of Work；
- 注入当前用户和角色；
- 注入服务对象；
- 注入审计上下文；
- 注入 OpenAPI security scope。

不得用于隐藏业务流程。例如，不应在依赖函数里自动触发 Tool 调用、报告签发或删除传播。

### 11.8.3 后台任务边界

FastAPI BackgroundTasks 可用于轻量、短时、可丢失后重试的动作，例如发送非关键通知或写入附属日志。桥梁巡检主流程、模型推理、报告渲染、索引重建和 Outbox 发布不得依赖请求进程内的临时后台任务，而应进入 Workflow、任务队列或受控 Worker。

## 11.9 API 契约与版本策略

所有前后端交互必须以版本化 API 契约为准。REST 路径采用 `/api/v1` 前缀，事件和 Schema 也要显式版本化。

### 11.9.1 API 响应 Envelope

```json
{
  "request_id": "req_20260730_001",
  "trace_id": "trace_8af2",
  "data": {
    "task_id": "task_7e33",
    "status": "running"
  },
  "warnings": [],
  "meta": {
    "api_version": "v1",
    "server_time": "2026-07-30T11:00:00+08:00"
  }
}
```

### 11.9.2 错误模型

```json
{
  "request_id": "req_20260730_001",
  "trace_id": "trace_8af2",
  "error": {
    "code": "REPORT_REVIEW_REQUIRED",
    "message": "该报告草稿仍存在待复核病害，不能签发。",
    "severity": "warning",
    "retryable": false,
    "user_action": "请完成病害复核后重新提交签发。",
    "details": {
      "review_item_count": 3
    }
  }
}
```

错误码按领域前缀命名：

| 前缀 | 领域 |
|---|---|
| `AUTH_` | 认证授权 |
| `TASK_` | 任务生命周期 |
| `WORKFLOW_` | 编排和恢复 |
| `TOOL_` | 工具调用 |
| `RAG_` | 知识检索 |
| `MEMORY_` | 上下文记忆 |
| `ARTIFACT_` | 文件和对象 |
| `REVIEW_` | 人工复核 |
| `REPORT_` | 报告草稿、渲染、签发 |
| `SECURITY_` | 安全拦截 |

### 11.9.3 分页与排序

列表接口默认使用 keyset pagination，避免深分页在大项目中退化。

```json
{
  "items": [],
  "page": {
    "limit": 50,
    "next_cursor": "eyJ0IjoiMjAyNi0wNy0zMCJ9",
    "has_more": true
  }
}
```

排序字段必须是受控白名单，不允许前端传任意 SQL 字段名。

## 11.10 任务与 Workflow API

任务 API 是后端主入口。前端创建任务时，不直接创建 LangGraph thread 或 Tool 调用，而是创建业务任务。

### 11.10.1 创建巡检任务

```http
POST /api/v1/tasks
Idempotency-Key: task-create-project-g104-20260730-001
```

```json
{
  "task_type": "bridge_inspection",
  "project_id": "project_g104_bridge_03",
  "asset_id": "bridge_03",
  "input_artifact_ids": ["art_batch_001"],
  "expected_outputs": ["damage_list", "review_items", "report_draft"],
  "workflow_template_id": "bridge_inspection_default.v1",
  "options": {
    "enable_rag": true,
    "enable_memory": true,
    "report_template_id": "bridge_regular_inspection.v1"
  }
}
```

后端返回：

```json
{
  "task_id": "task_7e33",
  "run_id": "run_20260730_001",
  "status": "queued",
  "allowed_actions": ["view", "cancel"],
  "event_stream": "/api/v1/tasks/task_7e33/events"
}
```

### 11.10.2 任务状态模型

| 状态 | 含义 | 前端表现 |
|---|---|---|
| `draft` | 已创建但未提交 | 可编辑输入 |
| `queued` | 等待执行 | 显示排队 |
| `running` | Workflow 执行中 | 显示节点进度 |
| `waiting_review` | 等待人工复核 | 高亮待办 |
| `waiting_input` | 等待追加资料 | 提示缺失字段 |
| `failed_recoverable` | 可恢复失败 | 提供重试或转人工 |
| `failed_terminal` | 终态失败 | 展示错误和审计 ID |
| `completed` | 流程完成 | 可查看成果 |
| `archived` | 已归档 | 只读 |

前端不得通过状态更新接口自行把任务从 `waiting_review` 改为 `running`。所有状态迁移由 Workflow Service 执行。

## 11.11 Agent、Tool、RAG、Memory 与 MCP 集成

后端应用服务与 Agent/Tool 等能力通过领域服务集成，而不是让前端直接调用底层工具。

```text
Frontend
  -> Task API
  -> Workflow Service
  -> Agent Runner
  -> Tool Router
      ├── Internal Tool SDK
      ├── MCP Server Adapter
      ├── RAG Service
      ├── Memory Service
      └── Report Service
```

### 11.11.1 集成规则

| 能力 | 后端入口 | 前端可见内容 | 前端不可见内容 |
|---|---|---|---|
| Agent | Task/Workflow API | 计划摘要、节点解释、复核原因 | 系统 Prompt、内部策略 |
| Tool | Tool Result 摘要 | 结果、Artifact、错误码 | 原始执行环境、密钥 |
| RAG | Evidence Pack API | 证据标题、条款、引用片段 | 无权限知识、索引细节 |
| Memory | Context Manifest API | 项目术语、偏好、冲突提示 | 原始 Memory 存储和越权记录 |
| MCP | Gateway/Admin API | Server 能力清单、健康状态 | Token、内部 Tool 映射细节 |
| Report | Report API | 草稿、引用、渲染文件 | 签名私钥、内部模板路径 |

### 11.11.2 Tool Result 展示

前端只展示后端整理后的 Tool Result 摘要和 Artifact 引用。对于大型输出，例如检测覆盖图、切片图片、表格、GeoJSON 和报告预览，前端通过 Artifact API 获取受控访问 URL 或分块数据。

## 11.12 Artifact 与文件服务架构

巡检系统存在大量对象数据：原始图片、视频、无人机元数据、点云、模型输出、覆盖图、报告草稿和签发文件。文件服务必须以“对象字节 + 数据库元数据 + 权限校验 + 审计”共同表达。

### 11.12.1 上传流程

```text
Frontend 请求上传会话
  -> Artifact API 创建 upload_session
  -> 返回分片大小、允许类型、临时上传凭证
  -> Frontend 分片上传到对象存储或上传代理
  -> Artifact Service 校验大小、类型、sha256、项目权限
  -> PostgreSQL 登记 artifact revision
  -> 发布 Outbox: artifact_uploaded
```

### 11.12.2 下载与预览

下载报告、预览图片和查看覆盖图时，前端不能直接拼接对象存储路径。必须通过 Artifact API：

```http
GET /api/v1/artifacts/{artifact_id}/access?purpose=preview
```

返回：

```json
{
  "artifact_id": "art_overlay_8af1",
  "access_url": "https://bridgeai.local/artifacts/signed/...",
  "expires_at": "2026-07-30T11:10:00+08:00",
  "content_type": "image/png",
  "sha256": "b7d2f4d7a5b6c8d9",
  "allowed_operations": ["preview"]
}
```

签发报告下载必须记录下载审计，包括下载人、时间、IP、报告修订、Artifact 版本和用途。

## 11.13 实时事件与通知

任务执行时间可能从数秒到数小时。前端需要实时展示进度，但实时通道不应成为权威状态源。

### 11.13.1 事件模型

```json
{
  "event_id": "evt_20260730_0008",
  "event_type": "workflow.node_completed",
  "task_id": "task_7e33",
  "run_id": "run_20260730_001",
  "node": "detect_damage",
  "sequence": 42,
  "occurred_at": "2026-07-30T11:03:00+08:00",
  "payload": {
    "status": "succeeded",
    "summary": "完成 128 张影像检测，发现 18 个候选病害"
  }
}
```

### 11.13.2 WebSocket/SSE 规则

| 规则 | 要求 |
|---|---|
| 认证 | 连接建立时校验 token 和任务权限 |
| 订阅范围 | 只能订阅有权限的 task/project |
| 序号 | 每个任务事件有递增 sequence |
| 恢复 | 断线后使用 `after_sequence` 补齐 |
| 降级 | 实时通道不可用时轮询 REST |
| 审计 | 高风险事件推送记录投递状态 |

第一阶段可以优先实现 SSE 任务事件流；若需要双向协作、多人复核光标或前端上传过程控制，再引入 WebSocket。

## 11.14 报告服务与签发链路

报告服务负责草稿、引用校验、渲染、复核和签发下载。第十章定义了报告草稿结构化输出；第十一章定义后端与前端如何承载它。

### 11.14.1 报告生命周期

```text
draft_requested
  -> draft_generated
  -> citation_checked
  -> engineer_review_required
  -> reviewer_approved
  -> rendered
  -> signature_required
  -> issued
  -> downloaded / withdrawn
```

### 11.14.2 Report API

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/v1/reports` | POST | 创建报告草稿请求 |
| `/api/v1/reports/{id}` | GET | 获取报告元数据 |
| `/api/v1/reports/{id}/draft` | GET | 获取结构化草稿 |
| `/api/v1/reports/{id}/citations` | GET | 获取引用映射 |
| `/api/v1/reports/{id}/review` | POST | 提交报告复核意见 |
| `/api/v1/reports/{id}/render` | POST | 触发 Word/PDF 渲染 |
| `/api/v1/reports/{id}/issue` | POST | 签发报告 |
| `/api/v1/reports/{id}/download` | GET | 获取签发文件下载 |

`issue` 接口必须校验：

- 报告草稿引用覆盖；
- 所有高风险病害复核完成；
- 报告 Artifact 渲染完成且哈希一致；
- 当前用户具备签发角色；
- 幂等键未冲突；
- 审计事件写入成功。

## 11.15 前端应用架构

前端采用 Vue Web 工作台。Vue 的组件化、响应式、组合式 API 和单文件组件适合构建可逐步扩展的工程业务界面。第一阶段建议使用 TypeScript，避免病害、任务、证据和报告 DTO 在前端变成弱类型散装对象。

建议目录结构：

```text
frontend/
├── src/
│   ├── app/
│   │   ├── main.ts
│   │   ├── router.ts
│   │   └── providers.ts
│   ├── api/
│   │   ├── client.ts
│   │   ├── tasks.ts
│   │   ├── artifacts.ts
│   │   ├── reviews.ts
│   │   └── reports.ts
│   ├── stores/
│   │   ├── auth.store.ts
│   │   ├── project.store.ts
│   │   ├── task.store.ts
│   │   └── event.store.ts
│   ├── pages/
│   │   ├── TaskListPage.vue
│   │   ├── TaskWorkspacePage.vue
│   │   ├── ReviewQueuePage.vue
│   │   ├── ReportWorkspacePage.vue
│   │   └── AdminHealthPage.vue
│   ├── features/
│   │   ├── inspection/
│   │   ├── damage-review/
│   │   ├── evidence/
│   │   ├── report/
│   │   └── artifact-viewer/
│   ├── components/
│   ├── types/
│   └── utils/
```

前端类型应尽量由 OpenAPI 或共享 Schema 生成，避免手工复制后端字段。

## 11.16 前端信息架构与路由

第一阶段前端至少包含以下一级区域：

| 区域 | 路由 | 主要用户 |
|---|---|---|
| 项目总览 | `/projects` | 项目经理、工程师 |
| 任务列表 | `/projects/:projectId/tasks` | 全部业务用户 |
| 任务工作台 | `/tasks/:taskId` | 工程师、复核人 |
| 复核队列 | `/reviews` | 检测工程师、报告审核人 |
| 报告工作台 | `/reports/:reportId` | 报告编制与审核人员 |
| 知识证据 | `/evidence/:packId` | 工程师、知识管理员 |
| 对象预览 | `/artifacts/:artifactId` | 授权用户 |
| 管理后台 | `/admin` | 管理员、运维 |

### 11.16.1 任务工作台布局

```text
┌────────────────────────────────────────────────────────────┐
│ 顶部：项目 / 任务 / 状态 / 主要操作                         │
├───────────────┬──────────────────────────────┬─────────────┤
│ 左侧任务流     │ 中间影像/地图/病害图层         │ 右侧证据面板 │
│ - 节点进度     │ - 图片/视频预览                │ - RAG 引用   │
│ - Tool 结果    │ - 病害框/分割/量测              │ - Memory     │
│ - 复核项       │ - GIS/路线位置                  │ - 审计摘要   │
├───────────────┴──────────────────────────────┴─────────────┤
│ 底部：报告草稿、开放问题、操作日志                           │
└────────────────────────────────────────────────────────────┘
```

任务工作台要让工程人员能够回答四个问题：

1. 当前任务执行到哪里；
2. AI 发现了什么病害；
3. 每个结论依据是什么；
4. 下一步需要谁确认什么。

## 11.17 前端状态管理

前端状态分为四类：

| 状态 | 示例 | 持久位置 | 刷新后恢复 |
|---|---|---|---|
| 会话状态 | 当前用户、组织、角色 | 后端 session / token | 是 |
| 业务状态 | 任务、病害、复核、报告 | 后端数据库 | 是 |
| 实时状态 | 当前节点进度、事件流连接 | 事件流 + REST 查询 | 是 |
| UI 状态 | 面板展开、筛选、缩放、选中图层 | 浏览器本地或 URL | 部分恢复 |

前端不得把复核结论、报告签发状态、病害确认状态只保存在本地 store。任何正式操作提交后必须以后端返回状态为准。

### 11.17.1 Store 划分

| Store | 职责 |
|---|---|
| `auth.store` | 用户、组织、角色、权限能力 |
| `project.store` | 当前项目、资产、构件字典 |
| `task.store` | 任务详情、节点状态、允许动作 |
| `event.store` | SSE/WebSocket 连接、事件序号、断线恢复 |
| `artifact.store` | 缩略图、预览 URL、下载状态 |
| `review.store` | 待复核项、领取状态、提交结果 |
| `report.store` | 报告草稿、引用、开放问题、渲染文件 |

## 11.18 影像、地图与病害复核界面

病害复核是前端最关键的专业工作区之一。界面必须同时展示影像证据、病害候选、量测结果、AI 置信度、复核状态和引用关系。

### 11.18.1 影像查看

影像查看器应支持：

- 原图、缩略图和切片加载；
- 病害框、分割轮廓、量测线、构件边界叠加；
- 按病害类型、置信度、复核状态筛选；
- 多图批量切换；
- 图像质量问题提示；
- Artifact 版本和哈希展示；
- 快捷键支持确认、驳回和跳转。

### 11.18.2 地图与线性定位

道路和桥梁场景既有 GIS 坐标，也有路线桩号、构件相对位置和图片像素位置。前端地图模块应支持：

| 定位方式 | 前端呈现 |
|---|---|
| GIS 坐标 | 地图点、线、面图层 |
| 路线桩号 | 线性参考轴和路段定位 |
| 构件相对位置 | 构件树和构件示意 |
| 图像像素位置 | 图片标注层 |

坐标系、SRID、桩号基线和构件版本必须可见或可追溯，避免工程人员误解位置。

### 11.18.3 复核操作

复核操作包括：

- 确认候选病害；
- 驳回误检；
- 修改病害类别；
- 补充位置描述；
- 标记量测需复查；
- 要求补充影像或证据；
- 添加工程备注；
- 将问题转报告复核。

所有复核操作必须写入后端 Review API，并返回新的复核状态和审计 ID。

## 11.19 证据、RAG 与 Memory 前端呈现

前端必须把“依据是什么”变成可见的一等信息。RAG 和 Memory 不能只出现在模型回答里，而应作为证据面板和上下文面板呈现。

### 11.19.1 证据面板

证据面板展示：

- RAG Evidence Pack ID；
- 规范或案例标题；
- 版本、条款号、片段摘要；
- 适用性说明；
- 引用到的报告句子；
- 权限和可见性提示；
- 冲突证据警告。

证据面板不得展示无权限全文。前端收到的是后端过滤后的证据摘要和受控片段。

### 11.19.2 Memory 面板

Memory 面板展示：

- 项目术语；
- 构件别名；
- 报告偏好；
- 历史人工修订；
- 冲突记忆；
- 本次是否被用于 Prompt Context。

Memory 面板必须明确“上下文线索”身份，不能把 Memory 内容展示为权威工程事实。

## 11.20 报告草稿与签发前端

报告工作台应支持结构化草稿编辑，而不是只给用户一个富文本框。

### 11.20.1 报告草稿视图

报告草稿视图分为：

| 区域 | 内容 |
|---|---|
| 章节树 | 报告章节、状态、开放问题数量 |
| 草稿编辑区 | 段落文本、引用标记、修改建议 |
| 引用面板 | claim 到 evidence refs 的映射 |
| 病害清单 | 与报告项关联的病害和复核状态 |
| 开放问题 | 缺证据、冲突、量测复核、模板缺口 |
| 操作区 | 保存草稿、提交复核、渲染预览、签发 |

### 11.20.2 签发门禁

签发按钮只有在后端返回 `allowed_actions` 包含 `issue_report` 时可用。即使按钮可见，点击后仍必须由后端重新校验：

- 当前报告修订；
- 当前用户角色；
- 所有复核项状态；
- 引用覆盖；
- Artifact 渲染结果；
- 幂等键；
- 审计写入。

前端不得提供“强制签发”入口。

## 11.21 管理后台与运维页面

第一阶段管理后台应以安全只读为主，避免在前端暴露高风险运维动作。

| 页面 | 内容 | 风险 |
|---|---|---|
| 系统健康 | API、数据库、Redis、MinIO、Qdrant、Worker 状态 | 低 |
| 版本信息 | 后端版本、Prompt/Schema/Tool/MCP 版本 | 低 |
| 任务监控 | 队列长度、失败任务、重试统计 | 中 |
| 审计查询 | 用户操作、报告下载、复核记录 | 中 |
| 权限诊断 | 当前用户 scope、项目角色 | 中 |
| MCP 能力 | Server 状态、工具清单、协议版本 | 中 |
| 索引状态 | RAG/Memory 索引版本和延迟 | 中 |

高风险动作，如删除对象、重放 Outbox、强制迁移、撤销签发、批量权限调整，应进入后端受控 Runbook 或双人审批流程，不在普通前端管理页面直接暴露。

## 11.22 安全、可观测性与测试

### 11.22.1 安全控制

| 控制 | 要求 |
|---|---|
| CSRF | Cookie 会话场景启用 CSRF 或 SameSite 策略 |
| XSS | 报告草稿、RAG 片段、OCR 文本输出转义 |
| 文件上传 | 类型、大小、sha256、病毒/恶意内容扫描 |
| 下载 | 短期签名 URL、权限校验、下载审计 |
| 权限 | 后端强制校验，前端只做展示 |
| 注入防护 | 用户内容、RAG、Memory、Tool Result 标注为数据 |
| 密钥 | 前端不保存长期密钥或对象存储凭据 |
| 审计 | 高风险动作记录 actor、scope、对象和结果 |

### 11.22.2 可观测性

后端至少采集：

- HTTP 请求量、延迟、错误率；
- WebSocket/SSE 连接数和断线次数；
- Workflow 节点耗时和失败率；
- Tool 调用耗时、重试和错误码；
- Artifact 上传下载吞吐和失败率；
- RAG/Memory 查询延迟和命中质量摘要；
- 报告渲染耗时和签发失败原因；
- PostgreSQL、Redis、MinIO、Qdrant 健康状态。

前端至少采集：

- 页面加载时间；
- 任务工作台首屏时间；
- 大图预览加载失败；
- 事件流断线恢复；
- API 错误码分布；
- 复核提交失败；
- 报告草稿保存失败。

日志、指标和追踪均使用 `request_id`、`trace_id`、`task_id`、`run_id`、`organization_id` 和 `project_id` 关联。

### 11.22.3 测试矩阵

| 测试类型 | 后端 | 前端 |
|---|---|---|
| 单元测试 | Domain Service、Policy、DTO 校验 | 组件、Store、格式化器 |
| 契约测试 | OpenAPI、错误模型、事件 Schema | API Client 与 Mock Server |
| 集成测试 | Task -> Workflow -> Tool -> Report | 页面工作流和状态恢复 |
| 权限测试 | 多租户、角色、RLS 正负样本 | 按权限隐藏/禁用操作 |
| 大文件测试 | 分片上传、预览、下载审计 | 上传进度、断点失败恢复 |
| 实时测试 | SSE/WebSocket 断线续传 | 事件序号、刷新恢复 |
| 安全测试 | XSS、上传、越权、注入样本 | 富文本转义、权限 UI |
| 可用性测试 | 错误可解释、重试可控 | 工程复核路径是否清晰 |

## 11.23 第一阶段实施里程碑

### 11.23.1 M1：后端应用服务骨架

目标：

- 建立 FastAPI 应用骨架和 `/api/v1` 路由；
- 完成 RequestContext、认证占位、错误模型和 OpenAPI；
- 接入 PostgreSQL Repository、Artifact 元数据查询和健康检查；
- 建立任务创建、查询和事件模型的最小闭环。

验收：

- OpenAPI 能生成 API 文档；
- 任务创建接口写入数据库并返回 task/run；
- 错误响应符合统一模型；
- 多组织/项目权限样本能被区分。

### 11.23.2 M2：Workflow 与 Artifact 工作台

目标：

- 后端接入 Workflow Runtime 和任务事件流；
- 实现 Artifact 上传会话、缩略图和预览访问；
- 前端实现项目、任务列表和任务工作台；
- 实现 SSE 或 WebSocket 任务进度。

验收：

- 页面刷新后能恢复任务状态；
- 事件流断线后能补齐；
- 未授权项目 Artifact 无法访问；
- 大图预览不阻塞任务列表。

### 11.23.3 M3：病害复核、证据与报告草稿

目标：

- 后端实现 Review API、RAG Evidence API、Memory Context API 和 Report Draft API；
- 前端实现影像标注、病害复核、证据面板和报告草稿工作台；
- 报告草稿绑定 Citation Map 和开放问题；
- 复核提交进入 Workflow 状态。

验收：

- 候选病害可确认、驳回和要求补证；
- 报告草稿每个关键结论可展开证据；
- Memory 冲突能被提示；
- 未完成复核不能签发报告。

### 11.23.4 M4：签发、审计与灰度发布

目标：

- 实现报告渲染、签发和下载审计；
- 实现管理后台健康、版本、任务和审计查询；
- 建立前后端契约测试和端到端冒烟；
- 完成第一阶段灰度发布流程。

验收：

- 签发报告有不可变 Artifact 和审计事件；
- 下载记录能回溯到报告修订；
- 后端和前端版本可在管理后台查看；
- P0 流程冒烟通过：上传 -> 创建任务 -> 检测 -> 复核 -> 草稿 -> 渲染 -> 签发。

## 11.24 架构决策记录

### ADR-011-001：后端采用应用服务 + 领域服务分层

**状态：** Accepted

**背景：** 巡检系统业务规则复杂，若全部写在 API 路由中，会导致权限、状态和审计难以复用。

**决定：** FastAPI 路由只做协议适配，业务规则进入 Domain Service，数据库访问进入 Repository。

**后果：** 代码结构更重，但测试、复用和审计边界更清晰。

### ADR-011-002：前端采用 Vue Web 工作台作为第一阶段主入口

**状态：** Accepted

**背景：** 第二章已将 Web/Vue 作为表现层方向。第一阶段需要快速构建可迭代的任务、复核和报告界面。

**决定：** 前端主入口采用 Vue Web 工作台，桌面端和移动端作为后续适配。

**后果：** 第一阶段集中资源打磨 Web 工作流；现场移动采集能力需要后续独立规划。

### ADR-011-003：实时进度采用事件流，REST 作为权威恢复路径

**状态：** Accepted

**背景：** 长任务需要实时反馈，但实时连接可能断开。

**决定：** 使用 SSE 或 WebSocket 推送任务事件；断线后通过 REST 和事件 sequence 恢复状态。

**后果：** 前端实现略复杂，但不会因连接中断丢失任务状态。

### ADR-011-004：前端不直连对象存储、数据库、Qdrant 或 MCP Server

**状态：** Accepted

**背景：** 直接暴露底层存储或 MCP Server 会绕过权限、审计和业务语义。

**决定：** 前端只能通过后端 API 访问 Artifact、RAG、Memory、MCP 能力和业务数据。

**后果：** 后端需要提供更多领域接口，但权限和审计闭环完整。

### ADR-011-005：报告工作台采用结构化草稿而非纯富文本

**状态：** Accepted

**背景：** 纯富文本难以保存 citation、病害关联、复核状态和开放问题。

**决定：** 报告前端围绕第十章 `ReportDraftOutput`、Citation Map 和开放问题设计。

**后果：** 编辑体验需要专门设计，但报告可审计性和复核效率更高。

### ADR-011-006：管理后台第一阶段以只读诊断为主

**状态：** Accepted

**背景：** 许多运维动作具有高风险，普通 Web 管理页面容易误操作。

**决定：** 第一阶段管理后台只提供健康、版本、任务、审计和权限诊断；高风险操作进入 Runbook 或审批。

**后果：** 运维自动化程度暂时较低，但降低误删和绕过流程风险。

### ADR-011-007：API 契约优先于前端临时字段

**状态：** Accepted

**背景：** 前后端并行开发时，临时字段容易漂移，破坏报告和复核链路。

**决定：** 前端类型由 OpenAPI 或共享 Schema 生成；业务字段变更先改契约，再改实现。

**后果：** 发布流程需要契约检查，但能减少线上字段不一致。

### ADR-011-008：大对象全部通过 Artifact 引用访问

**状态：** Accepted

**背景：** 原始影像、视频、点云和报告文件体积大，且涉及权限和审计。

**决定：** 前端通过 Artifact API 获取预览和下载访问，不直接使用对象存储路径。

**后果：** 文件服务设计更复杂，但可以统一权限、版本、哈希和下载审计。

## 参考资料

1. [FastAPI 官方文档](https://fastapi.tiangolo.com/)
2. [FastAPI：Dependencies](https://fastapi.tiangolo.com/reference/dependencies/)
3. [FastAPI：WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
4. [FastAPI：Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
5. [FastAPI：Security](https://fastapi.tiangolo.com/tutorial/security/)
6. [Vue 官方文档](https://vuejs.org/)
7. [Vue：Single-File Components](https://vuejs.org/guide/scaling-up/sfc.html)
8. [Vue：Composition API](https://vuejs.org/guide/extras/composition-api-faq.html)

## 修订记录

| 版本 | 日期 | 修订内容 | 修订人 |
|---|---|---|---|
| V1.0 | 2026-07-30 | 创建第十一章，定义后端应用服务、前端工作台、API 契约、实时事件、复核报告和审计集成架构 | Codex |
