---
title: BridgeAI-Agent 第十三章 部署、监控与安全
version: V1.0
status: 正式版
updated: 2026-07-30
---

# 第十三章 部署、监控与安全

| 项目 | 内容 |
|---|---|
| 文档编号 | BridgeAI-Agent-docs-13 |
| 章节 | 第十三章 部署、监控与安全 |
| 版本 | V1.0 |
| 日期 | 2026-07-30 |
| 适用范围 | 桥梁与道路巡检 AI Agent 第一阶段 |
| 部署基线 | 本地优先、内网生产、私有化可交付、集群化可演进 |
| 观测基线 | OpenTelemetry + Metrics + Logs + Traces + Audit |
| 前置章节 | 第八章数据与数据库、第九章 MCP、第十章 Prompt、第十一章后端/前端、第十二章模型管理与评测 |

## 13.1 本章目标

本章定义 BridgeAI-Agent 的部署、监控与安全体系，使桥梁与道路巡检 AI Agent 能够在本地、内网或私有化环境中稳定运行，并具备可观测、可恢复、可审计和可防护的工程基线。

BridgeAI-Agent 不是一个只处理普通文本的 Web 应用。它处理原始影像、视频、点云、模型权重、工程规范、项目记忆、病害识别结果、人工复核记录和正式报告。部署体系必须回答：

- 服务如何启动、升级、回滚和隔离；
- 数据库、对象存储、向量库和模型运行时如何备份恢复；
- 出现任务失败、报告签发阻断、模型漂移或权限异常时如何告警；
- 谁能访问项目、Artifact、报告和 MCP Tool；
- 密钥、日志、审计和供应链如何保护；
- 系统怎样证明自己没有静默丢证据、跳复核或泄露工程数据。

本章的目标不是一次性完成大型云原生平台，而是建立第一阶段可执行、可验收、可扩展的部署与安全基线。

## 13.2 部署目标与环境分层

BridgeAI-Agent 第一阶段支持四类环境：

| 环境 | 用途 | 部署形态 | 数据要求 |
|---|---|---|---|
| `local_dev` | 开发和功能验证 | 单机进程或 Docker Compose | 脱敏样本、最小数据 |
| `single_node_pilot` | Mac Studio / 工作站试点 | Docker Compose + 本地卷 + 反向代理 | 真实项目可控导入 |
| `intranet_production` | 内网生产 | 多服务主机或小型集群 | 真实项目、强备份、审计 |
| `cluster_future` | 后续规模化 | Kubernetes / 私有云 | 多组织、多项目、自动扩缩 |

第一阶段默认以 `single_node_pilot` 和 `intranet_production` 为主要交付目标。Kubernetes 是后续扩展选项，不作为第一阶段成功的必要条件。

## 13.3 总体部署拓扑

推荐第一阶段拓扑：

```text
Browser / Intranet Client
        │ HTTPS
        ▼
Reverse Proxy / API Gateway
        │
        ├── Vue Frontend Static
        ├── FastAPI Backend
        ├── MCP Gateway
        └── Event Stream
                │
                ▼
Application Services
        ├── Workflow Runtime
        ├── Agent Runner
        ├── Tool Worker
        ├── Report Worker
        ├── RAG Service
        ├── Memory Service
        └── Model Gateway
                │
                ▼
Stateful Services
        ├── PostgreSQL + PostGIS
        ├── MinIO / S3 Compatible Storage
        ├── Qdrant
        ├── Redis
        └── Backup / Audit / Observability Storage
```

所有外部入口统一经过网关。数据库、对象存储、Qdrant、Redis 和模型运行时不直接暴露给普通用户或前端。

## 13.4 服务清单与职责

