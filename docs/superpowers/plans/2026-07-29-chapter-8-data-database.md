# BridgeAI-Agent Chapter 8 Data and Database Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 编制并验证第八章《数据与数据库设计》V1.0，形成可指导桥梁与道路巡检 AI Agent 第一阶段建库、迁移、研发、联调、备份和验收的完整工程基线。

**Architecture:** 在一个 PostgreSQL 实例内按领域划分 `bridgeai_identity`、`bridgeai_core`、`bridgeai_asset`、`bridgeai_inspection`、`bridgeai_workflow`、`bridgeai_knowledge`、`bridgeai_memory`、`bridgeai_report` 和 `bridgeai_audit` Schema。PostgreSQL/PostGIS 保存权威业务与空间数据，MinIO 保存不可变大型 Artifact，Qdrant 保存可重建的 RAG/Memory 语义索引；共享数据库通过组织/项目组合约束、服务授权和强制 RLS 隔离，跨存储更新通过事务 Outbox、状态机和补偿收敛。

**Tech Stack:** Markdown、PostgreSQL 16+、PostGIS、pgcrypto、按需 pg_trgm/btree_gist、SQL、Alembic、Psycopg/SQLAlchemy 兼容数据访问、MinIO、Qdrant、LangGraph Checkpointer、BridgeAI Workflow/RAG/Memory 数据契约、官方技术资料。

## Global Constraints

- 创建 `docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md`，仅在最终任务中同步 `README.md` 的正式文档清单和后续章节。
- 不修改前七章正文；跨章字段或职责差异在第八章通过兼容映射、迁移说明和最终物理命名解决。
- 正式范围只包含桥梁与道路巡检 AI Agent，不引入智慧工地专属业务实体或 BridgeAI-Site 数据模型。
- PostgreSQL 16 及以上受支持版本，部署锁定具体小版本；必选 `postgis`、`pgcrypto`，按需 `pg_trgm`、`btree_gist`。
- Qdrant 是 RAG 与 Memory 的派生语义索引；不得引入 pgvector 双写或将向量索引当作权限、版本、删除状态的权威源。
- PostgreSQL 保存权威业务事实和元数据；MinIO 保存大体积二进制对象；Redis 只保存可丢失缓存、锁或短期协调状态。
- 所有租户业务表至少包含 `organization_id`，项目数据同时包含 `project_id`；使用强制 RLS、组合约束和服务层授权形成纵深隔离。
- 病害稳定实体与单次观测分离；已确认病害、已签发报告、已发布知识和正式 Memory 使用不可变修订和引用快照。
- 跨存储一致性采用 PostgreSQL 事务、Outbox、状态机、幂等、补偿和定期核对，不宣称不存在的分布式原子事务。
- 跨项目标准几何使用 CGCS2000（EPSG:4490）；保留原始坐标系、转换参数、工具版本和精度。
- 第一阶段恢复目标为 `RPO ≤ 15 分钟`、`RTO ≤ 4 小时`，以真实恢复演练为最终依据。
- 正文性能目标按 Mac Studio / Apple M3 Ultra / 512GB 统一内存本地基线说明，并记录数据规模、并发和缓存状态。
- 所有会变化的软件能力只引用执行当日核验的官方技术资料；行业事实不使用无法追溯的二手资料。
- 核心 DDL 必须包含字段、主键、组合外键、唯一约束、检查约束、索引和代表性 RLS；SQL 示例不得依赖 ORM 才能保证完整性。

---

### Task 1: 核验官方资料、建立跨章映射并创建正文骨架

**Files:**
- Create: `docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md`
- Read: `docs/superpowers/specs/2026-07-29-chapter-8-data-database-design.md`
- Read: `docs/md/BridgeAI-Agent-第一章-项目背景与建设目标-V1.0.md`
- Read: `docs/md/BridgeAI-Agent-第二章-总体架构设计-V1.0.md`
- Read: `docs/md/BridgeAI-Agent-第三章-Agent总体设计-V1.0.md`
- Read: `docs/md/BridgeAI-Agent-第四章-Tool-SDK设计规范-V1.0.md`
- Read: `docs/md/BridgeAI-Agent-第五章-Workflow与任务编排系统设计-V1.0.md`
- Read: `docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md`
- Read: `docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md`

**Interfaces:**
- Consumes: 已批准设计说明、第一章目录、第二至第四章系统边界、第五章 Workflow 表、第六章 RAG 概念实体和第七章 Memory 概念实体。
- Produces: 当前官方资料基线、跨章物理映射清单，以及含 8.1-8.28、参考资料和修订记录的完整 Markdown 骨架。

