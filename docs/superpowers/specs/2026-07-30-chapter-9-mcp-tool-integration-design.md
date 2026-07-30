# BridgeAI-Agent Chapter 9 MCP Tool Integration Design Spec

## 1. 背景

BridgeAI-Agent 前八章已完成项目目标、总体架构、Agent、Tool SDK、Workflow、RAG、Memory 与数据/数据库设计。第九章需要在第一套正式目录中定义 MCP 工具接入规范，使内部 Tool SDK 可以面向 MCP Client、编排框架和外部调用方稳定暴露能力。

第九章不得推翻第四章 Tool SDK，也不得让 MCP 绕过第五章 Workflow、第八章 PostgreSQL/RLS/Outbox/Artifact/审计边界。MCP 是标准化适配协议，不是业务状态主控、权限主控或跨存储一致性机制。

## 2. 范围

正式范围聚焦桥梁与道路巡检 AI Agent 第一阶段，包括：

- MCP 协议基线与版本锁定；
- Host/Client/Server 与 BridgeAI 组件映射；
- 内部 Tool SDK 到 MCP Tools 的适配规则；
- Resources、Prompts、Sampling/Elicitation 的第一阶段取舍；
- stdio 与 Streamable HTTP 传输选择；
- OAuth/Token、组织/项目权限、RLS 上下文和审计；
- 工具调用幂等、副作用、Outbox、Artifact 引用；
- RAG、Memory、报告、病害检测等代表工具清单；
- 测试、验收、灰度、运维和安全门禁。

不纳入：

- 智慧工地 BridgeAI-Site 的专属 MCP Server；
- A2A Agent 协议设计；
- 以 MCP 替代内部 Tool SDK；
- 以 MCP 直接暴露数据库表、MinIO bucket、Qdrant collection 或本地文件系统；
- 自动报告签发、资质结论自动批准或无人值守高风险写操作。

## 3. 官方资料基线

核验日期：2026-07-30。

采用 MCP Specification 2025-11-25 为正文基线。该版本定义 base protocol、lifecycle、transports、authorization、tools、resources、prompts、sampling、elicitation、tasks 和 schema reference。正文还参考 JSON-RPC 2.0、JSON Schema 2020-12、OAuth 2.1 Draft、RFC 8414、RFC 7591、RFC 9728 和 RFC 6750。

若 MCP 官方规范出现新版本，生产实现必须通过协议版本评估、兼容矩阵和固定样本回归后升级；不得默认跟随“latest”。

## 4. 设计原则

1. Internal-first：内部 Tool SDK 是权威实现，MCP Server 是 Adapter。
2. Capability by negotiation：所有功能必须来自初始化阶段能力协商。
3. Authority before exposure：只暴露授权后的业务能力，不暴露权威存储本身。
4. Tenant by construction：组织/项目上下文由服务端可信身份映射，不由自然语言参数覆盖。
5. Human gate for risk：高风险写操作、报告签发和删除传播必须保留人工确认。
6. Idempotent side effects：有副作用工具必须使用幂等键、Workflow 状态和 Outbox。
7. Evidence in, evidence out：工具输入输出必须引用 Artifact、Revision、Knowledge、Memory 和审计 ID。
8. Deny by default：未知工具、未知能力、无权限 scope、缺失上下文和协议版本不匹配均拒绝。
9. Observable by request：每次 MCP 请求都关联 request_id、trace_id、task_id/run_id 和 actor。
10. Versioned contract：Tool、Prompt、Resource URI、Schema 和 Server 均显式版本化。

## 5. 章节交付要求

创建 `docs/md/BridgeAI-Agent-第九章-MCP工具接入规范-V1.0.md`，并同步 `README.md`。正文应包含 9.1 至 9.25、参考资料和修订记录；至少包含：

- MCP 架构与 BridgeAI 组件映射；
- 传输、安全、生命周期和能力协商；
- Tools/Resources/Prompts 设计；
- Tool SDK 到 MCP 的 Manifest/Schema/Result 映射；
- 权限、RLS、幂等、Outbox、Artifact、审计与观测；
- 第一阶段 MCP Server 清单和里程碑；
- ADR-009-001 至 ADR-009-008。

## 6. 验证要求

最低验证：

```bash
doc='docs/md/BridgeAI-Agent-第九章-MCP工具接入规范-V1.0.md'
test -f "$doc"
test "$(rg -c '^## 9\.[0-9]+ ' "$doc")" -eq 25
test "$(rg -c '^### ADR-009-' "$doc")" -eq 8
test "$(awk '/^```/{n++} END{print n%2}' "$doc")" -eq 0
rg -n 'MCP|tools/list|tools/call|resources/list|prompts/list|initialize|OAuth|RLS|Outbox|Artifact|Workflow' "$doc"
rg -n '第九章-MCP工具接入规范-V1.0.md|已完成九章' README.md
git diff --check
```

不得把未搭建真实 MCP Server、OAuth 授权服务或端到端客户端联调写成已验证。