| 服务 | 职责 | 第一阶段部署建议 |
|---|---|---|
| `bridgeai-web` | Vue 前端静态资源 | 反向代理静态托管 |
| `bridgeai-api` | FastAPI 应用服务 | 常驻服务，水平扩展预留 |
| `bridgeai-workflow` | LangGraph Workflow Runtime | 与 API 分离或同机进程 |
| `bridgeai-agent-runner` | Agent 调用和结构化输出校验 | 受控并发 |
| `bridgeai-tool-worker` | YOLO、GIS、统计、文件处理 Tool | 靠近模型和对象存储 |
| `bridgeai-report-worker` | 报告草稿渲染和 PDF/Word 生成 | 独立队列 |
| `bridgeai-model-gateway` | 模型加载、路由、资源控制 | 本地 GPU/MLX 机器 |
| `bridgeai-rag` | 知识检索和证据包 | 连接 Qdrant 与 PostgreSQL |
| `bridgeai-memory` | 项目上下文和记忆服务 | 连接 PostgreSQL/Qdrant |
| `bridgeai-mcp-gateway` | MCP Server 入口和策略 | 内网访问 |
| `postgres` | 权威业务数据库 | 独立卷、PITR |
| `minio` | Artifact 字节存储 | 开启版本化和保留策略 |
| `qdrant` | RAG/Memory 派生索引 | 可重建，不作权威事实 |
| `redis` | 缓存、短锁、队列信号 | 不存权威事实 |
| `otel-collector` | 遥测采集和转发 | 内网 |

## 13.5 本地与 Docker Compose 部署

Docker Compose 适合作为第一阶段开发、试点和小规模内网部署基线。Compose 文件应表达服务、网络、卷、健康检查、配置和密钥挂载，但不得把生产密钥写入仓库。

### 13.5.1 Compose 分层

建议拆分：

```text
compose.yaml                 基础服务
compose.dev.yaml             开发覆盖
compose.observability.yaml   观测组件
compose.model.yaml           模型运行时
compose.backup.yaml          备份任务
```

运行原则：

- 默认网络分为 `public_net`、`app_net`、`data_net`；
- 只有反向代理暴露 80/443；
- PostgreSQL、MinIO、Qdrant、Redis 仅在内网网络可达；
- 每个服务配置 healthcheck；
- 数据卷使用明确命名；
- secrets/configs 通过外部文件或环境注入，不提交真实值。

### 13.5.2 Compose 服务示意

```yaml
services:
  bridgeai-api:
    image: bridgeai/api:1.0.0
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - app_net
      - data_net
    env_file:
      - ./config/api.env
    secrets:
      - db_password
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 5s
      retries: 3

secrets:
  db_password:
    file: ./secrets/db_password.txt
```

该示例只是部署形态说明，不能视为已经完成真实生产部署。

## 13.6 Kubernetes 后续演进

当任务量、组织数量、模型并发和可用性要求超过单机或小型内网部署能力时，可评估 Kubernetes。

Kubernetes 适合承载：

- 多副本 API 和前端；
- Worker 水平扩展；
- ConfigMap/Secret 管理配置；
- Deployment、Service、Ingress；
- readiness/liveness/startup probes；
- NetworkPolicy；
- HPA；
- 观测 Sidecar 或 Collector；
- 滚动发布和回滚。

不建议第一阶段直接把所有状态组件搬入 Kubernetes。PostgreSQL、MinIO、Qdrant 等状态服务可先采用专用主机或受控存储，待运维能力成熟后再迁移。

## 13.7 配置与密钥管理

配置分三类：

| 类型 | 示例 | 管理方式 |
|---|---|---|
| 普通配置 | 服务端口、日志级别、功能开关 | 配置文件、环境变量 |
| 敏感配置 | 数据库密码、JWT 密钥、对象存储密钥 | Secret Manager、Docker/K8s Secret、受控文件 |
| 运行策略 | 模型路由、灰度范围、Prompt/Schema 版本 | Registry + 审批发布 |

密钥规则：

- 不写入 Git 仓库；
- 不写入普通日志；
- 不传给前端；
- 不出现在错误响应；
- 不通过聊天、Prompt 或 Memory 保存；
- 定期轮换；
- 轮换后验证连接池和 Worker；
- 泄漏时有吊销和应急流程。

## 13.8 网络、安全边界与 TLS

网络分区建议：