- [ ] **Step 1: 复核前七章数据实体和存储边界**

Run:

~~~bash
rg -n -i 'PostgreSQL|PostGIS|Qdrant|MinIO|Redis|CREATE TABLE|Schema|organization_id|project_id|task_id|thread_id|run_id|Artifact|病害|构件|报告|复核|审计' docs/md/BridgeAI-Agent-{第一章-项目背景与建设目标,第二章-总体架构设计,第三章-Agent总体设计,第四章-Tool-SDK设计规范,第五章-Workflow与任务编排系统设计,第六章-RAG行业知识库设计,第七章-Memory与项目上下文设计}-V1.0.md
~~~

Expected: 能够为组织、项目、资产、构件、检测、病害、Workflow、RAG、Memory、报告、Artifact 和审计建立来源章节与最终 Schema 映射。

- [ ] **Step 2: 核验 PostgreSQL 官方资料**

仅使用 PostgreSQL 官方文档：

- Row Security Policies: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- Constraints: https://www.postgresql.org/docs/current/ddl-constraints.html
- Index Types: https://www.postgresql.org/docs/current/indexes-types.html
- Partial Indexes: https://www.postgresql.org/docs/current/indexes-partial.html
- Declarative Partitioning: https://www.postgresql.org/docs/current/ddl-partitioning.html
- Transaction Isolation: https://www.postgresql.org/docs/current/transaction-iso.html
- Explicit Locking: https://www.postgresql.org/docs/current/explicit-locking.html
- Continuous Archiving and PITR: https://www.postgresql.org/docs/current/continuous-archiving.html
- pgcrypto: https://www.postgresql.org/docs/current/pgcrypto.html

Expected: 正文准确描述强制 RLS、约束、索引、分区、事务隔离、锁和 PITR，不把单一机制描述为完整安全或恢复体系。

- [ ] **Step 3: 核验 PostGIS、迁移和外部存储官方资料**

仅使用以下官方资料：

- PostGIS Reference: https://postgis.net/docs/reference.html
- PostGIS Spatial Reference Systems: https://postgis.net/docs/using_postgis_dbmanagement.html#spatial_ref_sys
- PostGIS Spatial Indexes: https://postgis.net/workshops/postgis-intro/indexing.html
- Alembic Documentation: https://alembic.sqlalchemy.org/en/latest/
- Qdrant Payload and Filtering: https://qdrant.tech/documentation/concepts/payload/ 和 https://qdrant.tech/documentation/concepts/filtering/
- MinIO Object Versioning: https://docs.min.io/aistor/administration/objects-and-versioning/versioning/
- LangGraph Persistence: https://docs.langchain.com/oss/python/langgraph/persistence

Expected: 正文准确说明几何/SRID/空间索引、Alembic 编排、Qdrant 派生 Payload、MinIO 对象版本和 Checkpointer 框架边界。

- [ ] **Step 4: 创建并校验正文骨架**

使用 apply_patch 创建目标文件，包含主标题、章节标题、V1.0 信息表、8.1 至 8.28、参考资料和修订记录；二级节名称与设计说明第 20 节一致。

Run:

~~~bash
rg -n '^## 8\.[0-9]+ ' docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
~~~

Expected: 8.1 至 8.28 各出现一次且顺序正确。

- [ ] **Step 5: 提交正文骨架**

Run:

~~~bash
git add -- docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
git commit -m "docs: scaffold chapter 8 database design"
~~~

Expected: 提交只包含新建的第八章正文骨架。

---

### Task 2: 编写定位、原则、技术基线、存储分工与全局规范

**Files:**
- Modify: `docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md`

**Interfaces:**
- Consumes: Task 1 的官方资料和跨章映射。
- Produces: 8.1-8.7，以及后续 DDL 统一遵守的 Schema、ID、时间、状态、命名、租户和字段规则。

- [ ] **Step 1: 编写 8.1 本章目标、8.2 数据架构定位与职责边界、8.3 设计原则**

明确第八章是物理数据收敛章；区分 PostgreSQL、MinIO、Qdrant、Redis、LangGraph Checkpoint 和 Workflow State；定义 authority before index、tenant by construction、immutable revision、source traceability、structured column first、explicit units、migration before mutation、local first 和 recovery by evidence。

- [ ] **Step 2: 编写 8.4-8.5**

写明 PostgreSQL 16+、PostGIS、pgcrypto、按需 pg_trgm/btree_gist及不采用 pgvector 双写。建立业务关系数据、空间数据、对象数据、语义索引、缓存协调、框架状态和审计数据矩阵，每类说明权威源、允许写入者、保留方式和降级路径。

