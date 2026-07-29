# BridgeAI-Agent 第八章《数据与数据库设计》编制设计

## 1. 编制目标

在现有前七章的架构约束下，编制第八章《数据与数据库设计》V1.0，形成可直接指导 BridgeAI-Agent 第一阶段建库、迁移、研发、联调、测试、备份和验收的完整工程基线。

本章聚焦桥梁与道路巡检 AI Agent，以 PostgreSQL 为权威业务数据库，以 PostGIS 管理空间数据，并将第五章 Workflow、第六章 RAG、第七章 Memory 的概念实体收敛为唯一物理数据模型。本章不仅说明逻辑模型，还提供足以转化为 SQL/Alembic 迁移的核心 DDL、约束、索引、RLS、分区、Outbox、生命周期和恢复方案。

本章不把智慧工地数据模型纳入正式范围。智慧工地如需建设，应基于本套文档另行编制，而不是在桥梁道路巡检主模型中混入摄像头告警、工单整改、人员定位等领域实体。

## 2. 已确认的架构决策

第八章采用以下已确认方案：

1. 采用完整工程基线，而不是仅描述概念实体或只实现最小核心表；
2. 使用 PostgreSQL 与 PostGIS，Qdrant 继续承担 RAG 和 Memory 的派生语义索引；
3. 采用共享数据库、组织级与项目级 RLS 的隔离模式；
4. 在一个 PostgreSQL 实例内按领域划分 Schema，并共享受控的组织、项目和 Artifact 主数据；
5. PostgreSQL 保存权威业务事实和元数据，MinIO 保存大体积二进制对象，Redis 只承担可丢失缓存、锁或短期协调；
6. 已确认病害、已签发报告、已发布知识和正式 Memory 不原地覆盖，使用修订、替代关系和审计事件表达变化；
7. 使用 SQL 优先、Alembic 编排的迁移策略，并通过真实 PostgreSQL/PostGIS 实例验证；
8. 第一阶段备份恢复目标为 RPO 不高于 15 分钟、RTO 不高于 4 小时，最终以恢复演练结果为准。

## 3. 既有架构约束

第八章必须与前七章保持以下一致性：

- Agent 负责理解、规划和受策略约束的决策，不得绕过 Repository 或领域服务直接写数据库。
- Workflow Runtime 以 LangGraph 为第一阶段核心编排运行时；Checkpointer 的框架托管表与业务表分离。
- `task_id`、`run_id`、`thread_id` 分别表达业务任务、实际执行和恢复线程，即使首期值相同也不得合并字段。
- PostgreSQL 业务表保存桥梁、道路、构件、病害、检测记录、人工复核、报告和审计等权威事实。
- RAG 保存规范、标准、指南、案例和项目知识的元数据、版本、权限与引用；Qdrant 索引可重建。
- Memory 保存任务摘要、项目上下文、偏好、修订和运行经验；Memory 不能替代业务事实或 RAG 证据。
- Workflow State 只保存当前执行所需字段、结果标识、错误和复核状态，不复制完整业务历史。
- MinIO 或兼容 S3 的受控对象存储保存原始影像、视频、点云、模型、报告文件和大型派生 Artifact。
- 正式工程判断、病害等级、处治建议和报告签发必须保留人工复核和来源引用。
- 系统坚持本地优先、最小权限、来源可追溯、全链路可审计、模块可替换和渐进式演进。

## 4. 技术基线

### 4.1 数据库与扩展

- PostgreSQL 16 及以上受支持版本，部署时锁定具体小版本并记录扩展兼容矩阵；
- 必选扩展：`postgis`、`pgcrypto`；
- 按需扩展：`pg_trgm`、`btree_gist`；
- 不使用 `pgvector` 作为正式语义检索底座，避免与 Qdrant 形成双重索引权威；
- UUID 作为内部主键，跨系统业务编码使用独立唯一列；
- `TIMESTAMPTZ` 作为系统时间类型；工程权威量测使用 `NUMERIC` 并绑定单位。

### 4.2 数据访问与迁移

