---
title: BridgeAI-Agent 第九章 MCP 工具接入规范
version: V1.0
status: 正式版
updated: 2026-07-30
---

# 第九章 MCP 工具接入规范

| 项目 | 内容 |
|---|---|
| 文档编号 | BridgeAI-Agent-docs-09 |
| 章节 | 第九章 MCP 工具接入规范 |
| 版本 | V1.0 |
| 日期 | 2026-07-30 |
| 适用范围 | 桥梁与道路巡检 AI Agent 第一阶段 |
| 协议基线 | MCP Specification 2025-11-25 |
| 前置章节 | 第四章 Tool SDK、第五章 Workflow、第六章 RAG、第七章 Memory、第八章数据与数据库设计 |

## 9.1 本章目标

本章定义 BridgeAI-Agent 的 MCP 工具接入规范，使第四章定义的内部 Tool SDK 能够通过标准 MCP Server 暴露给受控 MCP Client、编排框架和工程应用入口。第九章的重点不是“把所有能力改写成 MCP”，而是在稳定的内部工具、数据库权限、Workflow 状态和审计链之上增加标准化互操作层。

本章交付以下内容：

- MCP 在 BridgeAI-Agent 中的定位、边界和组件映射；
- MCP Server、Tool、Resource、Prompt 和传输层的第一阶段设计；
- 内部 Tool SDK 到 MCP Tools 的 Manifest、Schema、Result、错误和 Artifact 映射；
- 组织/项目权限、RLS、OAuth/Token、幂等、Outbox、人工确认和审计规则；
- 面向桥梁与道路巡检的首批 MCP Server 与工具清单；
- 测试验收、运维观测、灰度发布和 ADR。

## 9.2 MCP 的定位与职责边界

MCP 是 Tool 调用、上下文资源和 Prompt 模板的标准化协议层。BridgeAI-Agent 第一阶段采用 **Internal Tool SDK first, MCP Adapter second**：

```text
Agent / Workflow / Human Review
        │
        ▼
Internal Tool SDK + Policy + Repository
        │
        ├── Native Python / LangGraph Adapter
        ├── FastAPI / OpenAPI Adapter
        └── MCP Server Adapter
                │
                ├── tools/list + tools/call
                ├── resources/list + resources/read
                └── prompts/list + prompts/get
```

MCP Server 只能调用已经注册、版本固定、通过测试的内部 Tool。MCP 不替代：

- Workflow 的任务状态、节点恢复、人工复核和幂等控制；
- PostgreSQL 的权威事实、RLS、组合约束和审计；
- MinIO Artifact 的不可变对象版本和 SHA-256 校验；
- Qdrant 的派生索引重建和权限过滤；
- 报告签发、病害确认、删除传播等高风险业务门禁。

## 9.3 官方协议基线与版本策略

本章以 **MCP Specification 2025-11-25** 为协议基线。该版本包含 base protocol、lifecycle、transports、authorization、server tools/resources/prompts、client roots/sampling/elicitation、tasks 和 schema reference。MCP 消息基于 JSON-RPC 2.0；Tool 的 `inputSchema` 和 `outputSchema` 使用 JSON Schema，未显式声明 `$schema` 时按 MCP 规范默认使用 2020-12。

生产实现必须锁定以下版本：

| 项目 | 第一阶段基线 | 升级规则 |
|---|---|---|
| MCP protocolVersion | `2025-11-25` | 新版本先进入兼容评估，不默认跟随 latest |
| JSON-RPC | `2.0` | 只接受规范字段，未知 method 拒绝 |
| JSON Schema | 2020-12 或显式声明版本 | Tool 输入输出变更必须走版本发布 |
| OAuth | MCP HTTP 授权规范引用的 OAuth 2.1/RFC 体系 | 生产部署按企业 IdP 和安全评审锁定 |
| BridgeAI Tool version | `MAJOR.MINOR.PATCH` | 生产 Workflow 固定版本，不隐式升级 |

协议升级不得改变历史任务复现语义。已经签发报告、已确认病害、已发布知识和正式 Memory 的引用快照继续按当时的 Tool、Schema、Prompt 和 Resource 版本恢复。

## 9.4 组件架构与调用链

BridgeAI-Agent 的 MCP 架构分为五层：

| 层级 | 组件 | 责任 |
|---|---|---|
| Host | BridgeAI Web、桌面端、受控第三方 Agent 宿主 | 展示可用工具、发起授权、呈现确认、接收结果 |
| MCP Client | Host 内部客户端或编排框架适配器 | 建立会话、能力协商、发送 JSON-RPC 请求、处理超时 |
| MCP Gateway | BridgeAI MCP 入口 | 认证、限流、租户解析、Server 路由、审计关联 |
| MCP Server Adapter | Inspection/RAG/Report 等领域 Server | 将 MCP method 映射到内部 Tool SDK |
| Internal Tool Runtime | Tool、Repository、Workflow、Outbox | 执行业务逻辑，写入权威状态和审计 |