- [ ] **Step 3: 编写 8.6 Schema 总体架构**

定义九个业务 Schema、依赖方向、跨域外键、只读视图和禁止跨域任意写入规则，并包含初始化骨架：

~~~sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS bridgeai_identity;
CREATE SCHEMA IF NOT EXISTS bridgeai_core;
CREATE SCHEMA IF NOT EXISTS bridgeai_asset;
CREATE SCHEMA IF NOT EXISTS bridgeai_inspection;
CREATE SCHEMA IF NOT EXISTS bridgeai_workflow;
CREATE SCHEMA IF NOT EXISTS bridgeai_knowledge;
CREATE SCHEMA IF NOT EXISTS bridgeai_memory;
CREATE SCHEMA IF NOT EXISTS bridgeai_report;
CREATE SCHEMA IF NOT EXISTS bridgeai_audit;
~~~

- [ ] **Step 4: 编写 8.7 全局规范**

固定 `snake_case`、UUID 主键、独立业务编码、`TIMESTAMPTZ`、`NUMERIC + unit_code`、`organization_id/project_id`、组合约束、观测/有效/记录时间、受约束文本状态、JSONB 对象检查、`created_by/updated_by` 和乐观版本号。解释频繁演进状态不使用 PostgreSQL ENUM。

- [ ] **Step 5: 校验并提交基础架构**

Run:

~~~bash
rg -n 'PostgreSQL 16|postgis|pgcrypto|pgvector|bridgeai_identity|bridgeai_core|bridgeai_asset|bridgeai_inspection|bridgeai_workflow|bridgeai_knowledge|bridgeai_memory|bridgeai_report|bridgeai_audit|organization_id|project_id|TIMESTAMPTZ|NUMERIC|JSONB' docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
git add -- docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
git commit -m "docs: define chapter 8 database foundations"
~~~

Expected: 8.1-8.7 完整，九个 Schema 和全局字段规则均有定义，无空节。

---

### Task 3: 编写身份项目、Artifact、资产构件和空间模型

**Files:**
- Modify: `docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md`

**Interfaces:**
- Consumes: Task 2 的租户、ID、时间、状态和字段规范。
- Produces: 8.8-8.11，以及后续业务表引用的 organizations、projects、artifacts、assets、components 和空间定位主键。

- [ ] **Step 1: 编写 8.8 身份与项目模型**

为以下表提供完整 DDL：`bridgeai_identity.organizations`、`users`、`service_principals`、`organization_memberships`，以及 `bridgeai_core.projects`、`project_memberships`。组织成员和项目成员分别表达组织级身份与项目访问；用户停用不删除历史审计主体；服务身份与人员身份分离；组合唯一键支持租户一致外键。

- [ ] **Step 2: 编写 8.9 Artifact 模型**

为 `bridgeai_core.artifacts`、`artifact_versions` 提供完整 DDL。字段覆盖 provider、bucket、object_key、version_id、SHA-256、大小、媒体类型、状态、敏感级别、保留与删除状态；定义 staged → verified → active → archived/revoked → deleting → deleted 和孤立对象回收。业务关联由后续各领域的 `dataset_artifacts`、`damage_evidence`、`report_artifacts` 等强外键关联表表达，不创建无法验证引用完整性的通用多态关联表。

- [ ] **Step 3: 编写 8.10 资产与构件模型**

为 `bridgeai_asset.assets`、`bridge_profiles`、`road_sections`、`components`、`component_aliases` 提供完整 DDL。`asset_type` 只包含 bridge/road；构件树使用 `parent_component_id`，并通过组织/项目/资产组合约束防止跨域挂接；正式编码、项目别名、停用和重编号映射分离。

- [ ] **Step 4: 编写 8.11 PostGIS 与工程定位**

定义 EPSG:4490 标准几何、原始 SRID、转换参数、精度、局部坐标、路线桩号、横向偏距、车道、构件表面和高程。提供几何合法性/SRID 检查、GiST 索引及带租户和资产过滤的空间查询。核心字段包括：

~~~sql
geom_4490 geometry(Geometry, 4490),
source_srid INTEGER,
position_accuracy_m NUMERIC(12, 4),
chainage_m NUMERIC(14, 3),
lateral_offset_m NUMERIC(12, 3),
local_x NUMERIC(14, 4),
local_y NUMERIC(14, 4),
local_z NUMERIC(14, 4)
~~~