- 应用通过领域服务和 Repository 访问数据；
- Python 侧可以使用 Psycopg 或 SQLAlchemy，但数据库约束不依赖 ORM 才能成立；
- 迁移采用 SQL 优先、Alembic 编排；
- DDL、RLS、迁移和恢复测试必须连接真实 PostgreSQL/PostGIS，SQLite 不能作为等价验证环境。

## 5. 数据域与 Schema 职责

| Schema | 核心职责 | 代表实体 |
|---|---|---|
| `bridgeai_identity` | 组织、用户、服务身份、角色和组织成员关系 | organizations、users、service_principals、organization_memberships |
| `bridgeai_core` | 项目、项目成员、Artifact、字典、幂等请求和事务 Outbox | projects、project_memberships、artifacts、code_items、idempotency_requests、outbox_events |
| `bridgeai_asset` | 桥梁、道路、路线区段、构件树、资产别名和空间定位 | assets、bridge_profiles、road_sections、components、component_aliases |
| `bridgeai_inspection` | 检测批次、采集会话、数据集、病害实体、观测修订、量测和证据 | inspection_campaigns、acquisition_sessions、damage_entities、damage_observations、damage_revisions |
| `bridgeai_workflow` | 任务、运行、事件、节点执行、Tool 执行引用和人工复核 | workflow_tasks、workflow_runs、workflow_events、workflow_node_executions、workflow_reviews |
| `bridgeai_knowledge` | RAG 知识源、文档、版本、切片、发布、引用和索引状态 | knowledge_sources、documents、document_versions、chunks、publications、citations |
| `bridgeai_memory` | 候选记忆、正式记忆、来源、修订、反馈、上下文清单和删除任务 | memory_records、memory_revisions、memory_sources、memory_feedback、context_manifests |
| `bridgeai_report` | 报告、报告修订、报告条目、签发、交付物和引用快照 | reports、report_revisions、report_items、report_citations、report_signatures |
| `bridgeai_audit` | 不可变审计事件、数据访问记录、安全事件和保留执行结果 | audit_events、data_access_events、security_events、retention_executions |
| 框架托管 Schema | LangGraph Checkpoint 等框架私有表 | 由框架迁移管理，业务迁移不得修改内部结构 |

### 5.1 跨域依赖规则

- `bridgeai_identity` 和 `bridgeai_core` 是共享基础域；
- 业务域可外键引用组织、项目和 Artifact，但不能反向让基础域依赖具体业务域；
- 业务域之间的强一致关系使用显式关联表和外键，不使用无法由数据库验证的通用多态外键；
- 异步派生关系使用 Outbox 事件，不通过数据库触发器直接访问 Qdrant、MinIO 或 Redis；
- 分析型跨域查询通过只读视图、物化视图或数据服务提供，不开放跨 Schema 任意写权限。

## 6. 存储职责边界

### 6.1 PostgreSQL

保存组织和项目归属、资产与构件、检测与病害、Workflow、RAG 元数据、Memory、报告、权限、状态、版本、引用、事务 Outbox 和审计记录。PostgreSQL 是判断记录是否有效、是否可读、是否删除和使用哪个版本的唯一权威源。

### 6.2 MinIO

保存原始影像、视频、点云、模型权重、标注文件、OCR/版面结果、派生图、报告文件、Context Artifact 和其他大体积二进制对象。数据库只保存不可变对象版本、对象键、哈希、大小、媒体类型、业务归属和生命周期状态。

### 6.3 Qdrant

RAG 与 Memory 使用独立集合、独立过滤载荷和独立生命周期。向量与 Payload 均为可重建派生数据；检索前的组织、项目、状态和敏感级别过滤由可信服务构造。

### 6.4 Redis

Redis 为可选组件，只保存缓存、分布式锁、短期队列协调和实时通知状态。Redis 故障不得导致权威业务记录、权限或任务恢复点永久丢失。

## 7. 核心实体与关系