| 网络 | 可访问服务 | 访问者 |
|---|---|---|
| `edge` | 反向代理、静态前端 | 用户浏览器 |
| `app` | API、Workflow、MCP Gateway | 网关、内部服务 |
| `model` | Model Gateway、视觉/LLM Runtime | Tool Worker、Agent Runner |
| `data` | PostgreSQL、MinIO、Qdrant、Redis | 后端服务 |
| `ops` | 观测、备份、管理工具 | 运维人员 |

安全要求：

- 生产入口必须启用 TLS；
- 内网服务之间建议使用 mTLS 或服务令牌；
- 数据库和对象存储不直接暴露公网；
- 管理端口只在 ops 网络开放；
- 默认拒绝跨网络访问，按服务白名单放行；
- 防火墙规则和反向代理配置纳入版本化审查；
- MCP Gateway 和 Tool Worker 不暴露给普通前端。

## 13.9 数据存储部署与恢复边界

第八章已经定义 PostgreSQL、MinIO、Qdrant、Redis 和 Checkpoint 的权威边界。第十三章从部署角度补充运行要求。

| 组件 | 部署要求 | 恢复原则 |
|---|---|---|
| PostgreSQL/PostGIS | 独立数据卷、WAL 归档、PITR、监控 | 权威事实源，恢复优先级最高 |
| MinIO | bucket versioning、对象校验、retention/legal hold | 按 Manifest 恢复精确版本 |
| Qdrant | collection/index version、payload scope | 可由 PostgreSQL/RAG/Memory 重建 |
| Redis | 可丢失缓存、短锁、队列信号 | 不作事实恢复依据 |
| LangGraph Checkpoint | 与 Workflow run 关联 | 从最后稳定节点恢复 |
| Observability Store | 日志、指标、trace、审计索引 | 保障事件定位和复盘 |

任何恢复不得以 Qdrant、Redis 或对象 latest 版本替代 PostgreSQL 权威事实和 Artifact 精确版本。

## 13.10 备份、RPO/RTO 与恢复演练

第一阶段建议目标：

| 指标 | 目标 |
|---|---|
| PostgreSQL RPO | ≤ 15 分钟 |
| PostgreSQL RTO | ≤ 4 小时 |
| Artifact 强引用恢复 | 与数据库恢复点一致 |
| Qdrant 恢复 | 从权威记录重建 |
| Workflow 恢复 | 从最后稳定节点或人工复核恢复 |
| 演练频率 | 至少每季度一次 |

### 13.10.1 备份内容

- PostgreSQL 基准备份和 WAL；
- 全局角色、权限和 RLS 目录证据；
- MinIO 对象版本 Manifest；
- Artifact 元数据与对象 SHA-256；
- Model Registry 与模型 Artifact；
- RAG/Memory 发布版本和索引构建任务；
- Workflow run、task、checkpoint 引用；
- Prompt/Schema/Tool/MCP 版本；
- 审计和 Outbox 状态。

### 13.10.2 恢复顺序

```text
隔离网络
  -> PostgreSQL PITR
  -> 角色/权限/RLS 验收
  -> Artifact 精确版本恢复
  -> Workflow/Checkpoint 对账
  -> RAG/Memory 索引重建
  -> Outbox/审计对账
  -> 读写冒烟
  -> 双人签署开放
```

恢复失败必须记录为 GAP，不能用“部分可用”冒充 RPO/RTO 达标。

## 13.11 OpenTelemetry 与可观测性架构

BridgeAI-Agent 采用 OpenTelemetry 思路统一 traces、metrics 和 logs。OpenTelemetry Collector 负责接收、处理和转发遥测数据；具体后端可以是 Prometheus、Grafana、Jaeger、Loki 或其他内网系统。

```text
Service Instrumentation
  -> OpenTelemetry SDK / Exporter
  -> OTel Collector
  -> Metrics Backend / Trace Backend / Log Backend
  -> Alerting / Dashboard / Runbook
```

### 13.11.1 统一关联字段

所有日志、指标、trace 和审计事件尽量包含：