- [ ] **Step 5: 校验并提交主数据与空间模型**

Run:

~~~bash
rg -n 'CREATE TABLE bridgeai_(identity|core|asset)\.|organizations|project_memberships|artifact_versions|bridge_profiles|road_sections|components|component_aliases|geometry\(Geometry, 4490\)|source_srid|chainage_m|USING GIST' docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
git add -- docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
git commit -m "docs: define chapter 8 asset and spatial models"
~~~

Expected: 8.8-8.11 包含核心表、外键、状态、空间约束和索引。

---

### Task 4: 编写检测采集、病害修订和多期演变模型

**Files:**
- Modify: `docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md`

**Interfaces:**
- Consumes: Task 3 的 projects、artifacts、assets、components 和空间字段。
- Produces: 8.12-8.14，以及 Workflow、报告和审计引用的检测、病害、修订和量测主键。

- [ ] **Step 1: 编写 8.12 检测与采集**

为 `bridgeai_inspection.inspection_campaigns`、`acquisition_sessions`、`acquisition_datasets`、`dataset_artifacts` 提供完整 DDL。定义计划检测、现场采集、导入批次、设备/操作者、采集时间、覆盖范围、质量状态和 Artifact 关联。

- [ ] **Step 2: 编写 8.13 病害实体、观测、修订与量测**

为 `damage_entities`、`damage_observations`、`damage_revisions`、`damage_measurements`、`damage_evidence`、`model_inference_runs` 提供完整 DDL。稳定病害与单次观测分离；修订使用 `(observation_id, revision_no)` 唯一并保存 predecessor、status、confidence、created_by、confirmed_by；量测明确 metric、value、unit、method、uncertainty 和来源。

- [ ] **Step 3: 编写不可变修订控制**

提供阻止已确认修订原地修改的触发器或受控函数。模型只能创建 draft/pending_review 修订，人工复核才能确认高风险结论；被替代版本保留引用但不作为当前默认版本。

- [ ] **Step 4: 编写 8.14 多期病害演变**

定义 new、persistent、expanded、reduced、repaired、recurred 及来源要求；提供按资产/构件/病害实体查询多期当前修订和量测趋势的 SQL。空间接近只能产生候选关联，最终合并保留人工确认或规则证据。

- [ ] **Step 5: 校验并提交检测病害模型**

Run:

~~~bash
rg -n 'inspection_campaigns|acquisition_sessions|acquisition_datasets|damage_entities|damage_observations|damage_revisions|damage_measurements|damage_evidence|model_inference_runs|revision_no|pending_review|confirmed|recurred|不可.*原地' docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
git add -- docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
git commit -m "docs: define chapter 8 inspection and damage models"
~~~

Expected: 8.12-8.14 形成采集、稳定病害、观测、修订、量测、证据、模型运行和跨期演变完整链路。

---

### Task 5: 收敛 Workflow、RAG 与 Memory 物理模型

**Files:**
- Modify: `docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md`

**Interfaces:**
- Consumes: 第五章 Workflow 表、第六章 RAG 契约、第七章 Memory 契约，以及 Task 3-4 的项目、Artifact、检测和病害主键。
- Produces: 8.15-8.17 和三个相邻领域唯一物理表名、键、状态、版本及兼容迁移规则。

- [ ] **Step 1: 编写 8.15 Workflow 兼容收敛**

为 `workflow_tasks`、`workflow_runs`、`workflow_events`、`workflow_node_executions`、`workflow_reviews` 给出最终 DDL 或完整兼容增量，补齐 organization_id、强外键、任务/运行/线程语义、状态检查、幂等、分区键、审计主体和 RLS。LangGraph Checkpointer 表继续由框架管理。

- [ ] **Step 2: 编写第五章兼容迁移矩阵**

逐表列出旧字段、最终字段、回填来源、默认值、约束启用顺序和验证查询。现有记录先补组织和项目归属，再启用 NOT NULL、组合外键与 RLS，不以重建空表代替升级。

- [ ] **Step 3: 编写 8.16 RAG 物理模型**

为 `knowledge_sources`、`documents`、`document_versions`、`chunks`、`publications`、`citations`、`index_sync_jobs` 提供核心 DDL。发布版本不可覆盖；chunk 保存原文定位和哈希；Qdrant point_id、collection 和 index_version 只作为派生同步字段；引用可恢复到版本、页码、章节或条款。

- [ ] **Step 4: 编写 8.17 Memory 与 Context 模型**