```text
Organization
  └─ Project
       ├─ Asset（Bridge / Road）
       │    └─ Component Tree
       ├─ Inspection Campaign
       │    └─ Acquisition Session
       │         └─ Artifact / Dataset
       ├─ Damage Entity
       │    └─ Damage Observation
       │         └─ Damage Revision
       │              ├─ Measurement
       │              ├─ Evidence Link
       │              └─ Human Review
       ├─ Workflow Task → Run → Node Execution / Event / Review
       ├─ Knowledge Publication / Citation
       ├─ Memory Record / Revision / Context Manifest
       └─ Report → Revision → Item / Citation → Signature
```

### 7.1 资产与构件

- `asset` 表示稳定桥梁或道路资产；
- `bridge_profile` 与 `road_section` 保存类型专属字段；
- `component` 使用父子关系表达桥跨、墩台、梁板、横隔板、路面区段等结构；
- 资产和构件业务编码在组织或项目约束下唯一；
- 项目别名与正式编码分离，别名不能替代权威主键；
- 构件停用或重编号通过状态与映射关系表达，不破坏历史检测引用。

### 7.2 检测、病害与多期追踪

- `inspection_campaign` 表示一次计划性检测批次；
- `acquisition_session` 表示一次现场或导入采集会话；
- `damage_entity` 表示跨期追踪的同一处稳定病害；
- `damage_observation` 表示某次检测对该病害的观测；
- `damage_revision` 表示模型初判、规则校验和人工修改形成的不可变修订；
- 量测、定位、证据和模型运行引用绑定到具体修订；
- 多期状态支持新增、持续、扩展、减轻、已修复和复发，但状态变化必须有观测或人工依据。

### 7.3 Workflow、RAG、Memory 与报告

- 第五章 Workflow 表作为兼容迁移输入，在本章补齐组织字段、外键、状态约束、幂等和 RLS；
- 第六章 RAG 概念实体在 `bridgeai_knowledge` 中获得唯一物理名称，发布版本不可原地覆盖；
- 第七章 Memory 概念实体在 `bridgeai_memory` 中获得唯一物理名称，候选、正式版本、来源、反馈和删除传播分表治理；
- 报告修订固定引用病害修订、知识版本、Memory 版本、模型版本和 Artifact 版本；
- 签发后不能改变引用快照，修订报告必须创建新版本和新签发流程。

## 8. ID、时间、状态与命名规范

- 表名、列名、约束和索引统一使用小写 `snake_case`；
- 主键统一命名为 `id`，外键使用 `<entity>_id`；
- 租户业务表至少包含 `organization_id`，项目数据同时包含 `project_id`；
- 使用组合外键或等价约束保证子记录与父记录的 `organization_id`、`project_id` 一致；
- 外部业务编码与 UUID 主键分离，编码变更不能改变内部引用；
- 审计时间以数据库服务器时间为准，不信任客户端传入的创建时间；
- 区分观测时间、业务有效时间和系统记录时间；
- 软删除只用于需要恢复或保留关系的业务对象，不能把 `deleted_at` 当成所有生命周期状态的替代品；
- 状态值使用受约束的文本或字典表；需要频繁演进的业务状态不使用难以迁移的 PostgreSQL ENUM；
- 稳定业务字段使用普通列，JSONB 只承载有版本的低频扩展属性，并用检查约束确保顶层类型正确。

## 9. 空间数据设计

### 9.1 规范坐标

- 跨项目标准空间位置统一转换并保存为 CGCS2000（EPSG:4490）几何；
- 原始坐标系、原始 SRID、转换参数、转换工具版本、转换时间和精度必须保留；
- 无法可靠转换的数据标记为待校核，不能伪造标准坐标；
- 原始摄影测量成果、高精度点云和网格文件保存在对象存储。

### 9.2 工程定位

- 道路病害支持路线、桩号、横向偏距、车道和行驶方向；
- 桥梁病害支持资产、构件、构件表面、局部坐标和高程；
- 全局几何与工程局部定位可以同时存在，并记录定位方法和精度；
- 几何合法性、范围和几何类型使用 PostGIS 函数及检查约束校验；
- 空间索引采用 GiST，查询必须同时带组织、项目或资产过滤，避免无边界全库空间扫描。