典型调用链：

```text
Host
  -> MCP Client initialize
  -> MCP Gateway 认证与协议版本检查
  -> Domain MCP Server tools/list
  -> Host 展示工具和风险标识
  -> tools/call
  -> Policy Engine + Tool SDK
  -> PostgreSQL/RLS + Artifact/Qdrant/Redis
  -> Workflow Event + Audit Event
  -> MCP Tool Result
```

所有跨存储副作用必须落到第八章定义的 `idempotency_requests`、`outbox_events`、Artifact Manifest、审计事件和 Workflow 状态中。

## 9.5 MCP Server 分组与部署形态

第一阶段按领域拆分 MCP Server，而不是把全部工具塞进单个超大 Server。

| Server | 主要能力 | 部署建议 | 风险等级 |
|---|---|---|---|
| `bridgeai.inspection` | 影像批次校验、预处理、病害检测、量测、构件映射 | 本地/内网，靠近 GPU 与文件存储 | 中高 |
| `bridgeai.knowledge` | 工程规范检索、条文解释、证据引用 | 内网 HTTP，连接 RAG Service | 中 |
| `bridgeai.memory` | 项目上下文读取、Context Manifest 生成、反馈 | 内网 HTTP，强权限过滤 | 中 |
| `bridgeai.report` | 报告草稿生成、引用校验、Word/PDF 渲染 | 内网 HTTP，生成 Artifact | 高 |
| `bridgeai.workflow` | 创建复核项、查询任务状态、受控重试 | 内网 HTTP，连接 Workflow Service | 高 |
| `bridgeai.admin.readonly` | 健康检查、版本、能力清单、只读诊断 | 运维内网或 stdio | 低中 |

本地开发和单机调试可使用 stdio transport；生产跨进程、跨主机和多用户访问使用 Streamable HTTP，并置于 BridgeAI MCP Gateway 后面。

## 9.6 内部 Tool SDK 到 MCP 的映射

第四章 Tool SDK 是内部权威契约，MCP Tool 是外部可发现视图。映射规则如下：

| Internal Tool SDK | MCP Tool | 规则 |
|---|---|---|
| `ToolManifest.name` | `Tool.name` | 使用稳定小写命名，允许点号表达领域 |
| `ToolManifest.display_name` | `Tool.title` | 用于 UI 展示，不作为权限依据 |
| `ToolManifest.description` | `Tool.description` | 说明输入、输出、风险和人工确认要求 |
| Pydantic input model | `inputSchema` | 转 JSON Schema，禁止 `additionalProperties` 漂移 |
| Pydantic output model | `outputSchema` | 有结构化输出的工具必须提供 |
| `ToolContext` | MCP request context + server session | 由服务端注入组织、项目、actor、request_id |
| `ToolResult.artifacts` | `content/resource_link/structuredContent` | 只返回 Artifact 引用，不返回未授权对象字节 |
| `ToolError` | Protocol error 或 `isError=true` | 协议错误与业务错误分开 |
| `requires_confirmation` | BridgeAI Manifest 扩展 + Policy | MCP annotation 只表达通用行为提示，BridgeAI 风险和确认策略以内部注册表为准 |

MCP Client 传入的自然语言参数不得覆盖 `organization_id`、`project_id`、`actor_id`、`role`、`permission_scope`、`RLS context` 和 `Artifact status`。这些字段只能由 Gateway/Policy Engine 根据认证身份和项目成员关系注入。MCP 标准 annotations 只作为模型和 UI 的行为提示，不能承载 BridgeAI 的最终风险等级、审批门禁或授权结果。

## 9.7 Tool 命名、Manifest 与 Schema 规范

Tool 名称使用以下格式：

```text
bridgeai.<domain>.<action>
```

示例：

```text
bridgeai.inspection.validate_image_batch
bridgeai.inspection.detect_damage
bridgeai.asset.map_damage_to_component
bridgeai.knowledge.retrieve_standard
bridgeai.memory.build_context_manifest
bridgeai.report.generate_pdf_draft
bridgeai.workflow.create_review_items
```

命名规则：

- 仅使用 ASCII 字母、数字、下划线、连字符和点号；
- 名称稳定，语义变化必须发布新 Tool version；
- 不在名称中携带租户、项目、用户、模型供应商或临时环境；
- 不用 `admin`、`delete`、`sign` 等高风险词作为普通工具误导模型；确需暴露时必须显式风险等级和确认门禁。