为 `memory_records`、`memory_revisions`、`memory_sources`、`memory_feedback`、`context_manifests`、`context_manifest_items`、`deletion_jobs` 提供核心 DDL。落实 candidate/active/superseded/expired/revoked/quarantined/tombstoned/deleted、单一主作用域、风险、来源、版本替代、召回清单和删除传播；Memory 与 RAG Qdrant 集合隔离。

- [ ] **Step 5: 校验并提交三域模型**

Run:

~~~bash
rg -n 'workflow_tasks|workflow_runs|workflow_events|workflow_node_executions|workflow_reviews|knowledge_sources|document_versions|chunks|publications|citations|index_sync_jobs|memory_records|memory_revisions|memory_sources|memory_feedback|context_manifests|deletion_jobs|Checkpointer|Qdrant' docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
git add -- docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
git commit -m "docs: unify chapter 8 workflow knowledge and memory schemas"
~~~

Expected: 8.15-8.17 将第五至第七章代表实体映射到唯一物理表，并保持能力边界。

---

### Task 6: 编写报告审计、事务 Outbox 与 RLS 权限模型

**Files:**
- Modify: `docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md`

**Interfaces:**
- Consumes: Task 3-5 的身份、项目、Artifact、病害修订、Workflow、知识版本和 Memory 版本。
- Produces: 8.18-8.21、报告引用快照、审计链、幂等请求、Outbox、数据库角色和代表性 RLS Policy。

- [ ] **Step 1: 编写 8.18 报告与签发模型**

为 `bridgeai_report.reports`、`report_revisions`、`report_items`、`report_citations`、`report_signatures`、`report_artifacts` 提供核心 DDL。报告修订固定引用病害修订、知识版本、Memory 版本、模型运行和 Artifact；签发记录绑定内容哈希、签发人、角色、时间和状态。已签发修订禁止原地修改。

- [ ] **Step 2: 编写 8.19 审计、安全事件与血缘**

为 `bridgeai_audit.audit_events`、`data_access_events`、`security_events`、`retention_executions`、`lineage_edges` 提供核心 DDL。审计记录 actor、service、action、object、result、before/after hash、request_id、trace_id 和服务器时间，不保存密码、令牌、完整 Prompt 或大体积正文。

- [ ] **Step 3: 编写 8.20 事务、并发、幂等与 Outbox**

为 `bridgeai_core.idempotency_requests` 和 `outbox_events` 提供完整 DDL。说明普通 READ COMMITTED、签发/发布行锁或受控 SERIALIZABLE、乐观版本、`FOR UPDATE SKIP LOCKED` Claim、请求哈希冲突、指数退避、死信、重放和核对任务；数据库事务内禁止同步调用 Qdrant、MinIO 或模型。

- [ ] **Step 4: 编写跨存储一致性时序**

覆盖 staged object → hash verify → DB register → Outbox → activate/index，以及 revoke → deny read → delete derived index/cache → delete object → tombstone 的正常和失败路径。共享 Artifact 仍被合法记录引用时不得物理删除。

- [ ] **Step 5: 编写 8.21 RLS 与数据库角色**

定义迁移所有者、业务读写、只读查询、索引 Worker、审计写入、备份恢复和紧急运维角色，并提供代表性 Policy：

~~~sql
ALTER TABLE bridgeai_core.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_core.projects FORCE ROW LEVEL SECURITY;

CREATE POLICY projects_org_isolation
ON bridgeai_core.projects
USING (organization_id = current_setting('app.organization_id', true)::uuid)
WITH CHECK (organization_id = current_setting('app.organization_id', true)::uuid);
~~~

同时说明事务级可信上下文、项目成员校验、表所有者不用于应用、`PUBLIC` 无权限和 `SECURITY DEFINER` 固定 `search_path`。

- [ ] **Step 6: 校验并提交治理与权限模型**

Run:

~~~bash
rg -n 'report_revisions|report_citations|report_signatures|audit_events|security_events|lineage_edges|idempotency_requests|outbox_events|SKIP LOCKED|SERIALIZABLE|ENABLE ROW LEVEL SECURITY|FORCE ROW LEVEL SECURITY|CREATE POLICY|SECURITY DEFINER|search_path' docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
git add -- docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
git commit -m "docs: define chapter 8 consistency and access controls"
~~~

Expected: 8.18-8.21 覆盖报告签发、审计、跨存储一致性、幂等和组织/项目隔离。

---

### Task 7: 编写索引、分区、保留、删除传播和迁移发布

**Files:**
- Modify: `docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md`