## 10. Artifact 与对象一致性

Artifact 使用不可变版本模型。上传流程为：

1. 客户端或受控服务上传临时对象；
2. 服务端计算或复核哈希、大小和媒体类型；
3. 数据库事务登记 Artifact 及业务关联，写入 Outbox；
4. Worker 将对象状态切换为可用，并触发后续解析或索引；
5. 登记失败或超时的孤立临时对象由回收任务处理。

业务读取只接受数据库状态为可用且哈希校验通过的对象版本。对象删除必须先停止业务读取，再处理派生物和底层对象；共享对象仍被其他合法记录引用时不得物理删除。

## 11. 事务、并发与幂等

- 同一 PostgreSQL 实例内的业务事实、修订、状态事件、审计摘要和 Outbox 在同一事务提交；
- 普通事务使用 `READ COMMITTED`；
- 签发、发布、版本替代和序号分配使用行锁、乐观版本号或受控 `SERIALIZABLE` 事务；
- 所有外部可重试写接口使用 `(organization_id, caller_id, idempotency_key)` 唯一约束；
- 幂等记录保存请求哈希、响应摘要、状态和有效期，同一键不同请求体必须拒绝；
- Worker 使用 `FOR UPDATE SKIP LOCKED` 或等价模式领取任务；
- 事务中禁止直接调用模型、Qdrant、MinIO 长耗时操作或外部网络服务；
- 跨存储一致性采用状态机、Outbox、补偿和定期核对，不虚构分布式原子事务。

## 12. RLS、角色与授权

### 12.1 会话授权上下文

应用在事务开始后通过可信网关或服务身份设置当前 `organization_id`、`actor_id` 和授权项目上下文。上述值不得来自 Agent 自然语言、Tool 输出或未校验请求体。

### 12.2 RLS 基线

- 所有租户业务表启用并强制执行 RLS；
- 表所有者和迁移角色不作为日常应用账号；
- RLS Policy 至少限制组织，项目数据继续校验项目成员关系；
- 服务层仍执行动作级授权和字段级脱敏，RLS 不作为唯一授权机制；
- 后台 Worker 使用最小权限服务角色，并限制可处理的事件类型；
- 对 RLS 的允许和拒绝路径均建立自动化测试。

### 12.3 数据库角色

至少区分迁移所有者、业务读写、只读查询、索引 Worker、审计写入、备份恢复和紧急运维角色。`PUBLIC` 默认无业务 Schema 权限；`SECURITY DEFINER` 函数必须固定 `search_path`、校验调用者并保持最小接口。

## 13. 审计、修订与删除

- 已确认病害、已签发报告、已发布知识和正式 Memory 采用追加式修订；
- 审计事件记录主体、动作、对象、结果、前后版本哈希、请求标识、Trace 标识和服务器时间；
- 审计正文不得包含密码、令牌、完整 Prompt、无必要业务原文或大体积数据；
- 高风险数据变更通过数据库权限、领域状态机和不可变保护共同约束；
- 删除请求通过正式任务记录 PostgreSQL、Qdrant、Redis、MinIO 和派生快照的传播状态；
- 删除开始后立即阻断读取，清理完成前不能因索引残留继续召回；
- 为满足审计可保留不含原文和个人信息的最小墓碑。

## 14. 索引与查询设计

- 主键、业务唯一键和外键连接使用 B-tree；
- 空间位置使用 GiST；
- 大型时间顺序事件表按场景使用 BRIN；
- 中文名称模糊查询按需使用 `pg_trgm` 的 GIN/GiST 索引；
- JSONB 仅为明确且稳定的查询路径建立表达式或 GIN 索引；
- 待办、有效版本和未处理 Outbox 使用条件索引；
- 高频列表可使用覆盖索引，但必须以真实查询计划和写放大成本验证；
- 每个关键查询在验收数据规模下保存 `EXPLAIN (ANALYZE, BUFFERS)` 基线。