Manifest 最小字段：

```json
{
  "name": "bridgeai.inspection.detect_damage",
  "title": "桥梁道路病害检测",
  "description": "对已登记影像数据集执行病害检测，返回模型运行、候选病害和证据 Artifact 引用。",
  "inputSchema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "project_id": { "type": "string", "format": "uuid" },
      "dataset_id": { "type": "string", "format": "uuid" },
      "model_profile": { "type": "string" },
      "idempotency_key": { "type": "string", "minLength": 16, "maxLength": 160 }
    },
    "required": ["project_id", "dataset_id", "idempotency_key"]
  },
  "outputSchema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "model_run_id": { "type": "string", "format": "uuid" },
      "candidate_count": { "type": "integer", "minimum": 0 },
      "review_required": { "type": "boolean" },
      "artifact_ids": {
        "type": "array",
        "items": { "type": "string", "format": "uuid" }
      }
    },
    "required": ["model_run_id", "candidate_count", "review_required", "artifact_ids"]
  },
  "annotations": {
    "readOnlyHint": false,
    "destructiveHint": false,
    "idempotentHint": true,
    "openWorldHint": false
  },
  "bridgeai_policy": {
    "risk": "medium",
    "side_effect": true,
    "human_confirmation": "required_for_high_risk"
  }
}
```

MCP annotations 只作为客户端提示，不能作为服务端授权依据。`bridgeai_policy` 是内部 Tool Registry/Manifest 扩展，不要求外部 MCP Client 理解；服务端必须重新校验输入、权限、状态、风险和幂等语义。

## 9.8 Tool 调用合同

`tools/call` 进入 BridgeAI 后统一转为内部 Tool SDK 调用：

```text
MCP tools/call
  -> request envelope validation
  -> identity and project authorization
  -> risk and confirmation policy
  -> idempotency register
  -> internal Tool execute
  -> authoritative write / outbox enqueue
  -> audit and workflow event
  -> MCP CallToolResult
```

调用合同：

| 项目 | 要求 |
|---|---|
| 请求 ID | MCP JSON-RPC `id` 只用于协议关联；业务幂等使用 `idempotency_key` |
| 超时 | Gateway、Server、Tool 各有上限；进度通知不能无限延长最大超时 |
| 取消 | 客户端取消只停止后续工作；已提交数据库事务必须靠状态机补偿 |
| 重试 | 只允许幂等重试；相同 key 不同 payload 必须拒绝 |
| 并发 | 同一项目/数据集/报告的高风险操作使用第八章锁和状态机 |
| 返回 | 结构化结果写入 `structuredContent`，同时提供简短文本摘要 |
| 副作用 | 所有写操作记录 Workflow Event、Audit Event 和 Outbox |

成功响应示例：

```json
{
  "content": [
    {
      "type": "text",
      "text": "已完成病害候选检测，生成 18 条候选记录，其中 6 条需要人工复核。"
    }
  ],
  "structuredContent": {
    "model_run_id": "2a1a18a4-07c3-41fb-9c13-984a6a61fd0f",
    "candidate_count": 18,
    "review_required": true,
    "artifact_ids": ["5b1d3bd6-bdbb-4690-9f84-bd3f3a8d0f4a"]
  },
  "isError": false
}
```

## 9.9 Resources 接入规范

MCP Resources 用于暴露可读上下文，不用于直接暴露数据库表或对象存储原始路径。BridgeAI 的 Resource URI 必须是受控 URI：

```text
bridgeai://artifact/{artifact_id}/version/{artifact_version_id}
bridgeai://project/{project_id}/asset/{asset_id}
bridgeai://damage/{damage_entity_id}/revision/{revision_id}
bridgeai://report/{report_id}/revision/{revision_id}
bridgeai://knowledge/publication/{publication_id}
bridgeai://memory/context-manifest/{context_manifest_id}
```

Resource 规则：

- `resources/list` 只列出调用者有权访问且与当前任务/项目相关的资源；
- `resources/read` 读取前再次执行组织/项目授权和状态校验；
- Artifact Resource 返回元数据、哈希、媒体类型和受控下载令牌，不返回永久 MinIO URL；
- 已撤销、删除中、墓碑、未发布或无权访问的 Resource 返回拒绝，不泄漏标题、数量或对象存在性；
- 大体积影像、点云、报告 PDF 等通过短期受控 URL 或 Artifact ID 交给应用层处理，不把大字节塞入 MCP 文本上下文。

## 9.10 Prompts 接入规范

MCP Prompts 用于暴露经过治理的模板，不用于让外部 Client 修改系统策略。第一阶段可提供：