- `trace_id`；
- `span_id`；
- `request_id`；
- `organization_id`；
- `project_id`；
- `task_id`；
- `run_id`；
- `node_name`；
- `tool_name`；
- `model_version`；
- `artifact_id`；
- `actor_id`；
- `risk_level`。

高基数字段不得无节制进入 metrics label。敏感正文、密钥、完整 Prompt、原始影像内容不得进入普通遥测。

## 13.12 日志、指标、追踪与审计

四类信号职责不同：

| 信号 | 主要用途 | 保存内容 |
|---|---|---|
| Logs | 排查错误和事件上下文 | 脱敏消息、错误码、关联 ID |
| Metrics | 趋势、SLO、告警 | 低基数维度和统计值 |
| Traces | 跨服务链路定位 | span、耗时、状态、依赖调用 |
| Audit | 合规和责任追溯 | actor、资源、动作、结果、证据 |

审计不是普通日志。报告签发、复核提交、Artifact 下载、MCP Tool 调用、权限拒绝、密钥轮换、发布变更和删除传播都必须进入审计链。

## 13.13 SLO、指标与告警

第一阶段建议 SLO：

| 对象 | 指标 | 目标 |
|---|---|---|
| API | 可用性 | ≥ 99% 内网工作时段 |
| API | P95 延迟 | ≤ 500 ms，长任务创建除外 |
| Workflow | 任务可恢复率 | ≥ 99% |
| Tool | 可重试失败恢复率 | ≥ 95% |
| Artifact | 强引用读取成功率 | ≥ 99.9% |
| PostgreSQL | RPO/RTO | ≤ 15 分钟 / ≤ 4 小时 |
| RAG | 无权限召回 | 0 |
| Report | 未复核签发成功 | 0 |
| Security | 合成越权成功 | 0 |

告警分级：

| 级别 | 示例 | 响应 |
|---|---|---|
| P0 | 越权成功、强引用丢失、签发绕过、密钥泄漏 | 立即隔离入口，启动安全事件 |
| P1 | 数据库归档中断、RPO 超限、Artifact 哈希不一致 | 立即处置，限制相关写入 |
| P2 | 延迟升高、队列积压、模型加载失败 | 排查扩容或降级 |
| P3 | 低风险趋势异常 | 排期优化 |

每条 P0/P1/P2 告警必须绑定 Runbook、owner 和升级路径。

## 13.14 Runbook 与事件响应

Runbook 至少包含：

- 影响范围；
- 安全边界；
- 负责角色；
- 只读诊断步骤；
- 停止条件；
- 可逆缓解；
- 需审批的高风险动作；
- 恢复验证；
- 复盘证据。

### 13.14.1 事件响应流程

```text
告警触发
  -> 分级
  -> 保全证据
  -> 限制影响面
  -> 只读诊断
  -> 可逆缓解
  -> 修复或回滚
  -> 验证恢复
  -> 复盘和行动项
```

禁止为了快速恢复而关闭 RLS、跳过报告复核、用 latest 对象替代精确 Artifact、手改 Outbox 为 published 或删除审计记录。

## 13.15 身份认证、授权与租户隔离

第十一章定义 API Gateway 和 RLS 透传；第十三章从安全运行角度规定验收要求。

身份与授权要求：

- 支持本地账号或企业 OIDC；
- 强制组织/项目/角色上下文；
- 高风险动作支持二次确认或双人审批；
- 服务间调用使用服务身份，不使用个人账号；
- PostgreSQL 应用角色不得拥有 `BYPASSRLS`；
- 生产环境启用并强制 RLS；
- 权限变更写入审计；
- 定期运行跨租户合成探针。

租户隔离验收：

| 验收项 | 通过条件 |
|---|---|
| 同项目读取 | 授权用户可读取 |
| 跨项目读取 | 返回 0 或拒绝 |
| 跨组织写入 | 拒绝 |
| Artifact 预览 | 无权限无法生成访问 URL |
| RAG 检索 | 无权限证据不召回 |
| Memory Context | 不返回其他项目上下文 |
| MCP Tool | 无 scope 不可调用 |

## 13.16 应用与前端安全