## 15. 分区、保留与归档

- Workflow 事件、节点执行、审计事件和高频访问日志按月范围分区；
- 第一阶段低数据量资产、项目、病害和报告表不提前分区；
- 分区必须预创建并监控默认分区，避免新月份写入失败；
- 分区删除、归档和备份遵循业务保留、合同和审计要求；
- 项目归档后默认停止活跃检索和写入，但仍可按授权读取历史；
- 保留策略执行记录、删除数量、异常和批准人写入审计域。

## 16. 迁移与兼容策略

迁移使用 expand → backfill → verify → switch → contract：

1. 先新增兼容结构，不立即删除旧列；
2. 分批回填，并记录游标、错误和校验和；
3. 比对行数、约束、关键聚合和抽样业务结果；
4. 切换应用读写路径并观察；
5. 在确认无旧版本使用后移除旧结构。

每个迁移必须说明升级步骤、锁风险、数据校验、失败处理和回滚或前滚策略。不可逆变换必须先生成可恢复快照。大表索引使用在线创建策略，长事务、全表重写和超限锁等待必须中止并告警。

第五章已有 `bridgeai_workflow` 表作为兼容迁移输入，不能以“重建空表”代替真实数据升级。第六、七章尚未物理落地的概念实体按本章最终命名首次创建。

## 17. 备份、恢复与灾难演练

- PostgreSQL 使用基础备份、WAL 归档和定期逻辑备份组合；
- MinIO 使用对象版本和与数据库恢复点对应的 Artifact 清单；
- 备份包记录数据库版本、扩展版本、迁移版本、角色权限、对象清单和校验和；
- 第一阶段目标为 RPO 不高于 15 分钟、RTO 不高于 4 小时；
- 每季度至少执行一次隔离环境恢复演练；
- 演练必须验证 PostGIS、RLS、组织隔离、对象哈希、签发报告、历史病害链、Outbox 和审计链；
- 恢复后的派生索引可以重建，但重建期间不得绕过权威状态和权限。

## 18. 性能与容量基线

性能测试在 Mac Studio / Apple M3 Ultra / 512GB 统一内存的本地基线环境上进行，并记录 PostgreSQL 配置、数据规模、并发、缓存冷热状态和对象存储影响。

第一阶段目标：

| 场景 | 目标 |
|---|---|
| 主键读取与幂等重复写入 | p95 不高于 100 ms |
| 项目任务、病害和报告常用列表 | p95 不高于 300 ms |
| 单资产多期病害对比 | p95 不高于 500 ms |
| 典型空间范围查询 | p95 不高于 500 ms |
| Outbox | 正常状态积压可控，失败事件可定向重放 |

性能指标不包含大对象实际传输时间。若数据规模、并发或硬件条件改变，必须重新建立基线，不能把单机测试结果宣称为所有部署环境的保证。

## 19. 测试与验收

### 19.1 必测场景

- 空库完成扩展、Schema、角色、表、RLS、索引和种子字典初始化；
- 非法状态、错误单位、无效时间区间和重复编码被数据库拒绝；
- 跨组织和跨项目外键、读取及写入被阻断；
- EPSG:4490 转换、道路桩号、构件定位、范围和距离查询正确；
- 病害从模型初判到人工确认、多期演变、修订替代和报告引用可复现；
- 数据库提交成功但 Qdrant 或 MinIO 后续处理失败时可以重放或补偿；
- 从第五章 Workflow 旧结构升级后任务、运行、事件和复核记录不丢失；
- 恢复数据库与对象存储后 Artifact 哈希、RLS、签发快照和审计链有效。

### 19.2 文档验收

1. 标题、编号、术语、信息表、参考资料和修订记录与前七章一致；
2. 所有第五至第七章概念实体均有明确物理映射或边界说明；
3. 核心 DDL 字段、约束、索引和策略内部一致；
4. 所有 SQL 代码围栏闭合，并通过基本语法或真实实例验证；
5. 所有时效性技术事实使用当前官方资料核验；
6. 不包含未决占位文字，也不包含智慧工地正式业务模型；
7. README 正式架构文档清单增加第八章；
8. Markdown 标题层级、表格、代码围栏和内部引用通过一致性检查。