| Prompt | 用途 | 输出边界 |
|---|---|---|
| `bridgeai.prompts.damage_review_summary` | 汇总病害复核上下文 | 生成复核说明草稿，不确认病害 |
| `bridgeai.prompts.repair_advice_draft` | 组织维修建议草案 | 需要 RAG 引用，不形成签发结论 |
| `bridgeai.prompts.report_section_draft` | 生成报告章节草稿 | 只产出草稿，进入报告复核 |
| `bridgeai.prompts.evidence_gap_question` | 生成补充材料问题 | 不扩大权限，不调用外部工具 |

Prompt 模板必须版本化，包含适用场景、输入变量、禁止事项、引用要求和输出 Schema。Prompt 结果必须经过第十章结构化输出规范和第六章 RAG 引用校验后才能进入报告草稿。

## 9.11 生命周期与能力协商

MCP 会话必须按初始化、运行、关闭三阶段管理：

1. Client 发送 `initialize`，声明 `protocolVersion`、client capabilities 和 clientInfo；
2. Server 返回选定 protocolVersion、server capabilities 和 serverInfo；
3. Client 发送 `notifications/initialized`；
4. 双方只使用已协商能力；
5. 连接关闭或超时后释放会话资源。

BridgeAI Server 第一阶段能力建议：

```json
{
  "protocolVersion": "2025-11-25",
  "capabilities": {
    "tools": { "listChanged": true },
    "resources": { "listChanged": true },
    "prompts": { "listChanged": true },
    "logging": {}
  },
  "serverInfo": {
    "name": "bridgeai.inspection",
    "title": "BridgeAI Inspection MCP Server",
    "version": "1.0.0"
  }
}
```

第一阶段 Server 不默认开启 server-initiated sampling 或 elicitation。确需由 Server 发起用户补充信息时，应先落到 Workflow 复核/澄清节点，再由 Host UI 呈现，避免 MCP Server 直接驱动模型或用户交互造成审计断点。

## 9.12 传输层选择

| 传输 | 使用场景 | 要求 |
|---|---|---|
| stdio | 本地开发、单机工具、受控桌面 Host | 凭据来自环境或系统钥匙串；子进程隔离；不得用于多人共享生产入口 |
| Streamable HTTP | 生产服务、跨主机、Web/移动端、第三方 Client | 强认证、TLS、Origin 校验、限流、审计和 Gateway 路由 |

Streamable HTTP 必须：

- 校验 `Origin`，防止 DNS rebinding；
- 使用 HTTPS 或内网 mTLS；
- 绑定受控域名和 MCP endpoint；
- 要求 `MCP-Protocol-Version` 与会话协商一致；
- 对每个请求设置 body 大小、内容类型、超时和并发限制；
- 对跨域访问使用显式 allowlist；
- 禁止在 URL query 中传递 access token、数据库凭据、Artifact token 或 Prompt。

stdio 必须：

- 使用最小环境变量；
- 不把长期密钥写入命令行参数；
- 子进程 stdout 只输出 MCP JSON-RPC，日志写 stderr 或受控日志；
- 进程退出、超时和取消都写入本地审计。

## 9.13 认证、授权与身份映射

HTTP MCP Server 使用 OAuth 体系或企业 IdP 签发的访问令牌。BridgeAI MCP Gateway 作为 protected resource，负责验证 token audience、issuer、expiry、scope、client_id 和绑定资源。

身份映射：

```text
access token
  -> subject_id / service_principal_id
  -> organization_memberships
  -> project_memberships
  -> Tool permission
  -> PostgreSQL SET LOCAL app.organization_id/app.project_id/app.subject_id
```

授权规则：

- scope 只表达客户端请求的能力上限，不替代项目成员关系；
- `project_id` 必须由 membership 校验通过；
- 服务身份和人员身份分离，自动化 Worker 使用 service principal；
- 高风险工具需要二次确认或审批记录；
- `resources/list`、`tools/list` 和 `prompts/list` 均按授权过滤；
- 权限拒绝不泄漏无权对象是否存在。

stdio 本地开发可从环境或系统钥匙串读取凭据，但仍必须生成 actor、organization、project 和 request_id；不得以“本地调用”为理由绕过 RLS 和审计。

## 9.14 组织/项目权限与 RLS 上下文

MCP 参数中的 `organization_id` 和 `project_id` 只用于表达业务目标，不能作为可信权限来源。可信上下文由 Gateway 注入：

```text
SET LOCAL app.organization_id = '<authorized organization>';
SET LOCAL app.project_id = '<authorized project>';
SET LOCAL app.subject_id = '<authenticated subject>';
SET LOCAL app.request_id = '<request id>';
SET LOCAL app.trace_id = '<trace id>';
```