**Interfaces:**
- Consumes: Task 3-6 的核心表、查询路径、事件表、生命周期和权限策略。
- Produces: 8.22-8.24、索引矩阵、分区管理、保留/删除状态机和 expand-contract 迁移方案。

- [ ] **Step 1: 编写 8.22 索引与查询优化**

为主键/外键 B-tree、空间 GiST、顺序事件 BRIN、模糊名称 Trigram、待办/当前版本/Outbox 条件索引和有限 JSONB 表达式索引建立选择矩阵。提供项目任务列表、多期病害、当前报告版本、待复核、Outbox Claim 和空间范围查询示例。

- [ ] **Step 2: 定义查询计划验收**

每个关键查询记录参数、数据量、冷热缓存、并发与 `EXPLAIN (ANALYZE, BUFFERS)`；禁止只凭索引存在宣称性能达标。说明覆盖索引、写放大、统计信息和 autovacuum 观察项。

- [ ] **Step 3: 编写 8.23 分区、归档、保留与删除传播**

Workflow 事件、节点执行、审计事件和访问日志按月 RANGE 分区。给出父表、月分区、默认分区监控和下一分区预建示例；资产、项目、病害和报告首期不分区。定义 active/archived/revoked/deleting/deleted/tombstoned 及 PostgreSQL、Qdrant、Redis、MinIO、派生报告/Context 的删除传播顺序。

- [ ] **Step 4: 编写 8.24 迁移与发布流程**

定义 expand → backfill → verify → switch → contract，包含：新增兼容列、分批回填游标、`NOT VALID` 后续 `VALIDATE CONSTRAINT`、`CREATE INDEX CONCURRENTLY` 事务边界、读写切换、观察窗口、不可逆变换前快照、前滚方案和第五章 Workflow 逐表升级顺序。

- [ ] **Step 5: 校验并提交索引分区迁移设计**

Run:

~~~bash
rg -n 'USING GIST|USING BRIN|pg_trgm|EXPLAIN \(ANALYZE, BUFFERS\)|PARTITION BY RANGE|默认分区|expand|backfill|VALIDATE CONSTRAINT|CREATE INDEX CONCURRENTLY|contract' docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
git add -- docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
git commit -m "docs: define chapter 8 indexing partitioning and migrations"
~~~

Expected: 8.22-8.24 的索引选择有查询依据，事件表有分区运维路径，迁移含兼容、回填、验证、切换和收缩步骤。

---

### Task 8: 编写备份恢复、性能容量、可观测性和测试验收

**Files:**
- Modify: `docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md`

**Interfaces:**
- Consumes: Task 2-7 的版本、对象、分区、迁移、权限、Outbox 和查询设计。
- Produces: 8.25-8.26、可验证恢复目标、运行指标、性能基线和测试矩阵。

- [ ] **Step 1: 编写 8.25 备份与恢复**

定义 PostgreSQL 基础备份、WAL 归档、PITR、逻辑备份，MinIO 对象版本与 Artifact 清单，以及数据库/扩展/迁移/角色/对象校验和清单。固定 `RPO ≤ 15 分钟`、`RTO ≤ 4 小时`，每季度隔离环境演练。

- [ ] **Step 2: 定义恢复验收顺序**

恢复后依次校验扩展、Schema/Migration、角色与 RLS、组织隔离、项目与资产、空间查询、Artifact 哈希、病害修订、报告签发、Workflow 恢复、Outbox 和审计链。Qdrant 可重建，但重建期不能绕过权威权限和状态。

- [ ] **Step 3: 编写 8.26 性能、容量与可观测性**

固定目标：主键读取与幂等重复写入 p95 ≤ 100 ms；项目任务、病害和报告列表 p95 ≤ 300 ms；单资产多期病害与典型空间查询 p95 ≤ 500 ms。大对象传输单独统计；记录数据规模、并发、冷热缓存、PostgreSQL 配置和查询计划。

指标覆盖连接池、事务/锁、慢查询、索引命中、表/索引膨胀、autovacuum、分区、WAL、归档、Outbox、RLS 拒绝、对象不一致和恢复点。

- [ ] **Step 4: 编写测试矩阵**

覆盖 DDL、约束、RLS 正负向、空间/SRID、不可变修订、多期病害、报告快照、Workflow 兼容迁移、RAG/Memory 索引重建、Outbox 故障注入、删除传播、性能和恢复演练。明确 SQLite 不作为数据库验收环境。

- [ ] **Step 5: 校验并提交运行验收设计**

Run:

