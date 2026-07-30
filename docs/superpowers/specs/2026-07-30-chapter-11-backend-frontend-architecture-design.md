# BridgeAI-Agent Chapter 11 Backend and Frontend Architecture Design Spec

## 1. 背景

BridgeAI-Agent 前十章已经完成项目目标、总体架构、Agent、Tool SDK、Workflow、RAG、Memory、数据与数据库、MCP 工具接入以及 Prompt 与结构化输出规范。第十一章需要继续按照第一章确定的正式目录，定义后端与前端架构，使前述 Agent、Workflow、Tool、RAG、Memory、数据库、MCP 和结构化输出能力能够以稳定的服务 API、任务工作台、复核界面和报告交付界面对外提供。

第十一章不得把后端写成“数据库表 CRUD 集合”，也不得把前端写成“页面列表”。后端必须体现应用服务、领域服务、编排服务、异步任务、实时通知、权限上下文、Artifact 访问和审计闭环；前端必须体现巡检任务创建、影像/病害查看、人工复核、证据引用、报告草稿、签发下载和系统运维的真实工作流。

## 2. 范围

正式范围聚焦桥梁与道路巡检 AI Agent 第一阶段，包括：

- 后端分层架构、服务边界和模块划分；
- FastAPI 应用服务、OpenAPI 契约、WebSocket/SSE 实时状态、后台任务和依赖注入边界；
- API Gateway、认证授权、组织/项目上下文、RLS 透传和服务身份；
- Workflow、Agent、Tool、RAG、Memory、Report、MCP、Artifact 和 Audit 服务集成；
- 前端 Vue Web 工作台、页面信息架构、状态管理、权限路由、实时任务进度和离线/降级；
- 影像/视频/地图/病害图层、人工复核、证据引用和报告草稿界面设计原则；
- API 契约版本、错误码、分页、文件上传下载、事件流、可观测性、安全和测试验收；
- 第一阶段后端/前端模块清单、实施里程碑和 ADR。

不纳入：

- 具体 UI 视觉稿和像素级交互设计；
- 生产级后端代码实现；
- 数据库 DDL 细节，已由第八章定义；
- 模型训练平台和评测体系完整设计；
- 移动端原生 App 完整架构；
- 云原生部署和监控平台完整设计。

## 3. 官方资料基线

核验日期：2026-07-30。

正文参考 FastAPI 官方文档关于 API、OpenAPI、依赖注入、安全依赖、WebSocket 和后台任务的能力说明；参考 Vue 官方文档关于渐进式 UI 框架、组件、响应式、组合式 API、TypeScript 和单文件组件的基础能力；同时沿用前十章已经采用的 PostgreSQL、RAG、Memory、MCP、Prompt/Schema 和审计约束。

第十一章只把这些技术作为工程承载选项，不把某个前端框架或后端框架升级为业务权威。业务权威仍来自 Workflow 状态、PostgreSQL 事实、Artifact、RAG Evidence、Memory Context、人工复核和审计事件。

## 4. 设计原则

1. API contract first：前后端通过版本化 API、事件和 Schema 协作。
2. Backend owns authority：后端负责权限、状态、事务、幂等和审计。
3. Frontend owns workspace：前端负责高效呈现任务、证据、复核和报告编辑体验。
4. Workflow visible but not bypassable：前端可看见进度和复核关口，但不能绕过状态机。
5. Artifact by reference：大文件、影像、报告和模型产物通过受控引用访问。
6. Real-time with recovery：实时进度可用 WebSocket/SSE，断线后必须可通过 REST 恢复。
7. Tenant by request context：组织/项目/角色由认证上下文注入，不由前端自由声明。
8. Local-first deployment：第一阶段优先支持本地/内网部署，再保留云端扩展点。

## 5. 章节交付要求

创建 `docs/md/BridgeAI-Agent-第十一章-后端与前端架构-V1.0.md`，并同步 `README.md`。正文应包含 11.1 至 11.24、参考资料和修订记录；至少包含：

- 后端总体架构、服务分层、模块和接口边界；
- API Gateway、认证授权、RLS 上下文、错误模型和 API 版本；
- Workflow、Agent、Tool、RAG、Memory、Report、MCP、Artifact 和 Audit 服务集成；
- 前端 Vue 工作台信息架构、路由、状态、实时进度和关键页面；
- 影像/地图/病害复核、证据引用、报告草稿和签发下载体验；
- 文件上传下载、大对象访问、事件流、权限、可观测性、安全和测试；
- 第一阶段模块清单、里程碑；
- ADR-011-001 至 ADR-011-008。

## 6. 验证要求

最低验证：

```bash
doc='docs/md/BridgeAI-Agent-第十一章-后端与前端架构-V1.0.md'
test -f "$doc"
test "$(rg -c '^## 11\.[0-9]+ ' "$doc")" -eq 24
test "$(rg -c '^### ADR-011-' "$doc")" -eq 8
test "$(awk '/^```/{n++} END{print n%2}' "$doc")" -eq 0
rg -n 'FastAPI|Vue|OpenAPI|WebSocket|API Gateway|RLS|Artifact|Workflow|人工复核|报告|MCP|审计' "$doc"
rg -n '第十一章-后端与前端架构-V1.0.md|已完成十一章' README.md
git diff --check
```

不得把未实现的后端服务、前端页面、端到端联调、视觉组件或部署流水线写成已验证。