Tool Repository 访问 PostgreSQL 时必须使用第八章定义的 RLS helper 和强制 RLS。MCP Server 不得：

- 使用表 owner 或 `BYPASSRLS` 角色处理业务请求；
- 让客户端传入 `app.all_projects`、`app.memory_admin` 等裸标志；
- 绕过项目成员 helper 直接查询跨项目数据；
- 从 Qdrant payload、Redis 缓存或 Tool annotation 推断权限；
- 在权限拒绝时返回对象名称、数量、路径或摘要。

## 9.15 幂等、副作用与 Outbox

MCP 的 JSON-RPC `id` 不是业务幂等键。BridgeAI 写操作必须显式提供 `idempotency_key`，并记录请求语义哈希。

| 操作类型 | 幂等规则 |
|---|---|
| 只读查询 | 可不提供业务幂等键，但必须记录 request_id |
| 检测/预处理 | 同 key 同 payload 返回同一 model_run/dataset 结果 |
| 报告草稿生成 | 同 key 同 payload 返回同一 draft revision 或 Artifact |
| 创建复核项 | 同 key 同 payload 不重复创建 |
| 删除/撤销 | 需要审批和状态机；重试不得重复传播 |

副作用工具的最小事务：

```text
BEGIN
  validate authorization and state
  register idempotency request
  write authoritative rows
  register Artifact metadata if any
  enqueue outbox_events
  append workflow_events and audit_events
COMMIT
```

MCP Server 不在数据库事务中同步调用模型、MinIO、Qdrant 或外部 HTTP。外部副作用通过 Outbox Worker 和补偿任务收敛。

## 9.16 Artifact 与 Resource URI

Tool 返回影像、标注、报告、日志或模型输出时，只返回受控 Artifact 引用：

```json
{
  "type": "resource_link",
  "uri": "bridgeai://artifact/5b1d3bd6-bdbb-4690-9f84-bd3f3a8d0f4a/version/0fd4e4f1-8b44-4b0e-a03d-3fb47ed91fd9",
  "name": "damage-detection-overlay",
  "mimeType": "image/png"
}
```

Artifact 规则：

- 返回前必须确认 `artifact_versions.status='active'` 或被当前任务授权读取；
- 验证 SHA-256、大小、media type、敏感级别和删除状态；
- 不返回长期 MinIO URL、bucket、object_key 或 version_id 给不可信 Client；
- 临时下载令牌由应用 API 签发，独立审计；
- `resource_link` 不等于业务签发，正式报告仍按第八章报告模型签发。

## 9.17 RAG 与 Memory 的 MCP 适配

RAG 和 Memory 可以作为 MCP Tools 和 Resources 暴露，但不能让 MCP Client 直接访问 Qdrant collection 或 Memory 表。

RAG Tool：

```text
bridgeai.knowledge.retrieve_standard
bridgeai.knowledge.build_evidence_pack
bridgeai.knowledge.validate_citations
```

Memory Tool：

```text
bridgeai.memory.read_project_context
bridgeai.memory.build_context_manifest
bridgeai.memory.submit_feedback
```

约束：

- 检索前先做权限过滤；
- 只返回 Evidence ID、Publication ID、Chunk 引用和摘要；
- Memory 写入必须进入 candidate/review 流程；
- Context Manifest 是可复现快照，不能由 Client 自行拼接；
- 已撤销、过期、隔离、墓碑或删除中的知识/记忆不得被 MCP Resource 复活。

## 9.18 首批 MCP Tool 清单

第一阶段 P0：

| Tool | Server | 类型 | 风险 | 说明 |
|---|---|---|---|---|
| `bridgeai.inspection.validate_image_batch` | inspection | 读写 | 中 | 校验影像批次并登记质量结果 |
| `bridgeai.inspection.preprocess_image_batch` | inspection | 读写 | 中 | 生成预处理 Artifact |
| `bridgeai.inspection.detect_damage` | inspection | 读写 | 中高 | 生成模型运行和候选病害 |
| `bridgeai.inspection.calculate_damage_statistics` | inspection | 只读/派生写 | 中 | 统计项目或资产病害指标 |
| `bridgeai.asset.map_damage_to_component` | inspection | 读写 | 高 | 将候选病害挂接构件，需复核 |
| `bridgeai.knowledge.retrieve_standard` | knowledge | 只读 | 中 | 检索规范和工程知识 |
| `bridgeai.knowledge.build_evidence_pack` | knowledge | 读写 | 中 | 固化证据包引用 |
| `bridgeai.memory.build_context_manifest` | memory | 读写 | 中 | 生成上下文清单 |
| `bridgeai.workflow.create_review_items` | workflow | 读写 | 高 | 创建人工复核项 |
| `bridgeai.report.generate_word_draft` | report | 读写 | 高 | 生成 Word 报告草稿 Artifact |
| `bridgeai.report.generate_pdf_draft` | report | 读写 | 高 | 生成 PDF 草稿 Artifact |
| `bridgeai.workflow.archive_task_result` | workflow | 读写 | 高 | 归档任务结果，需状态门禁 |