~~~bash
rg -n 'WAL|PITR|RPO.*15|RTO.*4|每季度|Artifact.*哈希|p95.*100|p95.*300|p95.*500|autovacuum|RLS.*拒绝|故障注入|SQLite' docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
git add -- docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
git commit -m "docs: define chapter 8 recovery performance and testing"
~~~

Expected: 8.25-8.26 为恢复、性能、可观测和各层测试提供确定性验收条件。

---

### Task 9: 完成实施范围、ADR、结论、参考资料与 README

**Files:**
- Modify: `docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: 8.1-8.26 的所有边界、实体、DDL、约束、迁移和验收规则。
- Produces: 8.27-8.28、十项 ADR、参考资料、修订记录、README 正式章节索引和完整 V1.0。

- [ ] **Step 1: 编写 8.27 第一阶段范围与里程碑**

按五个里程碑组织：扩展/Schema/身份/项目/RLS；Artifact/资产/构件/PostGIS；检测/病害/量测/多期关联；Workflow 迁移/RAG/Memory/报告/审计；Outbox/索引/分区/迁移/备份恢复/真实项目验收。

明确不纳入智慧工地、湖仓或数据仓库、跨地域多主、pgvector 双写、未知规模全面分区和自动报告签发。

- [ ] **Step 2: 编写十项 ADR**

每项写明背景、决策、理由、代价和约束：

- ADR-008-001：领域分 Schema、共享受控主数据；
- ADR-008-002：PostgreSQL 权威、MinIO 对象、Qdrant 派生索引；
- ADR-008-003：PostGIS 与 EPSG:4490 空间基线；
- ADR-008-004：共享数据库通过组织/项目 RLS 和组合约束隔离；
- ADR-008-005：病害稳定实体与单次观测分离；
- ADR-008-006：正式结果使用不可变修订和引用快照；
- ADR-008-007：跨存储使用事务 Outbox、状态机与补偿；
- ADR-008-008：expand-contract 兼容迁移第五章 Workflow；
- ADR-008-009：继续使用 Qdrant，不引入 pgvector 双写；
- ADR-008-010：高频事件按需分区，主业务表不提前分区。

- [ ] **Step 3: 编写 8.28、参考资料与修订记录**

总结权威事实、空间定位、多期病害、复核签发、RAG、Memory 和恢复审计，并衔接第九章 MCP 工具接入规范。参考资料只列 Task 1 已核验的官方页面并注明核验日；修订记录写明 V1.0 正式发布范围。

- [ ] **Step 4: 更新 README**

在正式架构文档列表增加第八章，将开头“已完成七章”更新为“已完成八章”，从后续章节移除第八章；保留 `temp/` 是历史参考、正式主线聚焦桥梁道路巡检的说明。

- [ ] **Step 5: 校验并提交完整章节**

Run:

~~~bash
rg -n '^## 8\.[0-9]+ ' docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
rg -n '^### ADR-008-' docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
rg -n '第八章-数据与数据库设计-V1.0.md|已完成八章' README.md
test -f docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md
git add -- docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md README.md
git commit -m "docs: complete chapter 8 data and database design"
~~~

Expected: 8.1-8.28 和 ADR-008-001 至 ADR-008-010 完整，README 指向真实第八章文件。

---

### Task 10: 执行全章结构、SQL、跨章和仓库验证

**Files:**
- Verify: `docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md`
- Verify: `README.md`
- Read: `docs/superpowers/specs/2026-07-29-chapter-8-data-database-design.md`
- Read: `docs/md/BridgeAI-Agent-第五章-Workflow与任务编排系统设计-V1.0.md`
- Read: `docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md`
- Read: `docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md`

**Interfaces:**
- Consumes: 完整第八章和批准设计说明。
- Produces: 结构、范围、SQL、契约映射和仓库状态的最终验证证据；发现问题时修复、重新验证并以独立提交记录修正。

- [ ] **Step 1: 校验 Markdown 和章节结构**

Run:

~~~bash
set -e
doc='docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md'
test "$(rg -c '^## 8\.[0-9]+ ' "$doc")" -eq 28
test "$(awk '/^```/{n++} END{print n%2}' "$doc")" -eq 0
git diff main...HEAD --check
~~~

Expected: 28 个二级节完整、代码围栏平衡、Git 差异无空白错误。

- [ ] **Step 2: 校验范围和未决内容**

Run:

~~~bash
doc='docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md'
rg -n 'TBD|TODO|FIXME|待补充|待确认|后续确定|BridgeAI-Site' "$doc" || true
~~~

Expected: 没有命中。正文若为排除范围使用“智慧工地”，必须明确其不属于正式模型且不出现专属实体 DDL。