## 20. 第八章正文结构

正文采用以下章节结构：

- 8.1 本章目标
- 8.2 数据架构定位与职责边界
- 8.3 设计原则
- 8.4 技术基线与扩展
- 8.5 数据分类与存储分工
- 8.6 Schema 总体架构
- 8.7 全局命名、ID、时间与状态规范
- 8.8 组织、用户、角色与项目模型
- 8.9 Artifact 与对象存储元数据模型
- 8.10 桥梁、道路、路线与构件模型
- 8.11 PostGIS 空间与工程定位设计
- 8.12 检测批次、采集会话与数据集模型
- 8.13 病害实体、观测、修订与量测模型
- 8.14 多期病害关联与历史演变
- 8.15 Workflow 数据模型兼容收敛
- 8.16 RAG 知识库数据模型
- 8.17 Memory 与 Context 数据模型
- 8.18 报告、引用、复核与签发模型
- 8.19 审计、安全事件与数据血缘
- 8.20 事务、并发、幂等与 Outbox
- 8.21 RLS、数据库角色与权限隔离
- 8.22 索引、查询与空间检索优化
- 8.23 分区、归档、保留与删除传播
- 8.24 数据迁移、兼容与发布流程
- 8.25 备份、恢复与灾难演练
- 8.26 性能、容量、可观测性与测试
- 8.27 第一阶段实施范围与架构决策
- 8.28 本章结论
- 参考资料
- 修订记录

## 21. 第一阶段实施范围

第一阶段必须交付：

- 组织、项目、成员和 RLS 基础；
- 桥梁、道路、构件、检测、病害、量测和证据链；
- 统一 Artifact 注册与 MinIO 对象关联；
- Workflow 兼容迁移；
- RAG、Memory 和报告的权威元数据模型；
- Outbox、幂等、审计和删除传播；
- PostGIS 空间与工程定位；
- 索引、必要分区、迁移、备份恢复和验收基线。

第一阶段不纳入：

- 智慧工地专属业务实体；
- 数据仓库、湖仓或实时流处理平台；
- 跨地域多主数据库；
- 使用数据库向量扩展替代 Qdrant；
- 为未知规模提前对所有业务表分区；
- 自动签发工程报告或绕过人工复核。

## 22. 架构决策记录

正文至少固化以下 ADR：

- ADR-008-001：按领域划分 PostgreSQL Schema，共享受控主数据；
- ADR-008-002：PostgreSQL 为权威源，MinIO 保存对象，Qdrant 保存可重建语义索引；
- ADR-008-003：PostGIS 与 EPSG:4490 作为跨项目标准空间基线；
- ADR-008-004：共享数据库通过组织/项目 RLS 与组合约束隔离；
- ADR-008-005：病害稳定实体与单次观测分离；
- ADR-008-006：正式结果采用不可变修订和引用快照；
- ADR-008-007：跨存储一致性采用事务 Outbox、状态机和补偿；
- ADR-008-008：迁移采用 expand-contract 并兼容第五章现有 Workflow 表；
- ADR-008-009：语义检索继续使用 Qdrant，不引入 pgvector 双写；
- ADR-008-010：高频事件表按需分区，业务主表不提前分区。

## 23. 实施顺序

1. 核验当前 PostgreSQL、PostGIS、LangGraph Checkpointer、Qdrant 和 MinIO 官方资料；
2. 建立前七章实体、字段和职责映射矩阵；
3. 编制数据域、全局规范、核心实体和空间模型；
4. 编制 Workflow、RAG、Memory、报告和审计物理模型；
5. 编制事务、RLS、索引、分区、迁移和恢复方案；
6. 补齐核心 DDL、策略 SQL、查询示例、测试矩阵和 ADR；
7. 校验 SQL、Markdown、术语、引用、章节编号和 README；
8. 修订为 V1.0 正式可交付稿。