P1：

| Tool | Server | 类型 | 风险 | 说明 |
|---|---|---|---|---|
| `bridgeai.inspection.measure_crack_width` | inspection | 读写 | 中高 | 裂缝宽度量测 |
| `bridgeai.inspection.measure_damage_area` | inspection | 读写 | 中高 | 病害面积量测 |
| `bridgeai.spatial.transform_coordinates` | inspection | 读写 | 中 | 坐标转换与精度记录 |
| `bridgeai.inspection.compare_historical_damage` | inspection | 只读/派生写 | 中 | 多期病害对比 |
| `bridgeai.inspection.dataset_quality_analysis` | inspection | 读写 | 中 | 数据集质量评估 |

不暴露为 MCP Tool 的动作：

- 直接更新正式病害确认结果；
- 直接签发正式报告；
- 直接删除 Artifact 或物理对象；
- 修改 RLS、角色、权限、Prompt 系统策略；
- 直接读写 PostgreSQL、MinIO、Qdrant、Redis。

## 9.19 错误处理与安全确认

错误分两层：

| 类型 | MCP 表达 | 示例 |
|---|---|---|
| 协议错误 | JSON-RPC error | method 不存在、参数结构不符合 CallToolRequest |
| Tool 执行业务错误 | `CallToolResult.isError=true` | 权限不足、质量门禁失败、需要人工复核 |

错误码建议：

| code | 含义 | 可重试 |
|---|---|---|
| `MCP_PROTOCOL_VERSION_UNSUPPORTED` | 协议版本不支持 | 否 |
| `MCP_CAPABILITY_NOT_NEGOTIATED` | 未协商能力 | 否 |
| `TOOL_INPUT_INVALID` | 输入不合法 | 否 |
| `TOOL_PERMISSION_DENIED` | 权限不足 | 否 |
| `TOOL_CONFIRMATION_REQUIRED` | 需要人工确认 | 否，等待用户 |
| `TOOL_IDEMPOTENCY_CONFLICT` | 幂等键语义冲突 | 否 |
| `TOOL_STATE_CONFLICT` | 业务状态不允许 | 可人工处理 |
| `TOOL_TIMEOUT` | 工具超时 | 可按幂等重试 |
| `TOOL_DEPENDENCY_UNAVAILABLE` | 模型、对象或索引服务不可用 | 可重试或降级 |

高风险工具必须由 Host 显示工具名、输入摘要、影响范围、Artifact/报告/病害对象和确认按钮。模型不能代替用户确认。

## 9.20 可观测性与审计

每次 MCP 请求至少记录：

| 字段 | 来源 |
|---|---|
| `request_id` | Gateway 生成或透传 |
| `jsonrpc_id` | MCP 请求 |
| `trace_id` | 分布式追踪 |
| `session_id` | MCP 会话 |
| `client_id` | OAuth client 或 stdio client |
| `server_name/server_version` | MCP Server |
| `tool_name/tool_version` | Tool Manifest |
| `organization_id/project_id` | 授权上下文 |
| `actor_id/service_principal_id` | 认证身份 |
| `task_id/run_id/node_execution_id` | Workflow |
| `idempotency_key/request_hash` | 写操作 |
| `artifact_ids/resource_uris` | 证据引用 |
| `result_status/error_code` | 调用结果 |
| `duration_ms/token_bytes/object_bytes` | 性能与容量 |

禁止在普通日志记录 access token、数据库凭据、完整 Prompt、完整影像、未脱敏个人信息、MinIO object_key 或受限知识正文。

核心指标：

- tools/list p95、tools/call p95、错误率、超时率；
- 权限拒绝数、确认拒绝数、幂等冲突数；
- 每工具并发、队列长度、GPU/CPU/内存占用；
- Outbox pending/retry/dead-letter；
- Artifact 校验失败数；
- RAG/Memory 权限过滤耗时和拒绝存在性泄漏测试；
- MCP Server 版本漂移和能力清单变化。

## 9.21 部署、配置与密钥管理

推荐部署：

```text
BridgeAI MCP Gateway
  ├── bridgeai.inspection MCP Server
  ├── bridgeai.knowledge MCP Server
  ├── bridgeai.memory MCP Server
  ├── bridgeai.report MCP Server
  └── bridgeai.workflow MCP Server
```

配置来源：