前端和 API 需要覆盖常见 Web 风险：

| 风险 | 控制 |
|---|---|
| XSS | 报告草稿、OCR、RAG 片段转义和 CSP |
| CSRF | Cookie 会话使用 SameSite/CSRF Token |
| SSRF | 后端不允许任意 URL 抓取 |
| 文件上传 | 类型、大小、哈希、恶意内容扫描 |
| 越权 | 后端强制鉴权，前端不作为安全边界 |
| 错误泄露 | 不返回堆栈、路径、密钥和 SQL |
| 下载滥用 | 短期签名 URL、下载审计、速率限制 |
| 富文本污染 | 报告编辑区仅允许白名单格式 |

安全测试应覆盖登录、权限、上传、下载、复核、报告签发、MCP 调用和管理后台。

## 13.17 AI、Prompt、RAG、Memory 与 MCP 安全

AI 安全控制承接第六、七、九、十、十二章。

| 风险 | 控制 |
|---|---|
| 直接提示注入 | L0-L3 Prompt 不可覆盖，拒答越权请求 |
| 间接提示注入 | 用户文件、OCR、Tool Result、RAG、Memory 均标记为数据 |
| 无证据生成 | 报告草稿强制 citation map |
| RAG 越权 | 权限过滤先于召回，发布版本固定 |
| Memory 污染 | 自动记忆先进入候选和质检 |
| MCP Tool 滥用 | Tool 白名单、scope、风险标识、人工确认 |
| 模型供应链 | 权重来源、哈希、许可证和评测报告 |
| 数据外传 | 云端 LLM 调用脱敏、审批和审计 |

高风险 Tool、报告签发、删除传播、权限变更、Outbox 重放和模型生产别名切换必须有人在回路。

## 13.18 数据保护、脱敏与保留

数据按敏感级别分层：

| 级别 | 示例 | 控制 |
|---|---|---|
| public | 公开规范标题、系统版本 | 可公开展示 |
| internal | 内部操作日志、非敏感配置 | 内网可见 |
| restricted | 项目影像、病害、报告草稿、Memory | 项目授权 |
| confidential | 签发报告、密钥、账号、敏感工程资料 | 最小权限、加密、审计 |

保留要求：

- 原始影像和签发报告按项目合同和法规保留；
- 审计记录追加写，不被普通删除流程覆盖；
- 删除请求必须先检查 legal hold、报告引用、复核和审计；
- 训练/评测样本脱敏后才能跨环境使用；
- 日志不保存敏感正文；
- 备份介质加密并限制访问。

## 13.19 供应链与发布安全

供应链安全覆盖代码、依赖、镜像、模型权重、Prompt、Schema 和部署配置。

发布前最低检查：

- Git commit 和 tag 固定；
- 依赖锁定和漏洞扫描；
- 容器镜像扫描；
- 镜像签名或摘要固定；
- 模型权重 SHA-256 和来源记录；
- Prompt/Schema 版本和评测报告；
- 数据库迁移 dry-run 和回滚/前滚方案；
- Secrets 不在镜像和仓库；
- 部署 Manifest 通过审查；
- SAST/DAST 或等效安全测试；
- SBOM 或依赖清单归档。

生产部署不得使用 `latest` 标签、未固定模型路径或未审查的外部脚本。

## 13.20 发布、灰度与回滚

发布分为：

```text
build
  -> scan
  -> test
  -> stage
  -> canary
  -> production
  -> observe
```

回滚策略：

| 组件 | 回滚方式 |
|---|---|
| 前端 | 静态资源版本切回 |
| API | 镜像版本切回或蓝绿切换 |
| Workflow | 模板版本和兼容代码切换 |
| Tool | Tool Registry 固定旧版本 |
| Model | Model Alias / Gateway Route 切回 |
| Prompt/Schema | Registry 版本切回 |
| 数据库 | 默认前滚修复，不盲目 downgrade |
| Qdrant | 索引别名切回 |

数据库结构变化必须遵守第八章 expand -> backfill -> verify -> switch -> contract。已写入新数据后不得用破坏性回滚丢弃证据。

