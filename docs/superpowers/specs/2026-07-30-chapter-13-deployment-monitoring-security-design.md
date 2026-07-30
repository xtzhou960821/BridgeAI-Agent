# BridgeAI-Agent Chapter 13 Deployment, Monitoring and Security Design Spec

## 1. 背景

BridgeAI-Agent 前十二章已经完成项目目标、总体架构、Agent、Tool SDK、Workflow、RAG、Memory、数据与数据库、MCP、Prompt/结构化输出、后端/前端架构以及模型管理与评测体系。第十三章需要继续按照第一章确定的正式目录，定义部署、监控与安全体系，使桥梁与道路巡检 AI Agent 能够在本地、内网或私有化环境中稳定运行，并具备可观测、可恢复、可审计和可防护的工程基线。

第十三章不得把部署写成“一条启动命令”，也不得把安全写成“加 HTTPS 和登录”。BridgeAI-Agent 处理原始影像、模型权重、工程报告、RAG/Memory 证据、人工复核和签发记录；部署体系必须覆盖服务拓扑、密钥、网络、存储、备份恢复、日志指标追踪、告警 Runbook、权限隔离、供应链安全和 AI 特有安全风险。

## 2. 范围

正式范围聚焦桥梁与道路巡检 AI Agent 第一阶段，包括：

- 本地开发、单机试点、内网生产和后续集群化部署拓扑；
- Docker Compose、进程守护、反向代理、TLS、服务发现和配置管理；
- PostgreSQL/PostGIS、MinIO、Qdrant、Redis、Model Gateway、Worker 和前后端服务部署边界；
- OpenTelemetry、日志、指标、追踪、告警、SLO、Runbook 和事件响应；
- 备份、恢复、RPO/RTO、对象版本、索引重建、Workflow/Checkpoint 恢复和演练；
- 身份认证、授权、RLS、密钥管理、网络分区、审计、数据脱敏和保留策略；
- 应用安全、AI 安全、MCP/Tool 安全、供应链安全和发布门禁；
- 第一阶段部署验收、监控告警、安全检查清单、里程碑和 ADR。

不纳入：

- 云厂商专属部署方案；
- 大规模 Kubernetes 生产集群完整运维手册；
- 代码级安全修复实现；
- 第十四章实施路线图和版本规划；
- 智慧工地专属部署拓扑。

## 3. 官方资料基线

核验日期：2026-07-30。

正文参考 OpenTelemetry 官方文档关于 traces、metrics、logs、Collector 和 vendor-neutral observability 的说明；参考 Docker Compose 官方文档关于多容器应用定义、服务、健康检查、secrets/configs 的说明；参考 Kubernetes 官方文档关于 Deployment、Service、ConfigMap、Secret、Probe、NetworkPolicy 和 HPA 的说明；参考 OWASP ASVS、OWASP Top 10 for LLM Applications 和 OWASP SCVS 作为应用、AI 与供应链安全参考。

这些资料只作为能力和术语基线。BridgeAI-Agent 第一阶段以本地/内网可控部署为优先，不把 Kubernetes、云托管或任何观测后端作为强依赖。

## 4. 设计原则

1. Local-first, private-ready：第一阶段先保证本地和内网部署可运行，再预留集群化扩展。
2. Secure by default：默认关闭高风险端口、默认最小权限、默认不外传敏感工程数据。
3. Observable by design：每个请求、任务、模型调用、Tool 调用、Artifact 和报告动作都有 trace、metric、log 或 audit 证据。
4. Recovery as product feature：备份恢复、RPO/RTO、恢复演练和 Runbook 是产品能力，不是运维附属品。
5. Secrets never in repo：密钥、令牌、证书和对象存储凭据不得进入仓库、普通日志或前端。
6. Immutable evidence：已签发报告、审计、Artifact 版本和关键证据不可原地覆盖。
7. Defense in depth：网关、应用、数据库 RLS、对象存储、MCP/Tool、模型和前端共同防护。
8. No silent degradation：任何降级都必须可见、可审计、可恢复，不能伪装成功。

## 5. 章节交付要求

创建 `docs/md/BridgeAI-Agent-第十三章-部署监控与安全-V1.0.md`，并同步 `README.md`。正文应包含 13.1 至 13.24、参考资料和修订记录；至少包含：

- 部署目标、拓扑、环境分层和服务清单；
- Docker Compose/本地内网部署、Kubernetes 后续扩展和配置密钥管理；
- 数据库、对象存储、向量库、模型网关、Worker、前后端和 MCP 的部署边界；
- OpenTelemetry、日志、指标、追踪、SLO、告警、Runbook 和事件响应；
- 备份恢复、RPO/RTO、演练和灾难恢复；
- 身份权限、网络安全、数据安全、AI 安全、供应链安全和发布门禁；
- 第一阶段部署/监控/安全清单和实施里程碑；
- ADR-013-001 至 ADR-013-008。

## 6. 验证要求

最低验证：

```bash
doc='docs/md/BridgeAI-Agent-第十三章-部署监控与安全-V1.0.md'
test -f "$doc"
test "$(rg -c '^## 13\.[0-9]+ ' "$doc")" -eq 24
test "$(rg -c '^### ADR-013-' "$doc")" -eq 8
test "$(awk '/^```/{n++} END{print n%2}' "$doc")" -eq 0
rg -n 'Docker Compose|Kubernetes|OpenTelemetry|TLS|RLS|MinIO|Qdrant|PostgreSQL|RPO|RTO|Runbook|密钥|审计|供应链|提示注入|告警' "$doc"
rg -n '第十三章-部署监控与安全-V1.0.md|已完成十三章' README.md
git diff --check
```

不得把未搭建的真实部署环境、监控看板、告警系统、备份恢复演练或安全扫描写成已验证。