- server name/version/protocolVersion；
- enabled tools and versions；
- OAuth issuer/audience/scope；
- allowed origins；
- rate limit and concurrency；
- Tool timeout and max payload；
- Artifact download policy；
- audit sink and trace exporter。

密钥规则：

- 不把密钥写入 MCP Prompt、Tool description、README 或日志；
- stdio 开发凭据走系统钥匙串或本地 `.env`，不得提交；
- HTTP 生产凭据走 Secret Manager；
- access token 只在 Gateway 校验，不下发到内部 Tool；
- Artifact 临时令牌短期有效、单用途、可撤销。

## 9.22 测试与验收矩阵

| 类别 | 正向 | 负向 | 证据 |
|---|---|---|---|
| 协议生命周期 | initialize/initialized 成功 | 版本不匹配、未初始化先调用 | JSON-RPC 记录 |
| 能力协商 | 协商 tools/resources/prompts 后调用 | 未协商 sampling 却请求 | 会话能力快照 |
| Tool Schema | 合法输入输出通过 | 多余字段、类型错误、缺必填 | schema validation report |
| 权限 | 同项目成员调用成功 | 跨组织/跨项目/过期成员拒绝 | RLS 与 audit |
| 幂等 | 同 key 同 payload 返回同一结果 | 同 key 不同 payload 拒绝 | idempotency rows |
| Outbox | 副作用事件入队并消费 | Worker 失败、重复消费、dead-letter | outbox evidence |
| Artifact | active version 可读 | revoked/deleting/hash mismatch 拒绝 | Artifact hash report |
| RAG/Memory | 授权证据和 Context Manifest | 撤销内容复活、权限泄漏 | evidence diff |
| 高风险确认 | 用户确认后执行 | 无确认、模型伪造确认 | confirmation audit |
| Transport | stdio/HTTP 正常 | Origin 错误、token 缺失、超时 | gateway logs |
| 可观测性 | trace/audit/metrics 完整 | 敏感正文或 token 进入日志 | log scan |

SQLite、Mock Client 和静态 JSON 校验只能作为快速反馈，不能替代真实 MCP Client/Server、OAuth、PostgreSQL RLS、Artifact、Workflow 和并发验收。

## 9.23 第一阶段实施里程碑

| 里程碑 | 目标 | 退出条件 |
|---|---|---|
| M1 协议骨架 | MCP Gateway、stdio dev server、initialize/tools/list | 协议版本、能力协商和审计记录通过 |
| M2 Tool Adapter | P0 只读与低风险 Tool 接入 | Tool Schema、错误、超时和权限过滤通过 |
| M3 副作用工具 | 检测、预处理、报告草稿、复核项 | 幂等、Workflow、Outbox、Artifact 证据闭环 |
| M4 Resources/Prompts | Artifact/Knowledge/Memory 资源与提示模板 | 无权限泄漏，引用可复现 |
| M5 生产灰度 | Streamable HTTP、OAuth、限流、监控 | 固定样本、跨租户负测、恢复与回滚演练通过 |

第一阶段只允许在一个真实桥梁或道路巡检项目中灰度 P0 工具；未通过权限、审计和人工复核门禁前，不面向外部第三方 Client 开放高风险工具。

## 9.24 架构决策记录

### ADR-009-001 MCP 作为 Tool SDK 适配层

- **背景**：第四章已经定义内部 Tool SDK，业务工具仍在快速演进。
- **决策**：MCP Server 只作为内部 Tool SDK 的标准协议适配层。
- **理由**：保持业务实现、测试、权限和审计稳定，同时获得 MCP 互操作能力。
- **代价/约束**：需要维护 Adapter 映射和双层版本；不能让 MCP Client 直接绕过内部 Tool Runtime。

### ADR-009-002 第一阶段按领域拆分 MCP Server

- **背景**：检测、知识、记忆、报告和 Workflow 的权限、资源和运行环境不同。
- **决策**：按领域拆分 Server，并由 MCP Gateway 统一认证和路由。
- **理由**：降低单 Server 权限面和资源耦合，便于灰度和限流。
- **代价/约束**：需要跨 Server trace、版本和能力清单管理。

### ADR-009-003 生产优先 Streamable HTTP，本地使用 stdio

- **背景**：stdio 适合本地子进程，生产需要跨主机、多用户和统一认证。
- **决策**：本地开发用 stdio，生产入口用 Streamable HTTP。
- **理由**：兼顾开发便利和生产安全治理。
- **代价/约束**：HTTP 必须实现 OAuth、Origin 校验、TLS、限流和审计。

### ADR-009-004 Tools 暴露业务能力，不暴露存储