## 13.21 容量、性能与降级

容量关注：

- PostgreSQL 表、索引、WAL、连接池；
- MinIO 对象容量、版本增长、带宽；
- Qdrant point、向量维度、segment、内存；
- Redis 内存和 key 过期；
- 模型运行时统一内存、GPU、加载时间；
- Worker 队列长度；
- 报告渲染并发；
- 前端大图预览带宽。

降级原则：

| 故障 | 允许降级 | 禁止降级 |
|---|---|---|
| RAG 不可用 | 报告草稿进入缺证据状态 | 编造规范引用 |
| Memory 不可用 | 使用业务事实和 RAG | 伪造项目历史 |
| Qdrant 不可用 | 退化为元数据/全文检索 | 绕过权限读索引 |
| 模型不可用 | 排队、备用模型、转人工 | 用未评测模型直接生产 |
| Artifact 不可读 | 阻断相关证据 | 用 latest 替代 |
| 事件流断开 | REST 恢复状态 | 认为任务失败或成功 |

## 13.22 部署验收与安全检查清单

第一阶段部署验收：

| 类别 | 验收项 |
|---|---|
| 服务 | API、前端、Workflow、Worker、Model Gateway、RAG、Memory、MCP 健康 |
| 数据 | PostgreSQL 迁移、RLS、MinIO versioning、Qdrant 索引、Redis TTL |
| 安全 | TLS、密钥、权限、越权探针、上传下载、MCP scope |
| 观测 | trace、metrics、logs、audit、dashboard、告警 |
| 恢复 | 备份、WAL、Artifact Manifest、Qdrant 重建、Workflow 恢复 |
| 发布 | 镜像、依赖、模型、Prompt/Schema、迁移、回滚方案 |
| 业务 | 上传 -> 检测 -> 复核 -> 报告 -> 签发冒烟 |

验收证据必须保存命令、时间、环境、版本、负责人、结果和失败项。不能只用截图或口头确认替代。

## 13.23 第一阶段实施里程碑

### 13.23.1 M1：本地/内网部署骨架

目标：

- 建立 Compose 服务拓扑；
- 配置反向代理、TLS、内部网络和服务健康检查；
- 启动 PostgreSQL、MinIO、Qdrant、Redis、API、前端和 Worker；
- 建立配置与密钥目录规范。

验收：

- 单机环境可运行主流程冒烟；
- 数据服务不暴露给普通用户网络；
- 真实密钥不在仓库；
- 服务健康检查可用。

### 13.23.2 M2：观测、告警与审计

目标：

- 接入 OpenTelemetry trace、metrics 和 logs；
- 建立基础 dashboard；
- 配置 P0/P1/P2 告警；
- 报告签发、Artifact 下载、MCP Tool、权限拒绝进入审计。

验收：

- 任务可通过 trace 串起 API、Workflow、Tool、Model 和 Report；
- 合成越权触发安全告警；
- 告警有 owner 和 Runbook；
- 审计链可查询。

### 13.23.3 M3：备份恢复与安全门禁

目标：

- 建立 PostgreSQL PITR 和 MinIO Artifact Manifest；
- 演练 Qdrant 重建和 Workflow 恢复；
- 建立密钥轮换和供应链扫描；
- 建立发布前安全门禁。

验收：

- 隔离恢复演练满足 RPO/RTO；
- 强引用 Artifact 哈希一致；
- RLS 正负向测试通过；
- 供应链扫描结果归档。

### 13.23.4 M4：生产灰度与应急演练

目标：

- 建立灰度发布、回滚和观察窗口；
- 建立事件响应流程；
- 演练报告签发阻断、RAG 不可用、模型不可用、Artifact 缺失和权限异常；
- 管理后台展示健康、版本、告警和审计摘要。

验收：

- 灰度失败可回滚；
- Runbook 可执行；
- 演练记录完整；
- 不出现静默降级或证据替代。

## 13.24 架构决策记录

### ADR-013-001：第一阶段采用本地/内网优先部署

**状态：** Accepted