- [ ] **Step 3: 校验前七章物理映射**

Run:

~~~bash
doc='docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md'
rg -n 'workflow_tasks|workflow_runs|workflow_events|workflow_reviews|workflow_node_executions' "$doc"
rg -n 'knowledge_sources|document_versions|chunks|publications|citations|index_sync_jobs' "$doc"
rg -n 'memory_records|memory_revisions|memory_sources|context_manifests|deletion_jobs' "$doc"
rg -n 'task_id|thread_id|run_id|Checkpoint|Workflow State|RAG|Memory|业务事实' "$doc"
~~~

Expected: 第五至第七章核心实体都有唯一物理映射，五类状态/知识能力仍有明确边界。

- [ ] **Step 4: 提取 SQL 代码块并静态检查**

Run:

~~~bash
doc='docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md'
awk '
  /^```sql$/ {in_sql=1; next}
  /^```$/ && in_sql {in_sql=0; print ""; next}
  in_sql {print}
' "$doc" > /tmp/bridgeai_chapter8.sql
test -s /tmp/bridgeai_chapter8.sql
rg -n 'CREATE (SCHEMA|TABLE|INDEX|POLICY|FUNCTION)|ALTER TABLE' /tmp/bridgeai_chapter8.sql
~~~

Expected: 提取文件非空，包含 Schema、核心表、索引、Policy、函数或触发器及 ALTER TABLE。独立查询示例与初始化 DDL 分开验证，不盲目串联执行。

- [ ] **Step 5: 在真实 PostgreSQL/PostGIS 环境验证初始化 DDL**

优先使用项目可用的本地或容器化 PostgreSQL/PostGIS 测试实例。建立专用空验证库，按正文顺序执行扩展、Schema、基础表、领域表、约束、索引、函数、触发器、RLS 和种子字典，记录实际版本后删除该专用验证库。

Run:

~~~bash
psql --version
pg_isready
~~~

Expected: 初始化 DDL 零错误。若没有可用实例，不得宣称真实数据库执行通过，必须明确记录只完成静态 SQL 检查，并在最终交付中列为环境验证缺口。

- [ ] **Step 6: 执行 RLS 与约束负向验证**

在专用验证库中至少测试：组织 A 不能访问组织 B；项目 A 构件不能挂到项目 B 资产；同一幂等键不同请求哈希被拒绝；已确认病害和已签发报告不能原地修改；错误 SRID 被拒绝；同一观测 revision_no 重复被拒绝。

Expected: 六类非法操作全部由数据库约束、RLS 或受控函数拒绝，而不只是应用代码返回错误。

- [ ] **Step 7: 校验 README 与仓库状态**

Run:

~~~bash
set -e
for path in $(rg -o 'docs/md/[^`]+\.md' README.md); do test -f "$path"; done
git status --short --branch
git log --oneline --decorate -12
git diff main...HEAD --stat
~~~

Expected: README 所有正式文档路径存在；工作区无未提交变更；第八章提交连续且只含计划内文档。

---

## Final Verification

Run:

~~~bash
set -e
doc='docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md'
test -f "$doc"
test "$(rg -c '^## 8\.[0-9]+ ' "$doc")" -eq 28
test "$(rg -c '^### ADR-008-' "$doc")" -eq 10
test "$(awk '/^```/{n++} END{print n%2}' "$doc")" -eq 0
! rg -n 'TBD|TODO|FIXME|待补充|待确认|后续确定|BridgeAI-Site' "$doc"
for schema in identity core asset inspection workflow knowledge memory report audit; do
  rg -q "bridgeai_${schema}" "$doc"
done
rg -q 'EPSG:4490' "$doc"
rg -q 'RPO.*15.*RTO.*4' "$doc"
rg -q 'FORCE ROW LEVEL SECURITY' "$doc"
rg -q 'outbox_events' "$doc"
for path in $(rg -o 'docs/md/[^`]+\.md' README.md); do test -f "$path"; done
git diff main...HEAD --check
git status --short --branch
~~~

Expected:

- 第八章文件存在，8.1-8.28 和十项 ADR 完整有序；
- Markdown 围栏平衡，正文无未决占位或 BridgeAI-Site 范围漂移；
- 九个业务 Schema、EPSG:4490、强制 RLS、Outbox 和恢复目标均落实；
- README 正式文档路径全部存在；
- 分支差异无空白错误，工作区干净；
- 真实数据库执行结果按 Task 10 Step 5 如实报告，不以静态检查替代实例验证。