- **背景**：PostgreSQL、MinIO 和 Qdrant 承载权威或派生数据，直接暴露会破坏权限边界。
- **决策**：MCP 只暴露业务 Tool 和受控 Resource URI。
- **理由**：服务端可以统一执行 RLS、状态、Artifact 和审计校验。
- **代价/约束**：需要额外 Resource 解析和临时下载 API。

### ADR-009-005 高风险工具必须人工确认

- **背景**：病害确认、报告签发、删除传播和复核项创建具有工程责任和审计要求。
- **决策**：高风险工具必须通过 Host UI 或 Workflow 人工确认。
- **理由**：模型不能承担资质责任，也不能伪造用户确认。
- **代价/约束**：自动化链路会增加等待状态和恢复逻辑。

### ADR-009-006 MCP 参数不作为可信权限上下文

- **背景**：自然语言和客户端参数容易被提示注入或恶意构造。
- **决策**：组织、项目、actor、role 和 RLS context 由 Gateway/Policy Engine 注入。
- **理由**：权限来自认证身份和成员关系，不来自模型输出。
- **代价/约束**：工具实现必须区分业务目标参数和可信执行上下文。

### ADR-009-007 副作用工具统一纳入 Workflow 与 Outbox

- **背景**：MCP tool call 可能被重试、取消或超时。
- **决策**：所有写操作必须使用幂等键、Workflow 事件和 Outbox。
- **理由**：确保重复调用不产生重复副作用，外部存储通过补偿收敛。
- **代价/约束**：工具结果可能是 accepted/pending，而不是同步完成。

### ADR-009-008 RAG 与 Memory 只通过受控工具和资源暴露

- **背景**：RAG/Memory 包含权限、版本、撤销和隐私边界。
- **决策**：不直接暴露 Qdrant collection 或 Memory 表，只暴露受控 Tool 与 Resource。
- **理由**：保留权限过滤、引用校验和上下文快照。
- **代价/约束**：调试检索结果需要专门的只读诊断工具和审计。

## 9.25 本章结论

第九章将 BridgeAI-Agent 的工具能力从内部 SDK 扩展为可互操作的 MCP 接入层。它明确了 MCP Host、Client、Gateway、Server Adapter 和内部 Tool Runtime 的边界，规定了 Tools、Resources、Prompts、传输、授权、幂等、Artifact、Workflow 和审计的统一合同。

第一阶段应先完成受控领域 Server、P0 工具、Resources/Prompts、OAuth/stdio 双传输、权限负测和固定样本回归。MCP 带来的价值是标准化互操作，而不是放松工程安全边界。所有病害确认、报告签发、删除传播和权限变更仍必须经过第八章的权威数据模型、第五章 Workflow 和人工复核链路。

第十章将进一步定义 Prompt 与结构化输出规范，约束 MCP Tools、RAG、Memory 和报告草稿在模型上下文中的呈现方式，确保工具结果、证据引用和自然语言生成之间保持清晰边界。

## 参考资料

以下官方资料于 **2026-07-30** 核验：

1. [Model Context Protocol Specification 2025-11-25: Overview](https://modelcontextprotocol.io/specification/2025-11-25/basic)
2. [Model Context Protocol Specification 2025-11-25: Lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)
3. [Model Context Protocol Specification 2025-11-25: Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
4. [Model Context Protocol Specification 2025-11-25: Authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
5. [Model Context Protocol Specification 2025-11-25: Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
6. [Model Context Protocol Specification 2025-11-25: Resources](https://modelcontextprotocol.io/specification/2025-11-25/server/resources)
7. [Model Context Protocol Specification 2025-11-25: Prompts](https://modelcontextprotocol.io/specification/2025-11-25/server/prompts)
8. [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
9. [OAuth 2.1 IETF Draft](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1)
10. [RFC 8414 OAuth 2.0 Authorization Server Metadata](https://datatracker.ietf.org/doc/html/rfc8414)
11. [RFC 7591 OAuth 2.0 Dynamic Client Registration Protocol](https://datatracker.ietf.org/doc/html/rfc7591)
12. [RFC 9728 OAuth 2.0 Protected Resource Metadata](https://datatracker.ietf.org/doc/html/rfc9728)
13. [RFC 6750 Bearer Token Usage](https://datatracker.ietf.org/doc/html/rfc6750)

## 修订记录

| 版本 | 日期 | 修订说明 |
|---|---|---|
| V1.0 | 2026-07-30 | 正式发布《第九章：MCP 工具接入规范》：定义 MCP 协议基线、Tool SDK 适配、Server 分组、Tools/Resources/Prompts、传输、OAuth、权限、RLS、幂等、Outbox、Artifact、RAG/Memory、观测、测试、里程碑和 ADR；真实 MCP Server 与 OAuth 端到端联调仍属于后续实施验收 |