**背景：** 桥梁道路巡检数据涉及工程影像、报告和模型资产，且项目已有本地硬件条件。

**决定：** 第一阶段优先支持本地和内网部署，Kubernetes 和云端作为后续扩展。

**后果：** 自动扩缩能力暂时有限，但数据安全、成本和落地速度更可控。

### ADR-013-002：Docker Compose 作为试点部署基线

**状态：** Accepted

**背景：** 第一阶段需要快速拉起多服务闭环，并能被工程人员在本地或内网复现。

**决定：** 使用 Docker Compose 描述试点服务拓扑，同时保留裸进程和 Kubernetes 迁移边界。

**后果：** Compose 不替代长期集群能力，但适合作为第一阶段可交付部署说明。

### ADR-013-003：OpenTelemetry 作为观测语义基线

**状态：** Accepted

**背景：** 系统包含 API、Workflow、Tool、模型、对象存储、RAG 和报告等跨服务链路。

**决定：** 采用 OpenTelemetry 的 traces、metrics、logs 思路统一关联字段和采集链路。

**后果：** 需要治理高基数字段和敏感日志，但跨服务排障能力更强。

### ADR-013-004：审计链独立于普通日志

**状态：** Accepted

**背景：** 普通日志可采样、轮转或脱敏，而报告签发、复核、权限和 Artifact 下载需要合规证据。

**决定：** 高风险业务动作进入独立审计链，不能只写普通应用日志。

**后果：** 存储和查询成本增加，但责任追溯和合规能力完整。

### ADR-013-005：恢复能力作为发布门禁

**状态：** Accepted

**背景：** 数据库、Artifact、RAG/Memory 索引和 Workflow 状态跨多个存储，备份存在不等于可恢复。

**决定：** 发布前必须有备份、Manifest、恢复演练或明确 GAP；RPO/RTO 以恢复证据为准。

**后果：** 发布流程更重，但避免灾难时才发现证据链断裂。

### ADR-013-006：前端和 MCP 不直连数据平面

**状态：** Accepted

**背景：** 直连 PostgreSQL、MinIO、Qdrant 或 Tool Runtime 会绕过权限、审计和状态机。

**决定：** 前端和外部 MCP Client 只能通过 API/MCP Gateway 访问受控能力。

**后果：** 网关压力更大，但安全边界清晰。

### ADR-013-007：供应链安全覆盖模型与 Prompt

**状态：** Accepted

**背景：** AI 系统的供应链不仅包括代码和镜像，还包括模型权重、Prompt、Schema、数据集和评测报告。

**决定：** 生产发布必须固定代码、镜像、依赖、模型、Prompt、Schema 和评测版本。

**后果：** 发布管理更复杂，但模型和提示词变化可审计、可回滚。

### ADR-013-008：禁止静默降级

**状态：** Accepted

**背景：** 巡检报告和病害复核依赖证据完整性。静默降级会制造看似成功但不可追溯的结果。

**决定：** RAG、Memory、模型、Artifact、事件流或权限服务降级时，必须显式记录、提示和审计。

**后果：** 部分任务会进入等待或人工复核，但不会伪造工程确定性。

## 参考资料

1. [OpenTelemetry 官方文档：What is OpenTelemetry?](https://opentelemetry.io/docs/what-is-opentelemetry/)
2. [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/)
3. [Docker Compose 官方文档](https://docs.docker.com/compose/)
4. [Kubernetes 官方文档：Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
5. [Kubernetes 官方文档：Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
6. [Kubernetes 官方文档：Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
7. [OWASP Application Security Verification Standard](https://owasp.org/www-project-application-security-verification-standard/)
8. [OWASP Top 10 for Large Language Model Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
9. [OWASP Software Component Verification Standard](https://owasp.org/www-project-software-component-verification-standard/)

## 修订记录

| 版本 | 日期 | 修订内容 | 修订人 |
|---|---|---|---|
| V1.0 | 2026-07-30 | 创建第十三章，定义本地/内网部署、可观测性、告警 Runbook、备份恢复、安全控制和发布门禁 | Codex |
