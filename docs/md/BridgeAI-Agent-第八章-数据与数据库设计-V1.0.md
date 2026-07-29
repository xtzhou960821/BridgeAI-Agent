# BridgeAI-Agent Architecture White Paper

# 第八章 数据与数据库设计

| 项目 | 内容 |
|---|---|
| 文档名称 | BridgeAI-Agent Architecture White Paper |
| 章节 | 第八章 数据与数据库设计 |
| 版本 | V1.0 |
| 状态 | 正式版 |
| 适用范围 | 桥梁与道路巡检 AI Agent |
| 默认开发环境 | Mac Studio / Apple M3 Ultra / 512GB 统一内存 |
| 权威业务数据库 | PostgreSQL（本地部署） |
| 空间数据扩展 | PostGIS |
| 语义检索 | Qdrant 派生 RAG 与 Memory 索引 |
| 对象存储 | MinIO 或兼容 S3 的受控对象存储 |
| 编制日期 | 2026-07-29 |

---

## 8.1 本章目标

本章是 BridgeAI-Agent 的物理数据收敛章，适用范围严格限定为**桥梁与道路巡检**。本章把前述业务、算法、工作流与报告要求收敛为可迁移、可约束、可恢复的数据模型与存储边界；它不是通用智慧工地或视频监控平台的数据设计。

本章的目标如下：

- 建立组织、项目、桥梁、道路、路线、构件、巡检、病害、证据、知识、记忆、报告与审计的权威关系数据模型；
- 将工程空间定位、对象证据、语义检索、短期协调、工作流持久化和审计证据置于各自合适的存储，并明确谁是权威源；
- 以迁移、约束、行级隔离、版本和审计保证多租户场景下的数据完整性、可追溯性与可恢复性；
- 为后续 DDL、索引、RLS、归档、备份和发布流程提供统一、可执行的基线，避免由应用代码隐式约定数据规则。

## 8.2 数据架构定位与职责边界

数据架构遵循“关系事实先落库、派生索引后构建”的分工。业务决定、审批结论、对象元数据和可追溯引用必须首先写入 PostgreSQL；任何缓存、向量或工作流运行时状态均不得替代该权威记录。跨存储传递时使用稳定 UUID、组织和项目边界、版本号及来源引用，不能仅以对象路径、向量点 ID 或会话键建立事实关联。

| 存储/状态组件 | 定位与权威范围 | 不承担的职责 |
|---|---|---|
| PostgreSQL + PostGIS | 业务关系事实、空间要素、对象元数据、版本、权限边界、事务、审计索引与引用关系的唯一权威源 | 不存放大体积原始媒体，也不作为向量近邻检索引擎 |
| MinIO（或兼容 S3 的受控对象存储） | 原始影像、视频、点云、模型产物、报告文件及其不可变版本的对象字节权威载体；对象身份、校验和、保留策略与引用关系由 PostgreSQL 管理 | 不承载业务关系、授权判断或可查询的巡检事实 |
| Qdrant | 由 PostgreSQL 权威文档、记忆或工件修订派生的 RAG 与 Memory 语义索引；检索结果必须回查权威记录、版本与租户边界 | 不作为业务事实、审批结论、审计或对象元数据的写入源；不采用 pgvector 双写 |
| Redis | 可丢失的缓存、分布式协调、限流、幂等短锁和短期任务信号 | 不保存唯一业务事实、长期工作流状态或不可重建审计证据 |
| LangGraph Checkpoint | 单个图执行的可恢复检查点和线程级持久化快照；其生命周期、线程与业务运行引用由 PostgreSQL 登记 | 不作为任务、审批、报告或领域状态的权威数据库 |
| Workflow State | 编排过程中的领域可见状态、人工复核、任务阶段和结果摘要；需以 `bridgeai_workflow` 的事务记录为权威 | 不把运行时内存、Redis 键或 Checkpoint 本身视为已提交的业务状态 |

当 Redis、Qdrant 或 LangGraph Checkpoint 不可用时，系统可降级为基于 PostgreSQL 的事务事实、对象元数据和已登记工作流运行进行查询、重建或人工续办；不得为维持可用性而绕过租户约束、审计或版本记录。

## 8.3 设计原则

1. **Authority before index（权威先于索引）**：先提交 PostgreSQL 的权威事实和版本，再异步生成 Qdrant 向量、全文索引、缓存或物化读模型；派生数据可重建，权威事实不可由派生数据反推写回。
2. **Tenant by construction（租户内建）**：租户和项目不是查询时才附加的筛选条件。边界字段按组织根、项目根、组织级和项目级表的适用矩阵在建模时确定；适用的字段必须通过组合外键、唯一约束、RLS 和索引共同约束，不能由应用代码猜测范围。
3. **Immutable revision（不可变修订）**：采集、识别、人工复核、知识切分和报告签发均保留不可变修订；修订以新记录表达，已发布证据不做覆盖式修改。
4. **Source traceability（来源可追溯）**：每项可用结论均能回溯到原始工件、采集会话、算法/提示词版本、操作人、时间和修订；外部对象以校验和与版本标识，不以可变 URL 作为唯一证据。
5. **Structured column first（结构化列优先）**：参与关联、筛选、权限、排序、统计、约束或索引的字段必须建为显式列；`JSONB` 仅承载受约束的扩展属性，不替代核心领域列。
6. **Explicit units（单位显式）**：长度、面积、体积、质量、荷载、置信度以外的工程量和阈值均以 `NUMERIC` 与 `unit_code` 成对保存，并在字段语义和检查约束中明确量纲。
7. **Migration before mutation（先迁移后变更）**：所有结构、索引、约束和受控数据字典的改变必须经版本化迁移发布；禁止线上手工漂移和应用启动时隐式改表。
8. **Local first（本地优先）**：默认开发、交付和恢复路径在受控本地部署完成；云端或外部服务只能作为明确配置的扩展，不能成为权威事实的唯一入口。
9. **Recovery by evidence（以证据恢复）**：恢复以 PostgreSQL 的事务事实、审计记录、对象版本与校验和为依据；缓存、语义索引和运行时检查点按登记版本重建并经校验后重新启用。

## 8.4 技术基线与扩展

关系数据库基线为 **PostgreSQL 16+**。空间能力使用 **PostGIS**，主键、随机标识及摘要等密码学辅助能力使用 **pgcrypto**。`pg_trgm` 用于经评估后确有模糊文本检索需求的字段，`btree_gist` 用于需要 GiST 组合排他约束的时间/空间或范围场景；二者均按需启用，不能作为无差别全库依赖。

向量检索统一使用 Qdrant 的派生集合及其 Payload 过滤能力；**不采用 pgvector，也不对同一向量执行 PostgreSQL/pgvector 与 Qdrant 双写**。Qdrant 写入必须由已提交的 PostgreSQL 修订、出站事件或可重放任务驱动，并按 8.7 的边界适用矩阵在适用时携带 `organization_id` 和 `project_id`、来源 UUID、修订号和索引版本。数据库结构演进使用 Alembic 管理，迁移顺序、兼容窗口与回滚策略见 8.24。

## 8.5 数据分类与存储分工

| 数据分类 | 权威源 | 允许写入者 | 保留方式 | 降级路径 |
|---|---|---|---|---|
| 业务关系数据（组织、项目、资产、巡检、病害、复核、报告元数据） | PostgreSQL | 经服务层授权的领域写模型和版本化迁移 | 事务提交、历史修订、归档策略与 PITR | 只读查询或受控人工续办；禁止写入缓存替代 |
| 空间数据（桥位、道路/路线、构件定位、观测几何） | PostgreSQL + PostGIS | 资产、巡检服务及受控导入任务 | 几何与 SRID 校验、修订和备份 | 使用已提交的属性与最近有效空间修订，待空间服务恢复后校验补算 |
| 对象数据（影像、视频、点云、模型产物、签发文件） | MinIO 对象字节 + PostgreSQL 对象元数据 | 受控上传服务、采集导入任务、报告签发服务 | 对象版本、校验和、保留/归档策略及 PostgreSQL 引用 | 暂停新上传；使用已校验副本或只读元数据，恢复后按校验和核验 |
| 语义索引（RAG、Memory 向量与过滤 Payload） | PostgreSQL 修订为权威，Qdrant 为派生索引 | 仅索引投影器/重建任务 | 可删除重建；索引版本与来源修订登记在 PostgreSQL | 退化为 PostgreSQL 元数据、全文/条件检索或人工查询；不得将 Qdrant 命中直接写回事实 |
| 缓存与协调数据 | Redis | 缓存、调度、限流和幂等协调组件 | TTL、可丢失，不纳入事实备份 | 直接访问 PostgreSQL；以数据库唯一约束和事务保证正确性 |
| 框架 Checkpoint | LangGraph Checkpoint 存储，运行登记在 PostgreSQL | 经编排服务执行的图运行时 | 按线程/运行保留并与运行记录关联 | 从最后已提交的 Workflow State 或输入证据重新启动/人工接管 |
| Workflow State | PostgreSQL `bridgeai_workflow` | 工作流领域服务、人工复核服务 | 事务状态迁移、审计、归档 | 以 PostgreSQL 状态为准，Checkpoint/Redis 恢复后仅作续跑辅助 |
| 审计数据与数据血缘 | PostgreSQL `bridgeai_audit`，对象版本为外部证据 | 审计写入器、受控数据库触发器/服务事件 | 追加写、保留策略、备份与校验 | 仅允许读取既有证据；不得清空或由缓存补造 |

## 8.6 Schema 总体架构

PostgreSQL 以九个业务 Schema 隔离领域对象、授权边界和迁移所有权。Schema 不是绕过 RLS 的安全边界：所有对外访问仍须经角色、RLS 和项目范围控制。表归属由其权威写模型决定，禁止因为查询便利把同一事实复制成跨域可写表。

初始化迁移至少创建下列扩展与业务 Schema：

```sql
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
```

| Schema | 领域职责 | 允许依赖方向 |
|---|---|---|
| `bridgeai_identity` | 组织、用户、服务主体、角色与授权主体 | 独立基础域；被其他域引用 |
| `bridgeai_core` | 项目、受控字典、通用工件元数据、引用与基础治理 | 可引用 `bridgeai_identity`；被其余业务域引用 |
| `bridgeai_asset` | 桥梁、道路、路线、构件及其空间基准 | 可引用 identity/core |
| `bridgeai_inspection` | 采集、数据集、病害、观测、量测、修订与演变 | 可引用 identity/core/asset |
| `bridgeai_workflow` | 工作流运行、任务、人工复核、状态迁移与出站事件 | 可引用 identity/core/asset/inspection |
| `bridgeai_knowledge` | 知识源、文档修订、切分、索引登记与引用 | 可引用 identity/core/asset/inspection |
| `bridgeai_memory` | 会话记忆、上下文条目、摘要与索引登记 | 可引用 identity/core/workflow/knowledge |
| `bridgeai_report` | 报告草稿、引用、复核、签发与交付工件 | 可引用 identity/core/asset/inspection/workflow/knowledge/memory |
| `bridgeai_audit` | 审计事件、安全事件、血缘、访问和变更证据 | 可只读引用所有业务域的稳定 UUID；业务域不得反向外键依赖 audit |

依赖仅可从上表左侧领域指向其列出的基础或上游领域；`bridgeai_identity`、`bridgeai_core`、`bridgeai_asset`、`bridgeai_inspection`、`bridgeai_workflow` 的业务事实不得反向依赖知识、记忆、报告或审计域。跨域外键必须引用上游域的稳定 UUID，并按 8.7 的边界适用矩阵保持组织和项目范围一致：项目级关联使用 `(organization_id, project_id)` 组合唯一键/组合外键，组织级关联使用 `organization_id` 作用域约束；组织根、项目根和真正全局表不伪造不适用的边界列。禁止以跨域外键建立循环依赖。

跨域读取通过明确命名的只读视图、稳定 API 或受控查询模型提供。只读视图只投影已授权字段，必须保留租户与项目过滤前提，不能成为写入绕行通道。除迁移角色、域所有者和经授权的领域服务外，禁止对其他 Schema 的基表进行任意写入；报表、知识、记忆和审计对业务域均不得执行反向补写。

## 8.7 全局命名、ID、时间与状态规范

以下规范对本章后续所有 DDL 生效；任何例外必须在迁移、表注释和架构决策记录中明确其理由、影响范围和兼容策略。

| 范畴 | 强制规范 |
|---|---|
| 命名 | Schema、表、列、索引、约束和视图均使用 `snake_case`；表名使用复数业务名，外键列为 `<referenced_entity>_id`，约束和索引使用可读、稳定的前缀。 |
| 主键与业务编码 | 每个实体以 `UUID` 作为主键，默认可由 `gen_random_uuid()` 生成；对人可读或外部对接编码另设独立、受唯一约束的业务编码，禁止以业务编码承担主键职责。 |
| 租户与项目 | `organization_id`、`project_id` 的存在与空值规则必须遵循下表的边界适用矩阵；项目必须属于组织，项目级子实体的组合外键必须阻止跨组织、跨项目关联。 |
| 时间 | 所有业务事件、记录创建/更新、有效期、过期和审计时间使用 `TIMESTAMPTZ`；禁止无时区 `timestamp`。至少区分 `observed_at`（观测发生）、`valid_from`/`valid_to`（业务有效）和 `created_at`/`updated_at`（记录写入）；不存在的语义不得用其他时间列冒充。 |
| 数值与单位 | 工程量、尺寸、面积、体积、质量、阈值等精确数值使用 `NUMERIC`，并以同一实体的非空 `unit_code` 或明确的字段级单位代码关联；不得以二进制浮点数存储需要复算、比较或出具报告的工程量。 |
| 约束 | 主外键、`NOT NULL`、`UNIQUE`、`CHECK` 和组合唯一约束优先在数据库实现；自然唯一性、租户/项目作用域、时间区间和修订号必须使用组合约束表达，不能仅依赖服务端约定。 |
| 状态 | 状态、类型和阶段使用受 `CHECK` 约束的文本代码或受控字典外键；需要演进时由迁移扩展允许值和状态机规则。频繁演进的状态不使用 PostgreSQL `ENUM`，以避免新增/废弃状态造成类型变更、部署耦合和回滚困难。 |
| JSONB | `JSONB` 仅保存可扩展、低频查询的对象属性；列默认值使用 `'{}'::jsonb`（数组语义另行声明），并以 `CHECK (jsonb_typeof(column_name) = 'object')` 约束对象形态。核心字段必须提升为结构化列。 |
| 审计字段与并发 | 可变业务记录必须包含 `created_at`、`created_by`、`updated_at`、`updated_by` 及非空的乐观锁 `version`；写入按版本比较并递增。不可变修订记录保留创建者与创建时间，并由新修订替代而非原位更新。 |

租户和项目边界按实体层级适用；“不设列”表示该表不声明该字段，不以可空外键伪造上级范围。所有适用的边界列均为 `UUID NOT NULL`，除真正全局系统表外不得通过空值绕过 RLS 或范围约束。

| 表类别 | `organization_id` | `project_id` | 空值/字段规则 | 必需的范围约束 |
|---|---|---|---|---|
| 组织根表（如 `organizations`） | 不设列；表自身 `id` 即组织 UUID | 不设列 | 两列均不适用，不得将组织自身作为外键回指自身 | `PRIMARY KEY (id)`；组织业务编码在全局范围唯一 |
| 项目根表（如 `projects`） | 必须设为 `UUID NOT NULL` | 不设列；表自身 `id` 即项目 UUID | 项目属于且仅属于一个组织；不以冗余 `project_id` 指向自身 | `FOREIGN KEY (organization_id)`；`UNIQUE (id, organization_id)` 供项目级组合外键引用 |
| 组织级表（如用户、成员、组织角色） | 必须设为 `UUID NOT NULL` | 不设列 | 仅在组织范围内存在；不得以 `project_id NULL` 表示组织级 | `FOREIGN KEY (organization_id)`；业务唯一性以 `organization_id` 组成作用域（例如 `UNIQUE (organization_id, user_id)`） |
| 项目级业务表（资产、巡检、病害、工作流、知识、记忆、报告等） | 必须设为 `UUID NOT NULL` | 必须设为 `UUID NOT NULL` | 两列均不可空，且项目必须隶属同一组织 | `FOREIGN KEY (organization_id)`；`FOREIGN KEY (project_id, organization_id) REFERENCES projects (id, organization_id)`；下游跨表关联以同一组合键约束 |
| 真正全局系统表（如迁移元数据或无租户载荷的受控系统字典） | 不设列 | 不设列 | 仅限不承载组织、项目、用户业务数据的系统记录；必须在表注释和迁移中说明全局理由 | 全局唯一键；一旦承载租户业务数据，必须重分类为上述组织级或项目级表 |

## 8.8 组织、用户、角色与项目模型

身份域将人员用户和服务主体分表存储，避免将 API 客户端伪装为人员账号。`users.status = 'disabled'` 只禁止后续登录，不删除用户、成员资格或已有审计主体 UUID。组织成员资格是人员进入组织的权威记录；项目成员资格在此基础上授予项目访问，或直接授予同组织的服务主体。

```sql
CREATE TABLE bridgeai_identity.organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_code TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT uq_organizations_code UNIQUE (organization_code),
    CONSTRAINT ck_organizations_code_nonblank CHECK (btrim(organization_code) <> ''),
    CONSTRAINT ck_organizations_name_nonblank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_organizations_status CHECK (status IN ('active', 'suspended', 'closed')),
    CONSTRAINT ck_organizations_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ck_organizations_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_identity.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    user_code TEXT NOT NULL,
    email TEXT NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    disabled_at TIMESTAMPTZ,
    disabled_reason TEXT,
    last_login_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_users_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT uq_users_id_organization UNIQUE (id, organization_id),
    CONSTRAINT uq_users_organization_code UNIQUE (organization_id, user_code),
    CONSTRAINT ck_users_code_nonblank CHECK (btrim(user_code) <> ''),
    CONSTRAINT ck_users_email_normalized
        CHECK (email = lower(btrim(email)) AND position('@' IN email) > 1),
    CONSTRAINT ck_users_display_name_nonblank CHECK (btrim(display_name) <> ''),
    CONSTRAINT ck_users_status CHECK (status IN ('invited', 'active', 'locked', 'disabled')),
    CONSTRAINT ck_users_disabled_state CHECK (
        (status = 'disabled' AND disabled_at IS NOT NULL)
        OR (status <> 'disabled' AND disabled_at IS NULL AND disabled_reason IS NULL)
    ),
    CONSTRAINT ck_users_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ck_users_version_positive CHECK (version > 0)
);

CREATE UNIQUE INDEX uq_users_organization_email_ci
    ON bridgeai_identity.users (organization_id, lower(email));

CREATE TABLE bridgeai_identity.service_principals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    principal_code TEXT NOT NULL,
    display_name TEXT NOT NULL,
    authentication_method TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    credential_expires_at TIMESTAMPTZ,
    disabled_at TIMESTAMPTZ,
    last_authenticated_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_service_principals_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT uq_service_principals_id_organization UNIQUE (id, organization_id),
    CONSTRAINT uq_service_principals_organization_code
        UNIQUE (organization_id, principal_code),
    CONSTRAINT ck_service_principals_code_nonblank CHECK (btrim(principal_code) <> ''),
    CONSTRAINT ck_service_principals_name_nonblank CHECK (btrim(display_name) <> ''),
    CONSTRAINT ck_service_principals_auth_method
        CHECK (authentication_method IN ('mtls', 'private_key_jwt', 'client_secret')),
    CONSTRAINT ck_service_principals_status
        CHECK (status IN ('active', 'suspended', 'disabled')),
    CONSTRAINT ck_service_principals_disabled_state CHECK (
        (status = 'disabled' AND disabled_at IS NOT NULL)
        OR (status <> 'disabled' AND disabled_at IS NULL)
    ),
    CONSTRAINT ck_service_principals_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ck_service_principals_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_identity.organization_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    user_id UUID NOT NULL,
    role_code TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    valid_from TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_organization_memberships_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_organization_memberships_user_scope
        FOREIGN KEY (user_id, organization_id)
        REFERENCES bridgeai_identity.users (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT uq_organization_memberships_id_organization UNIQUE (id, organization_id),
    CONSTRAINT uq_organization_memberships_organization_user
        UNIQUE (organization_id, user_id),
    CONSTRAINT ck_organization_memberships_role_nonblank CHECK (btrim(role_code) <> ''),
    CONSTRAINT ck_organization_memberships_status
        CHECK (status IN ('invited', 'active', 'suspended', 'revoked')),
    CONSTRAINT ck_organization_memberships_valid_range
        CHECK (valid_to IS NULL OR valid_to > valid_from),
    CONSTRAINT ck_organization_memberships_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_core.projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_code TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planning',
    valid_from TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_projects_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT uq_projects_id_organization UNIQUE (id, organization_id),
    CONSTRAINT uq_projects_organization_code UNIQUE (organization_id, project_code),
    CONSTRAINT ck_projects_code_nonblank CHECK (btrim(project_code) <> ''),
    CONSTRAINT ck_projects_name_nonblank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_projects_status
        CHECK (status IN ('planning', 'active', 'suspended', 'completed', 'archived')),
    CONSTRAINT ck_projects_valid_range CHECK (valid_to IS NULL OR valid_to > valid_from),
    CONSTRAINT ck_projects_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ck_projects_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_core.project_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    principal_type TEXT NOT NULL,
    user_id UUID,
    service_principal_id UUID,
    role_code TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    valid_from TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_project_memberships_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_project_memberships_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_project_memberships_user_organization_membership
        FOREIGN KEY (organization_id, user_id)
        REFERENCES bridgeai_identity.organization_memberships (organization_id, user_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_project_memberships_service_principal_scope
        FOREIGN KEY (service_principal_id, organization_id)
        REFERENCES bridgeai_identity.service_principals (id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_project_memberships_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT ck_project_memberships_principal_shape CHECK (
        (principal_type = 'user' AND user_id IS NOT NULL AND service_principal_id IS NULL)
        OR
        (principal_type = 'service_principal' AND user_id IS NULL AND service_principal_id IS NOT NULL)
    ),
    CONSTRAINT ck_project_memberships_role_nonblank CHECK (btrim(role_code) <> ''),
    CONSTRAINT ck_project_memberships_status
        CHECK (status IN ('active', 'suspended', 'revoked')),
    CONSTRAINT ck_project_memberships_valid_range
        CHECK (valid_to IS NULL OR valid_to > valid_from),
    CONSTRAINT ck_project_memberships_version_positive CHECK (version > 0)
);

CREATE UNIQUE INDEX uq_project_memberships_user
    ON bridgeai_core.project_memberships (organization_id, project_id, user_id)
    WHERE principal_type = 'user';

CREATE UNIQUE INDEX uq_project_memberships_service_principal
    ON bridgeai_core.project_memberships
       (organization_id, project_id, service_principal_id)
    WHERE principal_type = 'service_principal';
```

`created_by`/`updated_by` 保留稳定审计主体 UUID，不对 `users` 建单表外键：调用者可以是人员或服务主体，其不可变审计映射由 8.19 的审计域保存。禁止为了满足单表外键而把服务主体写入 `users`。

## 8.9 Artifact 与对象存储元数据模型

`artifacts` 是业务上稳定的逻辑工件，`artifact_versions` 是该工件在对象存储中的不可变字节版本。后续数据集、病害证据和报告只能通过本领域的强类型关联表引用其中一层；本章不建立 `artifact_links` 或含 `entity_type/entity_id` 的多态关联。

```sql
CREATE TABLE bridgeai_core.artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    artifact_code TEXT NOT NULL,
    artifact_kind TEXT NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    sensitivity_level TEXT NOT NULL DEFAULT 'internal',
    retention_policy_code TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_artifacts_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_artifacts_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT uq_artifacts_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_artifacts_project_code
        UNIQUE (organization_id, project_id, artifact_code),
    CONSTRAINT ck_artifacts_code_nonblank CHECK (btrim(artifact_code) <> ''),
    CONSTRAINT ck_artifacts_kind_nonblank CHECK (btrim(artifact_kind) <> ''),
    CONSTRAINT ck_artifacts_name_nonblank CHECK (btrim(display_name) <> ''),
    CONSTRAINT ck_artifacts_status CHECK (status IN ('active', 'archived', 'revoked')),
    CONSTRAINT ck_artifacts_sensitivity
        CHECK (sensitivity_level IN ('public', 'internal', 'confidential', 'restricted')),
    CONSTRAINT ck_artifacts_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ck_artifacts_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_core.artifact_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    artifact_id UUID NOT NULL,
    revision_no BIGINT NOT NULL,
    provider TEXT NOT NULL,
    bucket TEXT NOT NULL,
    object_key TEXT NOT NULL,
    version_id TEXT NOT NULL,
    sha256 CHAR(64),
    size_bytes BIGINT,
    media_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'staged',
    sensitivity_level TEXT NOT NULL DEFAULT 'internal',
    verified_at TIMESTAMPTZ,
    activated_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revocation_reason TEXT,
    retention_until TIMESTAMPTZ,
    legal_hold BOOLEAN NOT NULL DEFAULT FALSE,
    orphaned_at TIMESTAMPTZ,
    reclaim_after TIMESTAMPTZ,
    reclaim_attempts INTEGER NOT NULL DEFAULT 0,
    reclaim_last_error TEXT,
    deletion_requested_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_artifact_versions_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_artifact_versions_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_artifact_versions_artifact_scope
        FOREIGN KEY (artifact_id, organization_id, project_id)
        REFERENCES bridgeai_core.artifacts (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_artifact_versions_id_scope
        UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_artifact_versions_id_scope_artifact
        UNIQUE (id, organization_id, project_id, artifact_id),
    CONSTRAINT uq_artifact_versions_revision
        UNIQUE (artifact_id, revision_no),
    CONSTRAINT uq_artifact_versions_object
        UNIQUE (provider, bucket, object_key, version_id),
    CONSTRAINT ck_artifact_versions_revision_positive CHECK (revision_no > 0),
    CONSTRAINT ck_artifact_versions_provider CHECK (provider IN ('minio', 's3')),
    CONSTRAINT ck_artifact_versions_bucket_nonblank CHECK (btrim(bucket) <> ''),
    CONSTRAINT ck_artifact_versions_object_key_nonblank CHECK (btrim(object_key) <> ''),
    CONSTRAINT ck_artifact_versions_version_id_nonblank CHECK (btrim(version_id) <> ''),
    CONSTRAINT ck_artifact_versions_sha256 CHECK (
        sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT ck_artifact_versions_size_nonnegative CHECK (size_bytes IS NULL OR size_bytes >= 0),
    CONSTRAINT ck_artifact_versions_media_type_nonblank CHECK (btrim(media_type) <> ''),
    CONSTRAINT ck_artifact_versions_status CHECK (
        status IN ('staged', 'verified', 'active', 'archived', 'revoked', 'deleting', 'deleted')
    ),
    CONSTRAINT ck_artifact_versions_sensitivity CHECK (
        sensitivity_level IN ('public', 'internal', 'confidential', 'restricted')
    ),
    CONSTRAINT ck_artifact_versions_verified_payload CHECK (
        status = 'staged'
        OR (status IN ('deleting', 'deleted') AND orphaned_at IS NOT NULL)
        OR (sha256 IS NOT NULL AND size_bytes IS NOT NULL AND verified_at IS NOT NULL)
    ),
    CONSTRAINT ck_artifact_versions_activation_time CHECK (
        status NOT IN ('active', 'archived', 'revoked', 'deleting', 'deleted')
        OR activated_at IS NOT NULL
        OR orphaned_at IS NOT NULL
    ),
    CONSTRAINT ck_artifact_versions_terminal_times CHECK (
        (status <> 'archived' OR archived_at IS NOT NULL)
        AND (status <> 'revoked' OR (revoked_at IS NOT NULL AND revocation_reason IS NOT NULL))
        AND (status NOT IN ('deleting', 'deleted') OR deletion_requested_at IS NOT NULL)
        AND (status <> 'deleted' OR deleted_at IS NOT NULL)
    ),
    CONSTRAINT ck_artifact_versions_orphan_reclaim CHECK (
        (orphaned_at IS NULL AND reclaim_after IS NULL)
        OR (orphaned_at IS NOT NULL AND reclaim_after IS NOT NULL AND reclaim_after >= orphaned_at)
    ),
    CONSTRAINT ck_artifact_versions_reclaim_attempts CHECK (reclaim_attempts >= 0),
    CONSTRAINT ck_artifact_versions_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ck_artifact_versions_version_positive CHECK (version > 0)
);

CREATE UNIQUE INDEX uq_artifact_versions_one_active
    ON bridgeai_core.artifact_versions (artifact_id)
    WHERE status = 'active';

CREATE INDEX ix_artifact_versions_scope_status
    ON bridgeai_core.artifact_versions
       (organization_id, project_id, artifact_id, status);

CREATE INDEX ix_artifact_versions_orphan_reclaim
    ON bridgeai_core.artifact_versions (reclaim_after)
    WHERE orphaned_at IS NOT NULL AND status <> 'deleted';

CREATE OR REPLACE FUNCTION bridgeai_core.enforce_artifact_version_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'staged' THEN
            RAISE EXCEPTION 'artifact version initial status must be staged, got %', NEW.status;
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status <> 'staged' AND ROW(
        NEW.organization_id, NEW.project_id, NEW.artifact_id, NEW.revision_no,
        NEW.provider, NEW.bucket, NEW.object_key, NEW.version_id,
        NEW.sha256, NEW.size_bytes, NEW.media_type
    ) IS DISTINCT FROM ROW(
        OLD.organization_id, OLD.project_id, OLD.artifact_id, OLD.revision_no,
        OLD.provider, OLD.bucket, OLD.object_key, OLD.version_id,
        OLD.sha256, OLD.size_bytes, OLD.media_type
    ) THEN
        RAISE EXCEPTION 'verified artifact object identity and digest are immutable';
    END IF;

    IF OLD.status = NEW.status THEN
        RETURN NEW;
    ELSIF NOT (
        (OLD.status = 'staged' AND NEW.status = 'verified')
        OR (OLD.status = 'verified' AND NEW.status = 'active')
        OR (OLD.status = 'active' AND NEW.status IN ('archived', 'revoked'))
        OR (OLD.status IN ('archived', 'revoked') AND NEW.status = 'deleting')
        OR (OLD.status = 'deleting' AND NEW.status = 'deleted')
        OR (
            OLD.status IN ('staged', 'verified')
            AND NEW.status = 'deleting'
            AND NEW.orphaned_at IS NOT NULL
            AND NEW.reclaim_after IS NOT NULL
        )
    ) THEN
        RAISE EXCEPTION 'invalid artifact version transition: % -> %', OLD.status, NEW.status;
    END IF;

    IF NEW.status = 'deleting' THEN
        IF NEW.legal_hold THEN
            RAISE EXCEPTION 'artifact version % is under legal hold', NEW.id;
        END IF;
        IF NEW.retention_until IS NOT NULL AND NEW.retention_until > CURRENT_TIMESTAMP THEN
            RAISE EXCEPTION 'artifact version % is still retained', NEW.id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_artifact_versions_transition
BEFORE INSERT OR UPDATE
ON bridgeai_core.artifact_versions
FOR EACH ROW
EXECUTE FUNCTION bridgeai_core.enforce_artifact_version_transition();
```

正常生命周期是 `staged → verified → active → archived/revoked → deleting → deleted`。唯一例外是对已登记但未激活的孤立对象回收：对账任务必须先写入 `orphaned_at` 和不早于其的 `reclaim_after`，才能从 `staged`/`verified` 进入 `deleting`。对象存储中完全未登记的孤立字节由 bucket inventory 对账发现；强保留期和 legal hold 在进入删除状态时由数据库拒绝绕过。

## 8.10 桥梁、道路、路线与构件模型

`assets.id` 和 `components.id` 是内部稳定 UUID；`asset_code`/`component_code` 是可读的当前正式编码，不承担主键职责。资产范围只允许 `bridge` 和 `road`。桥梁与道路专有属性使用一对一子类表，外键同时带上组织、项目和资产类型，不可将道路资产写入桥梁属性表。

```sql
CREATE TABLE bridgeai_asset.assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    asset_code TEXT NOT NULL,
    official_code TEXT,
    asset_type TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    commissioned_on DATE,
    deactivated_at TIMESTAMPTZ,
    deactivation_reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_assets_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_assets_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT uq_assets_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_assets_id_scope_type UNIQUE (id, organization_id, project_id, asset_type),
    CONSTRAINT uq_assets_project_code UNIQUE (organization_id, project_id, asset_code),
    CONSTRAINT uq_assets_project_official_code
        UNIQUE (organization_id, project_id, official_code),
    CONSTRAINT ck_assets_code_nonblank CHECK (btrim(asset_code) <> ''),
    CONSTRAINT ck_assets_official_code_nonblank
        CHECK (official_code IS NULL OR btrim(official_code) <> ''),
    CONSTRAINT ck_assets_type CHECK (asset_type IN ('bridge', 'road')),
    CONSTRAINT ck_assets_name_nonblank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_assets_status CHECK (status IN ('planning', 'active', 'inactive', 'retired')),
    CONSTRAINT ck_assets_deactivation_state CHECK (
        (status IN ('inactive', 'retired') AND deactivated_at IS NOT NULL)
        OR (status IN ('planning', 'active') AND deactivated_at IS NULL AND deactivation_reason IS NULL)
    ),
    CONSTRAINT ck_assets_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ck_assets_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_asset.bridge_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    asset_id UUID NOT NULL,
    asset_type TEXT NOT NULL DEFAULT 'bridge',
    bridge_type_code TEXT NOT NULL,
    span_count INTEGER,
    total_length_m NUMERIC(14, 3),
    deck_width_m NUMERIC(12, 3),
    design_load_code TEXT,
    waterway_name TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_bridge_profiles_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_bridge_profiles_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_bridge_profiles_bridge_asset
        FOREIGN KEY (asset_id, organization_id, project_id, asset_type)
        REFERENCES bridgeai_asset.assets (id, organization_id, project_id, asset_type)
        ON DELETE RESTRICT,
    CONSTRAINT uq_bridge_profiles_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_bridge_profiles_asset_scope
        UNIQUE (asset_id, organization_id, project_id),
    CONSTRAINT ck_bridge_profiles_asset_type CHECK (asset_type = 'bridge'),
    CONSTRAINT ck_bridge_profiles_type_nonblank CHECK (btrim(bridge_type_code) <> ''),
    CONSTRAINT ck_bridge_profiles_span_count CHECK (span_count IS NULL OR span_count > 0),
    CONSTRAINT ck_bridge_profiles_total_length CHECK (total_length_m IS NULL OR total_length_m > 0),
    CONSTRAINT ck_bridge_profiles_deck_width CHECK (deck_width_m IS NULL OR deck_width_m > 0),
    CONSTRAINT ck_bridge_profiles_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ck_bridge_profiles_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_asset.road_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    asset_id UUID NOT NULL,
    asset_type TEXT NOT NULL DEFAULT 'road',
    section_code TEXT NOT NULL,
    route_code TEXT NOT NULL,
    direction_code TEXT NOT NULL,
    road_class_code TEXT,
    start_chainage_m NUMERIC(14, 3) NOT NULL,
    end_chainage_m NUMERIC(14, 3) NOT NULL,
    lane_count INTEGER,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_road_sections_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_road_sections_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_road_sections_road_asset
        FOREIGN KEY (asset_id, organization_id, project_id, asset_type)
        REFERENCES bridgeai_asset.assets (id, organization_id, project_id, asset_type)
        ON DELETE RESTRICT,
    CONSTRAINT uq_road_sections_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_road_sections_asset_scope
        UNIQUE (asset_id, organization_id, project_id),
    CONSTRAINT uq_road_sections_project_code
        UNIQUE (organization_id, project_id, section_code),
    CONSTRAINT ck_road_sections_asset_type CHECK (asset_type = 'road'),
    CONSTRAINT ck_road_sections_code_nonblank CHECK (btrim(section_code) <> ''),
    CONSTRAINT ck_road_sections_route_nonblank CHECK (btrim(route_code) <> ''),
    CONSTRAINT ck_road_sections_direction_nonblank CHECK (btrim(direction_code) <> ''),
    CONSTRAINT ck_road_sections_chainage CHECK (
        start_chainage_m >= 0 AND end_chainage_m > start_chainage_m
    ),
    CONSTRAINT ck_road_sections_lane_count CHECK (lane_count IS NULL OR lane_count > 0),
    CONSTRAINT ck_road_sections_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ck_road_sections_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_asset.components (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    asset_id UUID NOT NULL,
    parent_component_id UUID,
    component_code TEXT NOT NULL,
    component_type_code TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    installed_on DATE,
    deactivated_at TIMESTAMPTZ,
    deactivation_reason TEXT,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_components_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_components_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_components_asset_scope
        FOREIGN KEY (asset_id, organization_id, project_id)
        REFERENCES bridgeai_asset.assets (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_components_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_components_id_scope_asset
        UNIQUE (id, organization_id, project_id, asset_id),
    CONSTRAINT uq_components_asset_code
        UNIQUE (organization_id, project_id, asset_id, component_code),
    CONSTRAINT fk_components_parent_same_asset
        FOREIGN KEY (parent_component_id, organization_id, project_id, asset_id)
        REFERENCES bridgeai_asset.components (id, organization_id, project_id, asset_id)
        DEFERRABLE INITIALLY IMMEDIATE,
    CONSTRAINT ck_components_not_own_parent
        CHECK (parent_component_id IS NULL OR parent_component_id <> id),
    CONSTRAINT ck_components_code_nonblank CHECK (btrim(component_code) <> ''),
    CONSTRAINT ck_components_type_nonblank CHECK (btrim(component_type_code) <> ''),
    CONSTRAINT ck_components_name_nonblank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_components_status CHECK (status IN ('active', 'inactive', 'retired')),
    CONSTRAINT ck_components_deactivation_state CHECK (
        (status IN ('inactive', 'retired') AND deactivated_at IS NOT NULL)
        OR (status = 'active' AND deactivated_at IS NULL AND deactivation_reason IS NULL)
    ),
    CONSTRAINT ck_components_attributes_object CHECK (jsonb_typeof(attributes) = 'object'),
    CONSTRAINT ck_components_version_positive CHECK (version > 0)
);

CREATE OR REPLACE FUNCTION bridgeai_asset.reject_component_cycle()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    cycle_found BOOLEAN;
BEGIN
    IF NEW.parent_component_id IS NULL THEN
        RETURN NEW;
    END IF;

    -- 对同一资产的构件树写入建立唯一串行化点，
    -- 使等待者在前一事务提交后再读取祖先链。
    PERFORM 1
    FROM bridgeai_asset.assets AS a
    WHERE a.id = NEW.asset_id
      AND a.organization_id = NEW.organization_id
      AND a.project_id = NEW.project_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'component asset scope does not exist for component %', NEW.id
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    WITH RECURSIVE ancestors AS (
        SELECT c.id, c.parent_component_id
        FROM bridgeai_asset.components AS c
        WHERE c.id = NEW.parent_component_id
          AND c.organization_id = NEW.organization_id
          AND c.project_id = NEW.project_id
          AND c.asset_id = NEW.asset_id
        UNION
        SELECT c.id, c.parent_component_id
        FROM bridgeai_asset.components AS c
        JOIN ancestors AS a ON c.id = a.parent_component_id
        WHERE c.organization_id = NEW.organization_id
          AND c.project_id = NEW.project_id
          AND c.asset_id = NEW.asset_id
    )
    SELECT EXISTS (SELECT 1 FROM ancestors WHERE id = NEW.id)
    INTO cycle_found;

    IF cycle_found THEN
        RAISE EXCEPTION 'component hierarchy cycle detected for component %', NEW.id;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_components_reject_cycle
BEFORE INSERT OR UPDATE OF parent_component_id, organization_id, project_id, asset_id
ON bridgeai_asset.components
FOR EACH ROW
EXECUTE FUNCTION bridgeai_asset.reject_component_cycle();

CREATE TABLE bridgeai_asset.component_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    asset_id UUID NOT NULL,
    component_id UUID NOT NULL,
    alias_code TEXT NOT NULL,
    alias_type TEXT NOT NULL,
    source_system TEXT,
    valid_from TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMPTZ,
    mapping_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_component_aliases_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_component_aliases_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_component_aliases_component_same_asset
        FOREIGN KEY (component_id, organization_id, project_id, asset_id)
        REFERENCES bridgeai_asset.components (id, organization_id, project_id, asset_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_component_aliases_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_component_aliases_asset_alias
        UNIQUE (organization_id, project_id, asset_id, alias_code),
    CONSTRAINT ck_component_aliases_code_nonblank CHECK (btrim(alias_code) <> ''),
    CONSTRAINT ck_component_aliases_type CHECK (
        alias_type IN ('project_alias', 'former_official_code', 'external_code')
    ),
    CONSTRAINT ck_component_aliases_valid_range CHECK (valid_to IS NULL OR valid_to > valid_from),
    CONSTRAINT ck_component_aliases_renumber_reason CHECK (
        alias_type <> 'former_official_code' OR mapping_reason IS NOT NULL
    ),
    CONSTRAINT ck_component_aliases_version_positive CHECK (version > 0)
);

CREATE INDEX ix_components_parent_scope
    ON bridgeai_asset.components
       (organization_id, project_id, asset_id, parent_component_id);

CREATE INDEX ix_component_aliases_component_scope
    ON bridgeai_asset.component_aliases
       (organization_id, project_id, asset_id, component_id);
```

构件停用只更改 `components.status/deactivated_at/deactivation_reason`，不删除稳定 UUID。重编码在同一事务中更新 `components.component_code`，并把原编码以 `component_aliases.alias_type = 'former_official_code'` 映射回同一 `component_id`；项目俗称使用 `project_alias`，不得覆盖正式编码。自组合外键阻止跨组织、跨项目和跨资产挂接；重挂接前的 `BEFORE` 触发器先锁定共同 `assets` 行，将同资产构件树写入串行化后再检查祖先链，阻止单事务和并发双事务成环。

## 8.11 PostGIS 空间与工程定位设计

空间库内的标准几何统一为 **CGCS2000 / EPSG:4490**。`geom_4490` 用于空间过滤和交换；`source_geom/source_srid` 保留导入源几何及坐标参考；非 4490 数据必须登记转换工具、版本、参数和位置精度。工程定位同时保留局部坐标、路线桩号、横向偏距、车道、构件表面和高程，不用 JSONB 替代这些核心查询列。

```sql
CREATE TABLE bridgeai_asset.spatial_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    asset_id UUID NOT NULL,
    component_id UUID,
    location_kind TEXT NOT NULL,
    geom_4490 geometry(Geometry, 4490) NOT NULL,
    source_geom geometry(Geometry),
    source_srid INTEGER NOT NULL,
    transform_tool TEXT,
    transform_tool_version TEXT,
    transform_parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    position_accuracy_m NUMERIC(12, 4) NOT NULL,
    local_reference_code TEXT,
    local_x NUMERIC(14, 4),
    local_y NUMERIC(14, 4),
    local_z NUMERIC(14, 4),
    chainage_m NUMERIC(14, 3),
    lateral_offset_m NUMERIC(12, 3),
    lane_code TEXT,
    component_surface_code TEXT,
    elevation_m NUMERIC(14, 4),
    vertical_datum_code TEXT,
    valid_from TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_spatial_locations_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_spatial_locations_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_spatial_locations_asset_scope
        FOREIGN KEY (asset_id, organization_id, project_id)
        REFERENCES bridgeai_asset.assets (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_spatial_locations_component_same_asset
        FOREIGN KEY (component_id, organization_id, project_id, asset_id)
        REFERENCES bridgeai_asset.components (id, organization_id, project_id, asset_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_spatial_locations_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_spatial_locations_id_scope_asset
        UNIQUE (id, organization_id, project_id, asset_id),
    CONSTRAINT ck_spatial_locations_kind_nonblank CHECK (btrim(location_kind) <> ''),
    CONSTRAINT ck_spatial_locations_geom_4490 CHECK (
        ST_SRID(geom_4490) = 4490
        AND NOT ST_IsEmpty(geom_4490)
        AND ST_IsValid(geom_4490)
        AND ST_CoordDim(geom_4490) = 2
    ),
    CONSTRAINT ck_spatial_locations_source_srid CHECK (source_srid > 0),
    CONSTRAINT ck_spatial_locations_source_geom CHECK (
        source_geom IS NULL
        OR (
            ST_SRID(source_geom) = source_srid
            AND NOT ST_IsEmpty(source_geom)
            AND ST_IsValid(source_geom)
        )
    ),
    CONSTRAINT ck_spatial_locations_transform_trace CHECK (
        source_srid = 4490
        OR (
            source_geom IS NOT NULL
            AND transform_tool IS NOT NULL
            AND btrim(transform_tool) <> ''
            AND transform_tool_version IS NOT NULL
            AND btrim(transform_tool_version) <> ''
            AND transform_parameters <> '{}'::jsonb
        )
    ),
    CONSTRAINT ck_spatial_locations_transform_parameters_object
        CHECK (jsonb_typeof(transform_parameters) = 'object'),
    CONSTRAINT ck_spatial_locations_accuracy CHECK (position_accuracy_m > 0),
    CONSTRAINT ck_spatial_locations_local_xy CHECK (
        (local_x IS NULL AND local_y IS NULL AND local_z IS NULL AND local_reference_code IS NULL)
        OR
        (local_x IS NOT NULL AND local_y IS NOT NULL
         AND local_reference_code IS NOT NULL AND btrim(local_reference_code) <> '')
    ),
    CONSTRAINT ck_spatial_locations_chainage CHECK (chainage_m IS NULL OR chainage_m >= 0),
    CONSTRAINT ck_spatial_locations_offset_requires_chainage CHECK (
        lateral_offset_m IS NULL OR chainage_m IS NOT NULL
    ),
    CONSTRAINT ck_spatial_locations_lane_requires_chainage CHECK (
        lane_code IS NULL OR (chainage_m IS NOT NULL AND btrim(lane_code) <> '')
    ),
    CONSTRAINT ck_spatial_locations_surface_requires_component CHECK (
        component_surface_code IS NULL
        OR (component_id IS NOT NULL AND btrim(component_surface_code) <> '')
    ),
    CONSTRAINT ck_spatial_locations_elevation_datum CHECK (
        elevation_m IS NULL
        OR (vertical_datum_code IS NOT NULL AND btrim(vertical_datum_code) <> '')
    ),
    CONSTRAINT ck_spatial_locations_valid_range CHECK (valid_to IS NULL OR valid_to > valid_from),
    CONSTRAINT ck_spatial_locations_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ck_spatial_locations_version_positive CHECK (version > 0)
);

CREATE INDEX ix_spatial_locations_scope_asset
    ON bridgeai_asset.spatial_locations (organization_id, project_id, asset_id);

CREATE INDEX ix_spatial_locations_geom_4490
    ON bridgeai_asset.spatial_locations USING GIST (geom_4490);

CREATE INDEX ix_spatial_locations_route_position
    ON bridgeai_asset.spatial_locations
       (organization_id, project_id, asset_id, chainage_m)
    WHERE chainage_m IS NOT NULL;
```

空间查询必须在空间谓词之前同时提供组织、项目和资产过滤。下例的普通复合 B-tree 索引与 GiST 索引可由 PostgreSQL 做 bitmap-and，既不放大跨租户扫描，也不需要把组织 UUID 混入几何类型。

```sql
WITH query_area AS (
    SELECT ST_GeomFromText(:query_wkt, 4490) AS geom
)
SELECT sl.*
FROM bridgeai_asset.spatial_locations AS sl
CROSS JOIN query_area AS qa
WHERE sl.organization_id = :organization_id
  AND sl.project_id = :project_id
  AND sl.asset_id = :asset_id
  AND sl.geom_4490 && qa.geom
  AND ST_Intersects(sl.geom_4490, qa.geom);
```

EPSG:4490 为地理坐标系，不得把其角度差直接解释为米。米制缓冲、距离和面积计算必须在查询或受控派生列中显式转到项目适用的投影坐标系，并保留所用 SRID 和转换参数。

## 8.12 检测批次、采集会话与数据集模型

`inspection_campaigns` 表示一次有计划边界的检测任务，`acquisition_sessions` 表示一段由明确操作者和设备执行的现场采集，`acquisition_datasets` 表示一个可独立导入、质检和隔离的批次。三者都复写 `asset_id` 并由组合外键限定在同一组织、项目和资产内；数据集的对象存储内容只能通过 `dataset_artifacts` 强关联到确定的 Artifact 及其不可变版本。

```sql
CREATE TABLE bridgeai_inspection.inspection_campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    asset_id UUID NOT NULL,
    campaign_code TEXT NOT NULL,
    name TEXT NOT NULL,
    inspection_type TEXT NOT NULL,
    planned_start_at TIMESTAMPTZ NOT NULL,
    planned_end_at TIMESTAMPTZ NOT NULL,
    actual_start_at TIMESTAMPTZ,
    actual_end_at TIMESTAMPTZ,
    scope_location_id UUID,
    planned_scope TEXT NOT NULL,
    coverage_requirements JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'planned',
    cancellation_reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_inspection_campaigns_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_inspection_campaigns_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_inspection_campaigns_asset_scope
        FOREIGN KEY (asset_id, organization_id, project_id)
        REFERENCES bridgeai_asset.assets (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_inspection_campaigns_location_same_asset
        FOREIGN KEY (scope_location_id, organization_id, project_id, asset_id)
        REFERENCES bridgeai_asset.spatial_locations (id, organization_id, project_id, asset_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_inspection_campaigns_id_scope
        UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_inspection_campaigns_id_scope_asset
        UNIQUE (id, organization_id, project_id, asset_id),
    CONSTRAINT uq_inspection_campaigns_project_code
        UNIQUE (organization_id, project_id, campaign_code),
    CONSTRAINT ck_inspection_campaigns_code_nonblank CHECK (btrim(campaign_code) <> ''),
    CONSTRAINT ck_inspection_campaigns_name_nonblank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_inspection_campaigns_type_nonblank CHECK (btrim(inspection_type) <> ''),
    CONSTRAINT ck_inspection_campaigns_planned_range
        CHECK (planned_end_at > planned_start_at),
    CONSTRAINT ck_inspection_campaigns_actual_range
        CHECK (actual_end_at IS NULL OR (actual_start_at IS NOT NULL AND actual_end_at > actual_start_at)),
    CONSTRAINT ck_inspection_campaigns_scope_nonblank CHECK (btrim(planned_scope) <> ''),
    CONSTRAINT ck_inspection_campaigns_coverage_object
        CHECK (jsonb_typeof(coverage_requirements) = 'object'),
    CONSTRAINT ck_inspection_campaigns_status
        CHECK (status IN ('planned', 'in_progress', 'completed', 'cancelled')),
    CONSTRAINT ck_inspection_campaigns_status_times CHECK (
        (status = 'planned' AND actual_start_at IS NULL AND actual_end_at IS NULL)
        OR (status = 'in_progress' AND actual_start_at IS NOT NULL AND actual_end_at IS NULL)
        OR (status = 'completed' AND actual_start_at IS NOT NULL AND actual_end_at IS NOT NULL)
        OR status = 'cancelled'
    ),
    CONSTRAINT ck_inspection_campaigns_cancellation CHECK (
        (status = 'cancelled' AND cancellation_reason IS NOT NULL
         AND btrim(cancellation_reason) <> '')
        OR (status <> 'cancelled' AND cancellation_reason IS NULL)
    ),
    CONSTRAINT ck_inspection_campaigns_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ck_inspection_campaigns_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_inspection.acquisition_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    asset_id UUID NOT NULL,
    campaign_id UUID NOT NULL,
    session_code TEXT NOT NULL,
    operator_subject_id UUID NOT NULL,
    equipment_code TEXT NOT NULL,
    equipment_model TEXT,
    equipment_serial_number TEXT,
    acquisition_started_at TIMESTAMPTZ,
    acquisition_ended_at TIMESTAMPTZ,
    coverage_location_id UUID,
    coverage_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    quality_status TEXT NOT NULL DEFAULT 'pending',
    quality_notes TEXT,
    status TEXT NOT NULL DEFAULT 'scheduled',
    abort_reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_acquisition_sessions_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_acquisition_sessions_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_acquisition_sessions_campaign_same_asset
        FOREIGN KEY (campaign_id, organization_id, project_id, asset_id)
        REFERENCES bridgeai_inspection.inspection_campaigns
                   (id, organization_id, project_id, asset_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_acquisition_sessions_location_same_asset
        FOREIGN KEY (coverage_location_id, organization_id, project_id, asset_id)
        REFERENCES bridgeai_asset.spatial_locations (id, organization_id, project_id, asset_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_acquisition_sessions_id_scope
        UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_acquisition_sessions_id_scope_campaign_asset
        UNIQUE (id, organization_id, project_id, campaign_id, asset_id),
    CONSTRAINT uq_acquisition_sessions_campaign_code
        UNIQUE (organization_id, project_id, campaign_id, session_code),
    CONSTRAINT ck_acquisition_sessions_code_nonblank CHECK (btrim(session_code) <> ''),
    CONSTRAINT ck_acquisition_sessions_equipment_code CHECK (btrim(equipment_code) <> ''),
    CONSTRAINT ck_acquisition_sessions_equipment_model
        CHECK (equipment_model IS NULL OR btrim(equipment_model) <> ''),
    CONSTRAINT ck_acquisition_sessions_equipment_serial
        CHECK (equipment_serial_number IS NULL OR btrim(equipment_serial_number) <> ''),
    CONSTRAINT ck_acquisition_sessions_time_range CHECK (
        acquisition_ended_at IS NULL
        OR (acquisition_started_at IS NOT NULL AND acquisition_ended_at > acquisition_started_at)
    ),
    CONSTRAINT ck_acquisition_sessions_coverage_object
        CHECK (jsonb_typeof(coverage_summary) = 'object'),
    CONSTRAINT ck_acquisition_sessions_quality
        CHECK (quality_status IN ('pending', 'passed', 'warning', 'failed')),
    CONSTRAINT ck_acquisition_sessions_status
        CHECK (status IN ('scheduled', 'in_progress', 'completed', 'aborted')),
    CONSTRAINT ck_acquisition_sessions_status_times CHECK (
        (status = 'scheduled' AND acquisition_started_at IS NULL AND acquisition_ended_at IS NULL)
        OR (status = 'in_progress' AND acquisition_started_at IS NOT NULL
            AND acquisition_ended_at IS NULL)
        OR (status IN ('completed', 'aborted') AND acquisition_started_at IS NOT NULL
            AND acquisition_ended_at IS NOT NULL)
    ),
    CONSTRAINT ck_acquisition_sessions_abort_reason CHECK (
        (status = 'aborted' AND abort_reason IS NOT NULL AND btrim(abort_reason) <> '')
        OR (status <> 'aborted' AND abort_reason IS NULL)
    ),
    CONSTRAINT ck_acquisition_sessions_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ck_acquisition_sessions_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_inspection.acquisition_datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    asset_id UUID NOT NULL,
    campaign_id UUID NOT NULL,
    session_id UUID NOT NULL,
    dataset_code TEXT NOT NULL,
    import_batch_code TEXT NOT NULL,
    dataset_type TEXT NOT NULL,
    captured_from_at TIMESTAMPTZ,
    captured_to_at TIMESTAMPTZ,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    record_count BIGINT,
    size_bytes BIGINT,
    coverage_location_id UUID,
    quality_status TEXT NOT NULL DEFAULT 'pending',
    quality_score NUMERIC(7, 6),
    quality_report JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'importing',
    rejection_reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_acquisition_datasets_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_acquisition_datasets_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_acquisition_datasets_session_scope
        FOREIGN KEY (session_id, organization_id, project_id, campaign_id, asset_id)
        REFERENCES bridgeai_inspection.acquisition_sessions
                   (id, organization_id, project_id, campaign_id, asset_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_acquisition_datasets_location_same_asset
        FOREIGN KEY (coverage_location_id, organization_id, project_id, asset_id)
        REFERENCES bridgeai_asset.spatial_locations (id, organization_id, project_id, asset_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_acquisition_datasets_id_scope
        UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_acquisition_datasets_id_scope_campaign_asset
        UNIQUE (id, organization_id, project_id, campaign_id, asset_id),
    CONSTRAINT uq_acquisition_datasets_project_code
        UNIQUE (organization_id, project_id, dataset_code),
    CONSTRAINT uq_acquisition_datasets_import_batch
        UNIQUE (organization_id, project_id, import_batch_code),
    CONSTRAINT ck_acquisition_datasets_code_nonblank CHECK (btrim(dataset_code) <> ''),
    CONSTRAINT ck_acquisition_datasets_batch_nonblank CHECK (btrim(import_batch_code) <> ''),
    CONSTRAINT ck_acquisition_datasets_type CHECK (
        dataset_type IN ('image', 'video', 'point_cloud', 'sensor', 'annotation', 'mixed')
    ),
    CONSTRAINT ck_acquisition_datasets_capture_range CHECK (
        (captured_from_at IS NULL AND captured_to_at IS NULL)
        OR (captured_from_at IS NOT NULL AND captured_to_at IS NOT NULL
            AND captured_to_at >= captured_from_at)
    ),
    CONSTRAINT ck_acquisition_datasets_record_count
        CHECK (record_count IS NULL OR record_count >= 0),
    CONSTRAINT ck_acquisition_datasets_size CHECK (size_bytes IS NULL OR size_bytes >= 0),
    CONSTRAINT ck_acquisition_datasets_quality
        CHECK (quality_status IN ('pending', 'passed', 'warning', 'failed')),
    CONSTRAINT ck_acquisition_datasets_quality_score
        CHECK (quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 1)),
    CONSTRAINT ck_acquisition_datasets_quality_report
        CHECK (jsonb_typeof(quality_report) = 'object'),
    CONSTRAINT ck_acquisition_datasets_status
        CHECK (status IN ('importing', 'ready', 'quarantined', 'rejected', 'archived')),
    CONSTRAINT ck_acquisition_datasets_ready_quality CHECK (
        status <> 'ready' OR quality_status IN ('passed', 'warning')
    ),
    CONSTRAINT ck_acquisition_datasets_rejection CHECK (
        (status = 'rejected' AND rejection_reason IS NOT NULL AND btrim(rejection_reason) <> '')
        OR (status <> 'rejected' AND rejection_reason IS NULL)
    ),
    CONSTRAINT ck_acquisition_datasets_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ck_acquisition_datasets_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_inspection.dataset_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    dataset_id UUID NOT NULL,
    artifact_id UUID NOT NULL,
    artifact_version_id UUID NOT NULL,
    relation_type TEXT NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_dataset_artifacts_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_dataset_artifacts_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_dataset_artifacts_dataset_scope
        FOREIGN KEY (dataset_id, organization_id, project_id)
        REFERENCES bridgeai_inspection.acquisition_datasets (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_dataset_artifacts_artifact_scope
        FOREIGN KEY (artifact_id, organization_id, project_id)
        REFERENCES bridgeai_core.artifacts (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_dataset_artifacts_version_of_artifact
        FOREIGN KEY (artifact_version_id, organization_id, project_id, artifact_id)
        REFERENCES bridgeai_core.artifact_versions
                   (id, organization_id, project_id, artifact_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_dataset_artifacts_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_dataset_artifacts_relation
        UNIQUE (dataset_id, artifact_version_id, relation_type),
    CONSTRAINT ck_dataset_artifacts_relation CHECK (
        relation_type IN ('raw', 'calibration', 'preview', 'annotation', 'quality_report', 'derived')
    ),
    CONSTRAINT ck_dataset_artifacts_description
        CHECK (description IS NULL OR btrim(description) <> ''),
    CONSTRAINT ck_dataset_artifacts_version_positive CHECK (version > 0)
);

CREATE INDEX ix_inspection_campaigns_asset_status
    ON bridgeai_inspection.inspection_campaigns
       (organization_id, project_id, asset_id, status, planned_start_at);

CREATE INDEX ix_acquisition_sessions_campaign_time
    ON bridgeai_inspection.acquisition_sessions
       (organization_id, project_id, campaign_id, acquisition_started_at);

CREATE INDEX ix_acquisition_datasets_session_status
    ON bridgeai_inspection.acquisition_datasets
       (organization_id, project_id, session_id, status, imported_at);

CREATE INDEX ix_dataset_artifacts_artifact_version
    ON bridgeai_inspection.dataset_artifacts
       (organization_id, project_id, artifact_id, artifact_version_id);
```

## 8.13 病害实体、观测、修订与量测模型

`damage_entities` 是跨检测批次保持不变的病害身份；`damage_observations` 是特定时间的一次观测，可在空间候选关联得到确认前暂不归入稳定实体。`damage_revisions` 是观测结论的全追加修订流：`(observation_id, revision_no)` 全局唯一，前驱必须是同一观测的紧邻修订，任何旧修订都不原地改状态。

`damage_observations.current_revision_id/current_revision_no` 是唯一的默认当前指针，两列必须同时为空或同时非空。为解决观测与修订的闭环外键，先创建两张表，再以 `ALTER TABLE` 添加同观测、组织、项目的可延迟组合外键。新观测允许在首个修订落库前保持空指针，但指针一旦非空便不得清空；`pending_review` 和 `confirmed` 观测必须已指向同状态修订，且不得回退到较早状态。指针切换更新观测的 `updated_at/updated_by/version`，并由 8.19 记录审计事件。

```sql
CREATE TABLE bridgeai_inspection.damage_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    asset_id UUID NOT NULL,
    component_id UUID,
    canonical_location_id UUID,
    damage_code TEXT NOT NULL,
    damage_type_code TEXT NOT NULL,
    first_observed_at TIMESTAMPTZ NOT NULL,
    lifecycle_status TEXT NOT NULL DEFAULT 'active',
    closed_at TIMESTAMPTZ,
    closure_reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_damage_entities_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_damage_entities_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_damage_entities_asset_scope
        FOREIGN KEY (asset_id, organization_id, project_id)
        REFERENCES bridgeai_asset.assets (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_damage_entities_component_same_asset
        FOREIGN KEY (component_id, organization_id, project_id, asset_id)
        REFERENCES bridgeai_asset.components (id, organization_id, project_id, asset_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_damage_entities_location_same_asset
        FOREIGN KEY (canonical_location_id, organization_id, project_id, asset_id)
        REFERENCES bridgeai_asset.spatial_locations (id, organization_id, project_id, asset_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_damage_entities_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_damage_entities_id_scope_asset
        UNIQUE (id, organization_id, project_id, asset_id),
    CONSTRAINT uq_damage_entities_project_code
        UNIQUE (organization_id, project_id, damage_code),
    CONSTRAINT ck_damage_entities_code_nonblank CHECK (btrim(damage_code) <> ''),
    CONSTRAINT ck_damage_entities_type_nonblank CHECK (btrim(damage_type_code) <> ''),
    CONSTRAINT ck_damage_entities_status
        CHECK (lifecycle_status IN ('active', 'repaired', 'closed', 'merged')),
    CONSTRAINT ck_damage_entities_closed_state CHECK (
        (lifecycle_status IN ('closed', 'merged') AND closed_at IS NOT NULL
         AND closure_reason IS NOT NULL AND btrim(closure_reason) <> '')
        OR (lifecycle_status IN ('active', 'repaired')
            AND closed_at IS NULL AND closure_reason IS NULL)
    ),
    CONSTRAINT ck_damage_entities_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ck_damage_entities_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_inspection.model_inference_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    input_dataset_id UUID NOT NULL,
    run_code TEXT NOT NULL,
    task_type TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    model_provider TEXT NOT NULL,
    invoked_by UUID NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    runtime_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'queued',
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    output_count BIGINT,
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_model_inference_runs_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_model_inference_runs_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_model_inference_runs_input_dataset
        FOREIGN KEY (input_dataset_id, organization_id, project_id)
        REFERENCES bridgeai_inspection.acquisition_datasets (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_model_inference_runs_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_model_inference_runs_project_code
        UNIQUE (organization_id, project_id, run_code),
    CONSTRAINT ck_model_inference_runs_code_nonblank CHECK (btrim(run_code) <> ''),
    CONSTRAINT ck_model_inference_runs_task_nonblank CHECK (btrim(task_type) <> ''),
    CONSTRAINT ck_model_inference_runs_model_name CHECK (btrim(model_name) <> ''),
    CONSTRAINT ck_model_inference_runs_model_version CHECK (btrim(model_version) <> ''),
    CONSTRAINT ck_model_inference_runs_provider CHECK (btrim(model_provider) <> ''),
    CONSTRAINT ck_model_inference_runs_parameters_object CHECK (jsonb_typeof(parameters) = 'object'),
    CONSTRAINT ck_model_inference_runs_runtime_object
        CHECK (jsonb_typeof(runtime_metadata) = 'object'),
    CONSTRAINT ck_model_inference_runs_status
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    CONSTRAINT ck_model_inference_runs_times CHECK (
        (status = 'queued' AND started_at IS NULL AND finished_at IS NULL)
        OR (status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL)
        OR (status IN ('succeeded', 'failed', 'cancelled')
            AND started_at IS NOT NULL AND finished_at IS NOT NULL
            AND finished_at >= started_at)
    ),
    CONSTRAINT ck_model_inference_runs_output_count
        CHECK (output_count IS NULL OR output_count >= 0),
    CONSTRAINT ck_model_inference_runs_failure CHECK (
        (status = 'failed' AND failure_reason IS NOT NULL AND btrim(failure_reason) <> '')
        OR (status <> 'failed' AND failure_reason IS NULL)
    ),
    CONSTRAINT ck_model_inference_runs_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_inspection.damage_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    asset_id UUID NOT NULL,
    campaign_id UUID NOT NULL,
    acquisition_dataset_id UUID,
    damage_entity_id UUID,
    candidate_damage_entity_id UUID,
    previous_observation_id UUID,
    spatial_location_id UUID NOT NULL,
    observation_code TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    observation_method TEXT NOT NULL,
    association_status TEXT NOT NULL DEFAULT 'unlinked',
    association_method TEXT,
    association_rule_code TEXT,
    association_evidence TEXT,
    association_confirmed_at TIMESTAMPTZ,
    association_confirmed_by UUID,
    evolution_state TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    current_revision_id UUID,
    current_revision_no INTEGER,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_damage_observations_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_damage_observations_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_damage_observations_campaign_same_asset
        FOREIGN KEY (campaign_id, organization_id, project_id, asset_id)
        REFERENCES bridgeai_inspection.inspection_campaigns
                   (id, organization_id, project_id, asset_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_damage_observations_dataset_same_campaign_asset
        FOREIGN KEY (acquisition_dataset_id, organization_id, project_id, campaign_id, asset_id)
        REFERENCES bridgeai_inspection.acquisition_datasets
                   (id, organization_id, project_id, campaign_id, asset_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_damage_observations_entity_same_asset
        FOREIGN KEY (damage_entity_id, organization_id, project_id, asset_id)
        REFERENCES bridgeai_inspection.damage_entities
                   (id, organization_id, project_id, asset_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_damage_observations_candidate_entity_same_asset
        FOREIGN KEY (candidate_damage_entity_id, organization_id, project_id, asset_id)
        REFERENCES bridgeai_inspection.damage_entities
                   (id, organization_id, project_id, asset_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_damage_observations_previous_scope
        FOREIGN KEY (previous_observation_id, organization_id, project_id)
        REFERENCES bridgeai_inspection.damage_observations (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_damage_observations_location_same_asset
        FOREIGN KEY (spatial_location_id, organization_id, project_id, asset_id)
        REFERENCES bridgeai_asset.spatial_locations (id, organization_id, project_id, asset_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_damage_observations_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_damage_observations_project_code
        UNIQUE (organization_id, project_id, observation_code),
    CONSTRAINT ck_damage_observations_code_nonblank CHECK (btrim(observation_code) <> ''),
    CONSTRAINT ck_damage_observations_method_nonblank CHECK (btrim(observation_method) <> ''),
    CONSTRAINT ck_damage_observations_not_own_predecessor
        CHECK (previous_observation_id IS NULL OR previous_observation_id <> id),
    CONSTRAINT ck_damage_observations_association_status
        CHECK (association_status IN ('unlinked', 'candidate', 'confirmed')),
    CONSTRAINT ck_damage_observations_evolution_state CHECK (
        evolution_state IS NULL
        OR evolution_state IN ('new', 'persistent', 'expanded', 'reduced', 'repaired', 'recurred')
    ),
    CONSTRAINT ck_damage_observations_association_shape CHECK (
        (
            association_status = 'unlinked'
            AND damage_entity_id IS NULL
            AND candidate_damage_entity_id IS NULL
            AND previous_observation_id IS NULL
            AND association_method IS NULL
            AND association_rule_code IS NULL
            AND association_evidence IS NULL
            AND association_confirmed_at IS NULL
            AND association_confirmed_by IS NULL
            AND evolution_state IS NULL
        )
        OR
        (
            association_status = 'candidate'
            AND damage_entity_id IS NULL
            AND candidate_damage_entity_id IS NOT NULL
            AND association_method IN ('spatial_proximity', 'model', 'rule')
            AND association_evidence IS NOT NULL AND btrim(association_evidence) <> ''
            AND association_confirmed_at IS NULL
            AND association_confirmed_by IS NULL
            AND evolution_state IS NULL
            AND (association_method <> 'rule'
                 OR (association_rule_code IS NOT NULL AND btrim(association_rule_code) <> ''))
        )
        OR
        (
            association_status = 'confirmed'
            AND damage_entity_id IS NOT NULL
            AND candidate_damage_entity_id IS NULL
            AND association_method IN ('initial', 'manual', 'rule')
            AND association_evidence IS NOT NULL AND btrim(association_evidence) <> ''
            AND association_confirmed_at IS NOT NULL
            AND evolution_state IS NOT NULL
            AND (
                (association_method IN ('initial', 'manual')
                 AND association_confirmed_by IS NOT NULL
                 AND association_rule_code IS NULL)
                OR
                (association_method = 'rule'
                 AND association_confirmed_by IS NULL
                 AND association_rule_code IS NOT NULL
                 AND btrim(association_rule_code) <> '')
            )
            AND (
                (evolution_state = 'new' AND previous_observation_id IS NULL
                 AND association_method = 'initial')
                OR
                (evolution_state IN
                    ('persistent', 'expanded', 'reduced', 'repaired', 'recurred')
                 AND previous_observation_id IS NOT NULL
                 AND association_method IN ('manual', 'rule'))
            )
        )
    ),
    CONSTRAINT ck_damage_observations_status
        CHECK (status IN ('draft', 'pending_review', 'confirmed', 'voided')),
    CONSTRAINT ck_damage_observations_current_pair CHECK (
        (current_revision_id IS NULL AND current_revision_no IS NULL)
        OR (current_revision_id IS NOT NULL AND current_revision_no IS NOT NULL)
    ),
    CONSTRAINT ck_damage_observations_current_required CHECK (
        status IN ('draft', 'voided') OR current_revision_id IS NOT NULL
    ),
    CONSTRAINT ck_damage_observations_current_revision_positive
        CHECK (current_revision_no IS NULL OR current_revision_no > 0),
    CONSTRAINT ck_damage_observations_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ck_damage_observations_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_inspection.damage_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    observation_id UUID NOT NULL,
    revision_no INTEGER NOT NULL,
    predecessor_revision_id UUID,
    predecessor_revision_no INTEGER,
    status TEXT NOT NULL DEFAULT 'draft',
    origin_type TEXT NOT NULL,
    damage_type_code TEXT NOT NULL,
    severity_code TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    conclusion TEXT NOT NULL,
    confidence NUMERIC(7, 6) NOT NULL,
    model_inference_run_id UUID,
    confirmation_note TEXT,
    confirmed_at TIMESTAMPTZ,
    confirmed_by UUID,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    CONSTRAINT fk_damage_revisions_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_damage_revisions_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_damage_revisions_observation_scope
        FOREIGN KEY (observation_id, organization_id, project_id)
        REFERENCES bridgeai_inspection.damage_observations (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_damage_revisions_model_run_scope
        FOREIGN KEY (model_inference_run_id, organization_id, project_id)
        REFERENCES bridgeai_inspection.model_inference_runs (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_damage_revisions_observation_revision
        UNIQUE (observation_id, revision_no),
    CONSTRAINT uq_damage_revisions_id_scope_observation_revision
        UNIQUE (id, organization_id, project_id, observation_id, revision_no),
    CONSTRAINT fk_damage_revisions_predecessor_same_observation
        FOREIGN KEY (
            predecessor_revision_id, organization_id, project_id,
            observation_id, predecessor_revision_no
        )
        REFERENCES bridgeai_inspection.damage_revisions
                   (id, organization_id, project_id, observation_id, revision_no)
        DEFERRABLE INITIALLY IMMEDIATE,
    CONSTRAINT ck_damage_revisions_revision_positive CHECK (revision_no > 0),
    CONSTRAINT ck_damage_revisions_predecessor_shape CHECK (
        (revision_no = 1
         AND predecessor_revision_id IS NULL AND predecessor_revision_no IS NULL)
        OR
        (revision_no > 1
         AND predecessor_revision_id IS NOT NULL
         AND predecessor_revision_no = revision_no - 1
         AND predecessor_revision_id <> id)
    ),
    CONSTRAINT ck_damage_revisions_status
        CHECK (status IN ('draft', 'pending_review', 'confirmed', 'rejected')),
    CONSTRAINT ck_damage_revisions_origin
        CHECK (origin_type IN ('human', 'model', 'import')),
    CONSTRAINT ck_damage_revisions_origin_run_status CHECK (
        (origin_type = 'model'
         AND model_inference_run_id IS NOT NULL
         AND status IN ('draft', 'pending_review'))
        OR
        (origin_type IN ('human', 'import') AND model_inference_run_id IS NULL
         AND (origin_type <> 'import' OR status IN ('draft', 'pending_review')))
    ),
    CONSTRAINT ck_damage_revisions_type_nonblank CHECK (btrim(damage_type_code) <> ''),
    CONSTRAINT ck_damage_revisions_severity_nonblank CHECK (btrim(severity_code) <> ''),
    CONSTRAINT ck_damage_revisions_risk
        CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    CONSTRAINT ck_damage_revisions_conclusion_nonblank CHECK (btrim(conclusion) <> ''),
    CONSTRAINT ck_damage_revisions_confidence CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT ck_damage_revisions_confirmation CHECK (
        (status = 'confirmed'
         AND origin_type = 'human'
         AND confirmed_at IS NOT NULL
         AND confirmed_by IS NOT NULL)
        OR
        (status <> 'confirmed' AND confirmed_at IS NULL AND confirmed_by IS NULL
         AND confirmation_note IS NULL)
    ),
    CONSTRAINT ck_damage_revisions_high_risk_confirmation CHECK (
        status <> 'confirmed'
        OR risk_level IN ('low', 'medium')
        OR (confirmation_note IS NOT NULL AND btrim(confirmation_note) <> '')
    ),
    CONSTRAINT ck_damage_revisions_metadata_object CHECK (jsonb_typeof(metadata) = 'object')
);

ALTER TABLE bridgeai_inspection.damage_observations
    ADD CONSTRAINT fk_damage_observations_current_revision
    FOREIGN KEY (
        current_revision_id, organization_id, project_id, id, current_revision_no
    )
    REFERENCES bridgeai_inspection.damage_revisions
               (id, organization_id, project_id, observation_id, revision_no)
    ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE bridgeai_inspection.damage_measurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    observation_id UUID NOT NULL,
    revision_id UUID NOT NULL,
    revision_no INTEGER NOT NULL,
    metric_code TEXT NOT NULL,
    metric_value NUMERIC NOT NULL,
    unit_code TEXT NOT NULL,
    method_code TEXT NOT NULL,
    uncertainty_value NUMERIC NOT NULL,
    uncertainty_unit_code TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    source_dataset_id UUID,
    model_inference_run_id UUID,
    measured_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    CONSTRAINT fk_damage_measurements_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_damage_measurements_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_damage_measurements_revision_scope
        FOREIGN KEY (revision_id, organization_id, project_id, observation_id, revision_no)
        REFERENCES bridgeai_inspection.damage_revisions
                   (id, organization_id, project_id, observation_id, revision_no)
        ON DELETE RESTRICT,
    CONSTRAINT fk_damage_measurements_source_dataset
        FOREIGN KEY (source_dataset_id, organization_id, project_id)
        REFERENCES bridgeai_inspection.acquisition_datasets (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_damage_measurements_model_run
        FOREIGN KEY (model_inference_run_id, organization_id, project_id)
        REFERENCES bridgeai_inspection.model_inference_runs (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_damage_measurements_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_damage_measurements_revision_metric_method
        UNIQUE (revision_id, metric_code, method_code),
    CONSTRAINT ck_damage_measurements_revision_positive CHECK (revision_no > 0),
    CONSTRAINT ck_damage_measurements_metric_nonblank CHECK (btrim(metric_code) <> ''),
    CONSTRAINT ck_damage_measurements_unit_nonblank CHECK (btrim(unit_code) <> ''),
    CONSTRAINT ck_damage_measurements_method_nonblank CHECK (btrim(method_code) <> ''),
    CONSTRAINT ck_damage_measurements_uncertainty CHECK (uncertainty_value >= 0),
    CONSTRAINT ck_damage_measurements_uncertainty_unit
        CHECK (btrim(uncertainty_unit_code) <> ''),
    CONSTRAINT ck_damage_measurements_source_type
        CHECK (source_type IN ('manual', 'instrument', 'model', 'derived')),
    CONSTRAINT ck_damage_measurements_source_reference
        CHECK (btrim(source_reference) <> ''),
    CONSTRAINT ck_damage_measurements_source_shape CHECK (
        (source_type = 'model' AND model_inference_run_id IS NOT NULL)
        OR (source_type <> 'model' AND model_inference_run_id IS NULL)
    )
);

CREATE TABLE bridgeai_inspection.damage_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    observation_id UUID NOT NULL,
    revision_id UUID NOT NULL,
    revision_no INTEGER NOT NULL,
    artifact_id UUID NOT NULL,
    artifact_version_id UUID NOT NULL,
    evidence_role TEXT NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    evidence_locator JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_summary TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    CONSTRAINT fk_damage_evidence_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_damage_evidence_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_damage_evidence_revision_scope
        FOREIGN KEY (revision_id, organization_id, project_id, observation_id, revision_no)
        REFERENCES bridgeai_inspection.damage_revisions
                   (id, organization_id, project_id, observation_id, revision_no)
        ON DELETE RESTRICT,
    CONSTRAINT fk_damage_evidence_artifact_scope
        FOREIGN KEY (artifact_id, organization_id, project_id)
        REFERENCES bridgeai_core.artifacts (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_damage_evidence_version_of_artifact
        FOREIGN KEY (artifact_version_id, organization_id, project_id, artifact_id)
        REFERENCES bridgeai_core.artifact_versions
                   (id, organization_id, project_id, artifact_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_damage_evidence_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_damage_evidence_revision_artifact_role
        UNIQUE (revision_id, artifact_version_id, evidence_role),
    CONSTRAINT ck_damage_evidence_revision_positive CHECK (revision_no > 0),
    CONSTRAINT ck_damage_evidence_role CHECK (
        evidence_role IN (
            'source_media', 'annotation', 'sensor_record',
            'model_output', 'quality_report', 'review_record'
        )
    ),
    CONSTRAINT ck_damage_evidence_locator_object
        CHECK (jsonb_typeof(evidence_locator) = 'object'),
    CONSTRAINT ck_damage_evidence_summary_nonblank CHECK (btrim(evidence_summary) <> '')
);

CREATE OR REPLACE FUNCTION bridgeai_inspection.reject_damage_revision_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'damage revision %/% is append-only; create a successor revision instead',
        OLD.observation_id, OLD.revision_no
        USING ERRCODE = 'object_not_in_prerequisite_state';
END;
$$;

CREATE TRIGGER trg_damage_revisions_append_only
BEFORE UPDATE OR DELETE ON bridgeai_inspection.damage_revisions
FOR EACH ROW
EXECUTE FUNCTION bridgeai_inspection.reject_damage_revision_mutation();

CREATE OR REPLACE FUNCTION bridgeai_inspection.reject_damage_revision_child_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        '% rows are append-only; create evidence or measurements on a successor revision',
        TG_TABLE_NAME
        USING ERRCODE = 'object_not_in_prerequisite_state';
END;
$$;

CREATE TRIGGER trg_damage_measurements_append_only
BEFORE UPDATE OR DELETE ON bridgeai_inspection.damage_measurements
FOR EACH ROW
EXECUTE FUNCTION bridgeai_inspection.reject_damage_revision_child_mutation();

CREATE TRIGGER trg_damage_evidence_append_only
BEFORE UPDATE OR DELETE ON bridgeai_inspection.damage_evidence
FOR EACH ROW
EXECUTE FUNCTION bridgeai_inspection.reject_damage_revision_child_mutation();

CREATE OR REPLACE FUNCTION bridgeai_inspection.validate_damage_observation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    current_status TEXT;
    current_predecessor_id UUID;
    current_predecessor_no INTEGER;
    previous_entity_id UUID;
    previous_evolution_state TEXT;
    previous_observed_at TIMESTAMPTZ;
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.association_status = 'confirmed' THEN
            RAISE EXCEPTION
                'confirmed damage observation history cannot be deleted';
        END IF;
        RETURN OLD;
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF OLD.current_revision_id IS NOT NULL
           AND NEW.current_revision_id IS NULL THEN
            RAISE EXCEPTION
                'a non-null current revision pointer cannot be cleared';
        END IF;

        IF (OLD.status = 'pending_review'
            AND NEW.status NOT IN ('pending_review', 'confirmed', 'voided'))
           OR (OLD.status = 'confirmed'
               AND NEW.status NOT IN ('confirmed', 'voided'))
           OR (OLD.status = 'voided' AND NEW.status <> 'voided') THEN
            RAISE EXCEPTION
                'damage observation status cannot transition from % to %',
                OLD.status, NEW.status;
        END IF;

        IF OLD.association_status = 'confirmed'
           AND ROW(
               NEW.organization_id, NEW.project_id, NEW.asset_id,
               NEW.campaign_id, NEW.acquisition_dataset_id,
               NEW.damage_entity_id, NEW.previous_observation_id,
               NEW.spatial_location_id, NEW.observed_at, NEW.observation_method,
               NEW.association_status, NEW.association_method,
               NEW.association_rule_code, NEW.association_evidence,
               NEW.association_confirmed_at, NEW.association_confirmed_by,
               NEW.evolution_state
           ) IS DISTINCT FROM ROW(
               OLD.organization_id, OLD.project_id, OLD.asset_id,
               OLD.campaign_id, OLD.acquisition_dataset_id,
               OLD.damage_entity_id, OLD.previous_observation_id,
               OLD.spatial_location_id, OLD.observed_at, OLD.observation_method,
               OLD.association_status, OLD.association_method,
               OLD.association_rule_code, OLD.association_evidence,
               OLD.association_confirmed_at, OLD.association_confirmed_by,
               OLD.evolution_state
           ) THEN
            RAISE EXCEPTION
                'confirmed damage observation history is immutable';
        END IF;
    END IF;

    IF NEW.association_status = 'confirmed' THEN
        -- 同一病害实体是跨期关联的共同串行化点。
        -- 锁后才读取首次确认和前驱，避免并发创建冲突历史。
        PERFORM 1
        FROM bridgeai_inspection.damage_entities AS de
        WHERE de.id = NEW.damage_entity_id
          AND de.organization_id = NEW.organization_id
          AND de.project_id = NEW.project_id
          AND de.asset_id = NEW.asset_id
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'damage entity does not exist in observation scope'
                USING ERRCODE = 'foreign_key_violation';
        END IF;

        IF NEW.evolution_state = 'new'
           AND EXISTS (
               SELECT 1
               FROM bridgeai_inspection.damage_observations AS first_observation
               WHERE first_observation.organization_id = NEW.organization_id
                 AND first_observation.project_id = NEW.project_id
                 AND first_observation.damage_entity_id = NEW.damage_entity_id
                 AND first_observation.association_status = 'confirmed'
                 AND first_observation.evolution_state = 'new'
                 AND first_observation.id <> NEW.id
           ) THEN
            RAISE EXCEPTION
                'damage entity % already has a confirmed new observation',
                NEW.damage_entity_id
                USING ERRCODE = 'unique_violation';
        END IF;
    END IF;

    IF NEW.current_revision_id IS NOT NULL THEN
        SELECT dr.status, dr.predecessor_revision_id, dr.predecessor_revision_no
        INTO current_status, current_predecessor_id, current_predecessor_no
        FROM bridgeai_inspection.damage_revisions AS dr
        WHERE dr.id = NEW.current_revision_id
          AND dr.organization_id = NEW.organization_id
          AND dr.project_id = NEW.project_id
          AND dr.observation_id = NEW.id
          AND dr.revision_no = NEW.current_revision_no;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'current revision does not exist in observation scope'
                USING ERRCODE = 'foreign_key_violation';
        END IF;

        IF NEW.status = 'draft' AND current_status <> 'draft' THEN
            RAISE EXCEPTION 'draft observation must point to a draft revision';
        ELSIF NEW.status = 'pending_review' AND current_status <> 'pending_review' THEN
            RAISE EXCEPTION 'pending_review observation must point to a pending_review revision';
        ELSIF NEW.status = 'confirmed' AND current_status <> 'confirmed' THEN
            RAISE EXCEPTION 'confirmed observation must point to a confirmed revision';
        END IF;

        IF TG_OP = 'UPDATE'
           AND ROW(NEW.current_revision_id, NEW.current_revision_no)
               IS DISTINCT FROM ROW(OLD.current_revision_id, OLD.current_revision_no) THEN
            IF OLD.current_revision_id IS NULL AND NEW.current_revision_no <> 1 THEN
                RAISE EXCEPTION 'first current revision must be revision 1';
            ELSIF OLD.current_revision_id IS NOT NULL
                  AND (
                      current_predecessor_id IS DISTINCT FROM OLD.current_revision_id
                      OR current_predecessor_no IS DISTINCT FROM OLD.current_revision_no
                  ) THEN
                RAISE EXCEPTION
                    'current revision must advance to the direct successor of the old current revision';
            END IF;
        END IF;
    END IF;

    IF NEW.association_status = 'confirmed'
       AND NEW.previous_observation_id IS NOT NULL THEN
        SELECT previous.damage_entity_id, previous.evolution_state, previous.observed_at
        INTO previous_entity_id, previous_evolution_state, previous_observed_at
        FROM bridgeai_inspection.damage_observations AS previous
        WHERE previous.id = NEW.previous_observation_id
          AND previous.organization_id = NEW.organization_id
          AND previous.project_id = NEW.project_id;

        IF NOT FOUND OR previous_entity_id IS DISTINCT FROM NEW.damage_entity_id THEN
            RAISE EXCEPTION 'confirmed evolution predecessor must belong to the same damage entity';
        END IF;

        IF previous_observed_at >= NEW.observed_at THEN
            RAISE EXCEPTION 'evolution predecessor must be observed earlier';
        END IF;

        IF NEW.evolution_state = 'recurred'
           AND previous_evolution_state <> 'repaired' THEN
            RAISE EXCEPTION 'recurred evolution must follow a repaired observation';
        END IF;
    END IF;

    IF TG_OP = 'UPDATE'
       AND ROW(
           NEW.current_revision_id, NEW.current_revision_no, NEW.status,
           NEW.association_status, NEW.damage_entity_id,
           NEW.candidate_damage_entity_id, NEW.previous_observation_id,
           NEW.evolution_state
       ) IS DISTINCT FROM ROW(
           OLD.current_revision_id, OLD.current_revision_no, OLD.status,
           OLD.association_status, OLD.damage_entity_id,
           OLD.candidate_damage_entity_id, OLD.previous_observation_id,
           OLD.evolution_state
       ) THEN
        IF NEW.version <> OLD.version + 1 OR NEW.updated_at <= OLD.updated_at THEN
            RAISE EXCEPTION
                'current/association transition must increment version and advance updated_at';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_damage_observations_validate
BEFORE INSERT OR UPDATE OR DELETE ON bridgeai_inspection.damage_observations
FOR EACH ROW
EXECUTE FUNCTION bridgeai_inspection.validate_damage_observation();

CREATE UNIQUE INDEX uq_damage_observations_one_confirmed_new
    ON bridgeai_inspection.damage_observations
       (organization_id, project_id, damage_entity_id)
    WHERE association_status = 'confirmed' AND evolution_state = 'new';

CREATE INDEX ix_damage_entities_component_status
    ON bridgeai_inspection.damage_entities
       (organization_id, project_id, asset_id, component_id, lifecycle_status);

CREATE INDEX ix_model_inference_runs_dataset_status
    ON bridgeai_inspection.model_inference_runs
       (organization_id, project_id, input_dataset_id, status, created_at);

CREATE INDEX ix_damage_revisions_observation_status
    ON bridgeai_inspection.damage_revisions
       (organization_id, project_id, observation_id, status, revision_no DESC);

CREATE INDEX ix_damage_evidence_artifact_version
    ON bridgeai_inspection.damage_evidence
       (organization_id, project_id, artifact_id, artifact_version_id);
```

`confirmed_by` 与全局 `created_by/updated_by` 一样保存稳定审计主体 UUID，不单独绑定 `users`，以免丢失服务主体或历史身份语义。模型修订必须强关联 `model_inference_runs`，数据库 `CHECK` 保证其只能以 `draft/pending_review` 入库；人工对模型结果的采纳是新建后继 `human + confirmed` 修订，不是把模型修订原地改为已确认。高风险和极高风险修订还必须保存非空确认意见。

一旦观测的跨期关联进入 `association_status = confirmed`，它的组织、项目、资产、批次、数据集、空间位置、观测时间/方法、稳定病害、前驱、演变状态、确认方法/证据/主体全部冻结；修正必须新建观测或后续修订，不得原地重写已被后继演变引用的历史。

`damage_measurements` 的每条量测都显式保存 metric/value/unit/method/uncertainty/source；模型来源还必须指向模型运行。`damage_evidence` 同时强关联 Artifact 和属于该 Artifact 的确定版本，不接受对象键、URL 或多态 ID 替代外键。修订、量测和证据均有数据库追加控制；错误只能在新修订中纠正。

## 8.14 多期病害关联与历史演变

跨期演变状态只有以下六种，且它们是“本次观测相对前驱观测”的判定，不是直接覆盖稳定病害实体。

| `evolution_state` | 语义 | 强制来源 |
|---|---|---|
| `new` | 首次确认的病害 | 无前驱，`association_method = initial`，保存人工确认主体和证据摘要 |
| `persistent` | 与前期同一病害且主要量测无显著变化 | 同实体早于本次的前驱，人工确认或受控规则编码，以及证据摘要 |
| `expanded` | 尺寸、面积、体积或严重度扩大 | 同实体前驱，当前/前期量测或人工评定，以及阈值规则或确认主体 |
| `reduced` | 量测范围缩小但仍可观测 | 同 `expanded`，必须保留可复算的当前/前期量测或人工证据 |
| `repaired` | 经处置后本期已不再呈现或已达修复标准 | 同实体前驱、处置/复查证据和人工确认或受控规则 |
| `recurred` | 已判定修复后再次出现 | 前驱必须是同实体的 `repaired` 观测，并保留人工确认或受控规则证据 |

`association_status = candidate` 时只能写 `candidate_damage_entity_id`，不得写最终 `damage_entity_id/evolution_state`。空间距离、模型相似度或单一规则命中都只能生成这种候选；空间近邻方法被 `CHECK` 排除在最终确认方法之外。候选转为 `confirmed` 时，只能保留人工确认（`association_confirmed_by`）或受控规则（`association_rule_code`）其一，并必须写入证据摘要。触发器额外验证前驱的实体、时间顺序和 `recurred <- repaired` 关系。

建立任何 confirmed 跨期关联前先锁定共同 `damage_entities` 行，然后检查前驱和首次确认。每个稳定病害实体只能有一条 `association_status = confirmed AND evolution_state = new` 观测；部分唯一索引与锁后触发器共同阻止顺序和并发重复。

空间候选查询必须先限定组织、项目和资产，再在项目适用投影坐标系内计算米制距离。查询结果只可写入 `candidate_damage_entity_id + association_status = candidate + association_method = spatial_proximity`，禁止直接更新稳定实体关联。

当前确认修订及量测趋势按下列范式查询。所有关联都带完整项目作用域，可通过可空参数按资产、构件或稳定病害实体继续收窄。

```sql
WITH current_confirmed AS (
    SELECT
        de.id AS damage_entity_id,
        de.asset_id,
        de.component_id,
        o.id AS observation_id,
        o.observed_at,
        o.evolution_state,
        dr.id AS revision_id,
        dr.revision_no,
        dr.damage_type_code,
        dr.severity_code,
        dr.risk_level,
        dr.confidence
    FROM bridgeai_inspection.damage_entities AS de
    JOIN bridgeai_inspection.damage_observations AS o
      ON o.damage_entity_id = de.id
     AND o.organization_id = de.organization_id
     AND o.project_id = de.project_id
     AND o.asset_id = de.asset_id
    JOIN bridgeai_inspection.damage_revisions AS dr
      ON dr.id = o.current_revision_id
     AND dr.organization_id = o.organization_id
     AND dr.project_id = o.project_id
     AND dr.observation_id = o.id
     AND dr.revision_no = o.current_revision_no
    WHERE de.organization_id = :organization_id
      AND de.project_id = :project_id
      AND de.asset_id = :asset_id
      AND (:component_id IS NULL OR de.component_id = :component_id)
      AND (:damage_entity_id IS NULL OR de.id = :damage_entity_id)
      AND o.association_status = 'confirmed'
      AND o.status = 'confirmed'
      AND dr.status = 'confirmed'
), measurement_series AS (
    SELECT
        cc.*,
        dm.metric_code,
        dm.metric_value,
        dm.unit_code,
        dm.method_code,
        dm.uncertainty_value,
        dm.uncertainty_unit_code,
        dm.source_type,
        LAG(dm.metric_value) OVER (
            PARTITION BY cc.damage_entity_id, dm.metric_code, dm.unit_code, dm.method_code
            ORDER BY cc.observed_at, cc.observation_id
        ) AS previous_metric_value
    FROM current_confirmed AS cc
    LEFT JOIN bridgeai_inspection.damage_measurements AS dm
      ON dm.revision_id = cc.revision_id
     AND dm.observation_id = cc.observation_id
     AND dm.revision_no = cc.revision_no
     AND dm.organization_id = :organization_id
     AND dm.project_id = :project_id
)
SELECT
    measurement_series.*,
    metric_value - previous_metric_value AS metric_delta
FROM measurement_series
ORDER BY damage_entity_id, observed_at, metric_code, method_code;
```

该查询只读观测的显式当前指针，因此被后继修订替代的旧版仍可通过主键引用和追溯，但不会意外进入默认趋势。

```sql
CREATE INDEX ix_damage_observations_entity_time
    ON bridgeai_inspection.damage_observations
       (organization_id, project_id, asset_id, damage_entity_id, observed_at)
    WHERE association_status = 'confirmed';

CREATE INDEX ix_damage_observations_candidates
    ON bridgeai_inspection.damage_observations
       (organization_id, project_id, asset_id, candidate_damage_entity_id, observed_at)
    WHERE association_status = 'candidate';

CREATE INDEX ix_damage_measurements_trend
    ON bridgeai_inspection.damage_measurements
       (organization_id, project_id, observation_id, metric_code, unit_code, method_code);
```

## 8.15 Workflow 数据模型兼容收敛

第五章已经定义并可能已经部署 `workflow_tasks`、`workflow_runs`、`workflow_events`、`workflow_node_executions` 和 `workflow_reviews`。本节给出它们在第八章的**唯一最终物理形态**：新环境按下列 DDL 建表；既有环境必须按 8.15.2 的兼容迁移原位升级或采用有数据核对的影子分区切换，禁止通过删除旧表、建立空表来“完成迁移”。

`task_id` 是业务任务，`run_id` 是一次执行，`thread_id` 是 LangGraph 恢复线程，三者没有值相等约束。任务上的 `thread_id` 只表示初始/默认线程；每次实际运行仍在 `workflow_runs.thread_id` 登记，因此同一任务可以有多个 run 和多个 thread。LangGraph Checkpointer 的 `checkpoints`、`checkpoint_writes`、`checkpoint_blobs` 等表继续由所采用的框架版本和官方迁移管理；BridgeAI 迁移不得复制、改名、加业务外键或把其中 State 当作领域事实。

### 8.15.1 最终物理表

```sql
CREATE TABLE bridgeai_workflow.workflow_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    thread_id TEXT NOT NULL,
    asset_id UUID,
    acquisition_dataset_id UUID,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    current_node TEXT,
    progress NUMERIC(5, 2) NOT NULL DEFAULT 0,
    state_version BIGINT NOT NULL DEFAULT 1,
    selected_model_version TEXT,
    idempotency_key TEXT NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_code TEXT,
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_workflow_tasks_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_workflow_tasks_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_workflow_tasks_asset_scope
        FOREIGN KEY (asset_id, organization_id, project_id)
        REFERENCES bridgeai_asset.assets (id, organization_id, project_id) ON DELETE RESTRICT,
    CONSTRAINT fk_workflow_tasks_dataset_scope
        FOREIGN KEY (acquisition_dataset_id, organization_id, project_id)
        REFERENCES bridgeai_inspection.acquisition_datasets (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_workflow_tasks_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_workflow_tasks_idempotency
        UNIQUE (organization_id, project_id, idempotency_key),
    CONSTRAINT ck_workflow_tasks_thread_nonblank CHECK (btrim(thread_id) <> ''),
    CONSTRAINT ck_workflow_tasks_type_nonblank CHECK (btrim(task_type) <> ''),
    CONSTRAINT ck_workflow_tasks_status CHECK (
        status IN ('pending', 'queued', 'running', 'waiting_review',
                   'succeeded', 'failed', 'cancelled')
    ),
    CONSTRAINT ck_workflow_tasks_progress CHECK (progress BETWEEN 0 AND 100),
    CONSTRAINT ck_workflow_tasks_state_version CHECK (state_version > 0),
    CONSTRAINT ck_workflow_tasks_idempotency_nonblank CHECK (btrim(idempotency_key) <> ''),
    CONSTRAINT ck_workflow_tasks_time_order CHECK (
        (started_at IS NULL OR started_at >= requested_at)
        AND (completed_at IS NULL OR (started_at IS NOT NULL AND completed_at >= started_at))
    ),
    CONSTRAINT ck_workflow_tasks_terminal_time CHECK (
        (status IN ('succeeded', 'failed', 'cancelled') AND completed_at IS NOT NULL)
        OR (status NOT IN ('succeeded', 'failed', 'cancelled') AND completed_at IS NULL)
    ),
    CONSTRAINT ck_workflow_tasks_error CHECK (
        status <> 'failed' OR (error_code IS NOT NULL AND btrim(error_code) <> '')
    ),
    CONSTRAINT ck_workflow_tasks_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ck_workflow_tasks_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_workflow.workflow_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    task_id UUID NOT NULL,
    thread_id TEXT NOT NULL,
    run_number INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    start_node TEXT,
    end_node TEXT,
    trigger_type TEXT NOT NULL,
    triggered_by UUID,
    idempotency_key TEXT NOT NULL,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    duration_ms BIGINT,
    error_code TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_workflow_runs_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_workflow_runs_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_workflow_runs_task_scope
        FOREIGN KEY (task_id, organization_id, project_id)
        REFERENCES bridgeai_workflow.workflow_tasks (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_workflow_runs_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_workflow_runs_id_scope_task
        UNIQUE (id, organization_id, project_id, task_id),
    CONSTRAINT uq_workflow_runs_id_scope_task_thread
        UNIQUE (id, organization_id, project_id, task_id, thread_id),
    CONSTRAINT uq_workflow_runs_number
        UNIQUE (organization_id, project_id, task_id, run_number),
    CONSTRAINT uq_workflow_runs_idempotency
        UNIQUE (organization_id, project_id, task_id, idempotency_key),
    CONSTRAINT ck_workflow_runs_thread_nonblank CHECK (btrim(thread_id) <> ''),
    CONSTRAINT ck_workflow_runs_number_positive CHECK (run_number > 0),
    CONSTRAINT ck_workflow_runs_status CHECK (
        status IN ('queued', 'running', 'waiting_review', 'succeeded',
                   'failed', 'cancelled')
    ),
    CONSTRAINT ck_workflow_runs_trigger_nonblank CHECK (btrim(trigger_type) <> ''),
    CONSTRAINT ck_workflow_runs_idempotency_nonblank CHECK (btrim(idempotency_key) <> ''),
    CONSTRAINT ck_workflow_runs_config_object CHECK (jsonb_typeof(config) = 'object'),
    CONSTRAINT ck_workflow_runs_time_order CHECK (
        finished_at IS NULL OR (started_at IS NOT NULL AND finished_at >= started_at)
    ),
    CONSTRAINT ck_workflow_runs_terminal_time CHECK (
        (status IN ('succeeded', 'failed', 'cancelled') AND finished_at IS NOT NULL)
        OR (status NOT IN ('succeeded', 'failed', 'cancelled') AND finished_at IS NULL)
    ),
    CONSTRAINT ck_workflow_runs_duration CHECK (
        duration_ms IS NULL OR (duration_ms >= 0 AND finished_at IS NOT NULL)
    ),
    CONSTRAINT ck_workflow_runs_error CHECK (
        status <> 'failed' OR (error_code IS NOT NULL AND btrim(error_code) <> '')
    ),
    CONSTRAINT ck_workflow_runs_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_workflow.workflow_events (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY,
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    task_id UUID NOT NULL,
    run_id UUID,
    trace_id TEXT NOT NULL,
    producer_event_key TEXT NOT NULL,
    event_type TEXT NOT NULL,
    node_name TEXT,
    event_level TEXT NOT NULL DEFAULT 'info',
    actor_subject_id UUID,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, occurred_at),
    CONSTRAINT fk_workflow_events_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_workflow_events_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_workflow_events_task_scope
        FOREIGN KEY (task_id, organization_id, project_id)
        REFERENCES bridgeai_workflow.workflow_tasks (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_workflow_events_run_same_task
        FOREIGN KEY (run_id, organization_id, project_id, task_id)
        REFERENCES bridgeai_workflow.workflow_runs (id, organization_id, project_id, task_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_workflow_events_producer_key_partition_local
        UNIQUE (organization_id, project_id, producer_event_key, occurred_at),
    CONSTRAINT ck_workflow_events_trace_nonblank CHECK (btrim(trace_id) <> ''),
    CONSTRAINT ck_workflow_events_key_nonblank CHECK (btrim(producer_event_key) <> ''),
    CONSTRAINT ck_workflow_events_type_nonblank CHECK (btrim(event_type) <> ''),
    CONSTRAINT ck_workflow_events_level
        CHECK (event_level IN ('debug', 'info', 'warning', 'error', 'critical')),
    CONSTRAINT ck_workflow_events_payload_object CHECK (jsonb_typeof(payload) = 'object'),
    CONSTRAINT ck_workflow_events_recording_order CHECK (recorded_at >= occurred_at)
) PARTITION BY RANGE (occurred_at);

CREATE TABLE bridgeai_workflow.workflow_events_default
    PARTITION OF bridgeai_workflow.workflow_events DEFAULT;

CREATE INDEX ix_workflow_events_global_producer_key
    ON bridgeai_workflow.workflow_events
       (organization_id, project_id, producer_event_key);

CREATE OR REPLACE FUNCTION bridgeai_workflow.reject_duplicate_producer_event_key()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            NEW.organization_id::text || E'\\x1f'
            || NEW.project_id::text || E'\\x1f'
            || NEW.producer_event_key,
            0
        )
    );

    IF EXISTS (
        SELECT 1
        FROM bridgeai_workflow.workflow_events AS existing
        WHERE existing.organization_id = NEW.organization_id
          AND existing.project_id = NEW.project_id
          AND existing.producer_event_key = NEW.producer_event_key
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '23505',
            CONSTRAINT = 'uq_workflow_events_producer_key_global',
            MESSAGE = format(
                'duplicate producer_event_key %s in organization/project scope',
                NEW.producer_event_key
            );
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_workflow_events_global_producer_key
BEFORE INSERT ON bridgeai_workflow.workflow_events
FOR EACH ROW EXECUTE FUNCTION bridgeai_workflow.reject_duplicate_producer_event_key();

CREATE OR REPLACE FUNCTION bridgeai_workflow.reject_workflow_event_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'workflow events are append-only; append a correction event instead';
END;
$$;

CREATE TRIGGER trg_workflow_events_append_only
BEFORE UPDATE OR DELETE ON bridgeai_workflow.workflow_events
FOR EACH ROW EXECUTE FUNCTION bridgeai_workflow.reject_workflow_event_mutation();

CREATE TABLE bridgeai_workflow.workflow_node_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    task_id UUID NOT NULL,
    run_id UUID NOT NULL,
    node_name TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'pending',
    input_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key TEXT NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    duration_ms BIGINT,
    error_code TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_workflow_node_executions_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_workflow_node_executions_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_workflow_node_executions_task_scope
        FOREIGN KEY (task_id, organization_id, project_id)
        REFERENCES bridgeai_workflow.workflow_tasks (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_workflow_node_executions_run_same_task
        FOREIGN KEY (run_id, organization_id, project_id, task_id)
        REFERENCES bridgeai_workflow.workflow_runs (id, organization_id, project_id, task_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_workflow_node_executions_id_scope
        UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_workflow_node_executions_id_scope_task_run
        UNIQUE (id, organization_id, project_id, task_id, run_id),
    CONSTRAINT uq_workflow_node_executions_attempt
        UNIQUE (organization_id, project_id, run_id, node_name, attempt),
    CONSTRAINT uq_workflow_node_executions_idempotency
        UNIQUE (organization_id, project_id, idempotency_key),
    CONSTRAINT ck_workflow_node_executions_node_nonblank CHECK (btrim(node_name) <> ''),
    CONSTRAINT ck_workflow_node_executions_attempt_positive CHECK (attempt > 0),
    CONSTRAINT ck_workflow_node_executions_status CHECK (
        status IN ('pending', 'running', 'waiting_review', 'succeeded',
                   'failed', 'skipped', 'cancelled')
    ),
    CONSTRAINT ck_workflow_node_executions_input_object
        CHECK (jsonb_typeof(input_summary) = 'object'),
    CONSTRAINT ck_workflow_node_executions_output_object
        CHECK (jsonb_typeof(output_summary) = 'object'),
    CONSTRAINT ck_workflow_node_executions_idempotency_nonblank
        CHECK (btrim(idempotency_key) <> ''),
    CONSTRAINT ck_workflow_node_executions_time_order CHECK (
        finished_at IS NULL OR (started_at IS NOT NULL AND finished_at >= started_at)
    ),
    CONSTRAINT ck_workflow_node_executions_terminal_time CHECK (
        (status IN ('succeeded', 'failed', 'skipped', 'cancelled') AND finished_at IS NOT NULL)
        OR (status NOT IN ('succeeded', 'failed', 'skipped', 'cancelled') AND finished_at IS NULL)
    ),
    CONSTRAINT ck_workflow_node_executions_duration CHECK (
        duration_ms IS NULL OR (duration_ms >= 0 AND finished_at IS NOT NULL)
    ),
    CONSTRAINT ck_workflow_node_executions_error CHECK (
        status <> 'failed' OR (error_code IS NOT NULL AND btrim(error_code) <> '')
    ),
    CONSTRAINT ck_workflow_node_executions_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_workflow.workflow_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    task_id UUID NOT NULL,
    run_id UUID,
    node_execution_id UUID,
    review_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    priority TEXT NOT NULL DEFAULT 'normal',
    title TEXT NOT NULL,
    description TEXT,
    input_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    suggested_result JSONB,
    final_result JSONB,
    reviewer_subject_id UUID,
    decision_idempotency_key TEXT,
    reviewed_at TIMESTAMPTZ,
    due_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_workflow_reviews_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_workflow_reviews_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_workflow_reviews_task_scope
        FOREIGN KEY (task_id, organization_id, project_id)
        REFERENCES bridgeai_workflow.workflow_tasks (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_workflow_reviews_run_same_task
        FOREIGN KEY (run_id, organization_id, project_id, task_id)
        REFERENCES bridgeai_workflow.workflow_runs (id, organization_id, project_id, task_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_workflow_reviews_node_execution_scope
        FOREIGN KEY (
            node_execution_id, organization_id, project_id, task_id, run_id
        ) REFERENCES bridgeai_workflow.workflow_node_executions
          (id, organization_id, project_id, task_id, run_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_workflow_reviews_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_workflow_reviews_id_organization UNIQUE (id, organization_id),
    CONSTRAINT uq_workflow_reviews_decision_idempotency
        UNIQUE (organization_id, project_id, decision_idempotency_key),
    CONSTRAINT ck_workflow_reviews_type_nonblank CHECK (btrim(review_type) <> ''),
    CONSTRAINT ck_workflow_reviews_status CHECK (
        status IN ('pending', 'claimed', 'approved', 'rejected', 'cancelled', 'expired')
    ),
    CONSTRAINT ck_workflow_reviews_priority
        CHECK (priority IN ('low', 'normal', 'high', 'critical')),
    CONSTRAINT ck_workflow_reviews_title_nonblank CHECK (btrim(title) <> ''),
    CONSTRAINT ck_workflow_reviews_input_object CHECK (jsonb_typeof(input_data) = 'object'),
    CONSTRAINT ck_workflow_reviews_suggested_object CHECK (
        suggested_result IS NULL OR jsonb_typeof(suggested_result) = 'object'
    ),
    CONSTRAINT ck_workflow_reviews_final_object CHECK (
        final_result IS NULL OR jsonb_typeof(final_result) = 'object'
    ),
    CONSTRAINT ck_workflow_reviews_decision_shape CHECK (
        (status IN ('approved', 'rejected')
         AND reviewer_subject_id IS NOT NULL
         AND reviewed_at IS NOT NULL
         AND final_result IS NOT NULL
         AND decision_idempotency_key IS NOT NULL
         AND btrim(decision_idempotency_key) <> '')
        OR (status NOT IN ('approved', 'rejected') AND reviewed_at IS NULL)
    ),
    CONSTRAINT ck_workflow_reviews_node_requires_run CHECK (
        node_execution_id IS NULL OR run_id IS NOT NULL
    ),
    CONSTRAINT ck_workflow_reviews_due_time CHECK (due_at IS NULL OR due_at >= created_at),
    CONSTRAINT ck_workflow_reviews_version_positive CHECK (version > 0)
);

CREATE INDEX ix_workflow_tasks_scope_status
    ON bridgeai_workflow.workflow_tasks (organization_id, project_id, status, updated_at);
CREATE INDEX ix_workflow_runs_task_status
    ON bridgeai_workflow.workflow_runs
       (organization_id, project_id, task_id, status, run_number DESC);
CREATE INDEX ix_workflow_events_task_time
    ON bridgeai_workflow.workflow_events
       (organization_id, project_id, task_id, occurred_at DESC);
CREATE INDEX ix_workflow_events_trace_time
    ON bridgeai_workflow.workflow_events
       (organization_id, project_id, trace_id, occurred_at DESC);
CREATE INDEX ix_workflow_node_executions_run_status
    ON bridgeai_workflow.workflow_node_executions
       (organization_id, project_id, run_id, status, node_name);
CREATE INDEX ix_workflow_reviews_pending
    ON bridgeai_workflow.workflow_reviews
       (organization_id, project_id, priority, due_at)
    WHERE status IN ('pending', 'claimed');
```

`created_by`、`updated_by`、`triggered_by`、`actor_subject_id` 和 `reviewer_subject_id` 都是稳定审计主体 UUID，可能指人员或服务主体，因此不伪造指向 `users` 的单表外键；其身份类型和当时权限快照由 8.19 审计域解释。事件以 `occurred_at` 为范围分区键；生产迁移应预建月分区并保留 DEFAULT 分区作为短时故障护栏，监控不得容忍 DEFAULT 分区长期积压。`producer_event_key` 是生产者对同一逻辑事件跨重试、跨进程和跨时间保持不变的稳定键；分区内唯一约束只作局部护栏，BEFORE INSERT 触发器以事务级 advisory lock 串行化同组织/项目/键的并发写入，再通过父表索引跨所有分区查重，因此不同 `occurred_at` 也不能重复。事件整行追加写，禁止 UPDATE/DELETE；纠错必须追加带关联键的新事件，不能事后改写 scope、稳定键、分区时间或语义载荷。

### 8.15.2 第五章兼容迁移矩阵

共同顺序固定为：**新增可空列/宽松检查 → 回填并隔离异常 → 建唯一索引 → 外键 `NOT VALID` → `VALIDATE CONSTRAINT` → `SET NOT NULL` 与最终 `CHECK` → 启用并强制 RLS**。组合外键统一按“被引用主键在前，随后 `organization_id, project_id`，再加父实体键”的顺序；不得把列顺序互换后依赖偶然存在的另一条唯一约束。

| 旧表 | 旧字段 → 最终字段 | 回填与默认 | 约束启用顺序 | 验证查询 |
|---|---|---|---|---|
| `workflow_tasks` | `id → id`；`thread_id → thread_id`（移除全局唯一）；`project_id → project_id`；`bridge_id → asset_id`；`input_batch_id → acquisition_dataset_id`；其余业务字段同名；新增 `organization_id/idempotency_key/requested_at/updated_by/version` | `organization_id` 从 `projects.organization_id`；`asset_id` 先按旧 bridge UUID 匹配 `assets.id` 且 `asset_type='bridge'`；批次映射到同项目 `acquisition_datasets.id`；`idempotency_key='legacy:task:'||id`；`requested_at=created_at`；`updated_by=created_by`；终态缺失 `started_at/completed_at` 时以不早于 `created_at/updated_at` 的值回填 | 先检查孤儿项目、资产和数据集；再建作用域唯一键与幂等唯一键；项目/资产/数据集外键先 `NOT VALID` 后验证；规范化状态后启用 CHECK；最后非空、RLS | `SELECT t.id FROM bridgeai_workflow.workflow_tasks t LEFT JOIN bridgeai_core.projects p ON (p.id,p.organization_id)=(t.project_id,t.organization_id) WHERE p.id IS NULL OR t.organization_id IS NULL OR t.idempotency_key IS NULL;` 应为 0 行 |
| `workflow_runs` | `id/task_id/run_number/status/start_node/end_node/trigger_type/triggered_by/config` 同名；新增 `organization_id/project_id/thread_id/idempotency_key/error_*/created_*/updated_*/version` | 边界从父 `workflow_tasks`；历史 run 无独立 thread 时只在迁移时复制父任务 `thread_id`，之后禁止自动同步；`idempotency_key='legacy:run:'||id`；`created_at=COALESCE(started_at, task.created_at)`；`created_by/updated_by=COALESCE(triggered_by, task.created_by)` | 先验证 `(task_id,organization_id,project_id)`；再建 run 作用域唯一键和 `(task_id,run_number)` 范围唯一；外键 `NOT VALID`/验证；最后状态、时间、非空和 RLS | `SELECT r.id FROM bridgeai_workflow.workflow_runs r LEFT JOIN bridgeai_workflow.workflow_tasks t ON (t.id,t.organization_id,t.project_id)=(r.task_id,r.organization_id,r.project_id) WHERE t.id IS NULL OR r.thread_id IS NULL;` 应为 0 行 |
| `workflow_events` | `id → id` 保留 BIGINT；`created_at → occurred_at`；新增 `recorded_at/organization_id/project_id/producer_event_key/actor_subject_id`；其余同名 | 边界从任务；`run_id` 存在时必须属于同一任务；`producer_event_key='legacy:event:'||id`；`event_level=lower(event_level)`；`recorded_at=GREATEST(created_at,迁移写入时间)` | 普通旧表先完成边界和 run 校验；再创建按 `occurred_at` 分区的影子表，逐分区 `INSERT ... SELECT` 保留全部 id，核对总数/每月数/min-max/hash 后在短事务切换名称；外键 `NOT VALID`/验证后启用 RLS。影子表不是空表替代，任何核对不一致即回滚切换 | `SELECT e.id,e.occurred_at FROM bridgeai_workflow.workflow_events e LEFT JOIN bridgeai_workflow.workflow_tasks t ON (t.id,t.organization_id,t.project_id)=(e.task_id,e.organization_id,e.project_id) LEFT JOIN bridgeai_workflow.workflow_runs r ON (r.id,r.organization_id,r.project_id,r.task_id)=(e.run_id,e.organization_id,e.project_id,e.task_id) WHERE t.id IS NULL OR (e.run_id IS NOT NULL AND r.id IS NULL);` 应为 0 行；切换前后另比 `count(*),min(id),max(id),min(occurred_at),max(occurred_at)` |
| `workflow_node_executions` | 原字段同名；新增 `organization_id/project_id/created_by/created_at/updated_by/updated_at/version` | 边界从 task，并以 run 反查交叉确认；审计主体优先取 run 的 `triggered_by/created_by`，否则取 task；`created_at=COALESCE(started_at,task.created_at)`；旧全局幂等键保留，但最终唯一范围改为组织/项目 | 先查 task/run 不一致；建 `(id,organization_id,project_id)` 和 run+node+attempt 唯一键；task/run 外键 `NOT VALID`/验证；再状态、时间、非空与 RLS | `SELECT n.id FROM bridgeai_workflow.workflow_node_executions n LEFT JOIN bridgeai_workflow.workflow_runs r ON (r.id,r.organization_id,r.project_id,r.task_id)=(n.run_id,n.organization_id,n.project_id,n.task_id) WHERE r.id IS NULL OR n.idempotency_key IS NULL;` 应为 0 行 |
| `workflow_reviews` | `reviewer_id → reviewer_subject_id`；原字段同名；新增 `organization_id/project_id/run_id/node_execution_id/decision_idempotency_key/updated_at/updated_by/version` | 边界从 task；能从事件/节点确定的历史 review 回填 run/node，否则保持可空；终态决策键为 `'legacy:review:'||id`；`updated_by=COALESCE(reviewer_id,created_by)`，`updated_at=COALESCE(reviewed_at,created_at)`；历史 `input_data` 的 SQL NULL 先改为 `{}` | 先确认可选 run/node 均与 task 同范围；建作用域唯一和决策幂等唯一；FK `NOT VALID`/验证；最后决策形态 CHECK、非空与 RLS | `SELECT v.id FROM bridgeai_workflow.workflow_reviews v LEFT JOIN bridgeai_workflow.workflow_tasks t ON (t.id,t.organization_id,t.project_id)=(v.task_id,v.organization_id,v.project_id) LEFT JOIN bridgeai_workflow.workflow_runs r ON (r.id,r.organization_id,r.project_id,r.task_id)=(v.run_id,v.organization_id,v.project_id,v.task_id) WHERE t.id IS NULL OR (v.run_id IS NOT NULL AND r.id IS NULL) OR (v.status IN ('approved','rejected') AND (v.reviewer_subject_id IS NULL OR v.final_result IS NULL));` 应为 0 行 |

旧状态必须通过版本化映射先收敛，典型映射为 `in_progress → running`、`awaiting_human → waiting_review`、`completed → succeeded`、`error → failed`、事件级别 `INFO/WARN/ERROR → info/warning/error`。迁移脚本遇到映射表之外的值必须停止并输出待裁决清单，不得用默认状态吞掉语义。

外键在线启用范式如下；其余组合外键使用同一顺序：

```sql
ALTER TABLE bridgeai_workflow.workflow_runs
    ADD CONSTRAINT fk_workflow_runs_task_scope
    FOREIGN KEY (task_id, organization_id, project_id)
    REFERENCES bridgeai_workflow.workflow_tasks (id, organization_id, project_id)
    ON DELETE RESTRICT NOT VALID;

ALTER TABLE bridgeai_workflow.workflow_runs
    VALIDATE CONSTRAINT fk_workflow_runs_task_scope;

ALTER TABLE bridgeai_workflow.workflow_runs
    ALTER COLUMN organization_id SET NOT NULL,
    ALTER COLUMN project_id SET NOT NULL,
    ALTER COLUMN thread_id SET NOT NULL,
    ALTER COLUMN idempotency_key SET NOT NULL;
```

五张表完成异常清零和约束验证后才启用 RLS。项目级策略基线如下；迁移/表所有者不得授予应用角色 `BYPASSRLS`，并使用 `FORCE ROW LEVEL SECURITY` 防止表所有者误走普通服务连接。审计主体的角色、成员关系和操作授权仍由服务层验证，RLS 只承担组织/项目的数据库纵深隔离。

```sql
DO $workflow_rls$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'workflow_tasks', 'workflow_runs', 'workflow_events',
        'workflow_node_executions', 'workflow_reviews'
    ]
    LOOP
        EXECUTE format(
            'ALTER TABLE bridgeai_workflow.%I ENABLE ROW LEVEL SECURITY', table_name
        );
        EXECUTE format(
            'ALTER TABLE bridgeai_workflow.%I FORCE ROW LEVEL SECURITY', table_name
        );
        EXECUTE format(
            'CREATE POLICY %I ON bridgeai_workflow.%I USING (
                 organization_id = NULLIF(current_setting(''app.organization_id'', true), '''')::uuid
                 AND project_id = NULLIF(current_setting(''app.project_id'', true), '''')::uuid
             ) WITH CHECK (
                 organization_id = NULLIF(current_setting(''app.organization_id'', true), '''')::uuid
                 AND project_id = NULLIF(current_setting(''app.project_id'', true), '''')::uuid
             )',
            'pl_' || table_name || '_scope', table_name
        );
    END LOOP;
END
$workflow_rls$;
```

## 8.16 RAG 知识库数据模型

RAG 的权威链为 `knowledge_sources → documents → document_versions → chunks`，发布决定写入追加式 `publications`，对外使用的证据快照写入 `citations`，Qdrant 投影结果只登记在 `index_sync_jobs`。本节将第六章概念名 `knowledge_documents/knowledge_document_versions/knowledge_chunks/knowledge_publications` 收敛为 `bridgeai_knowledge.documents/document_versions/chunks/publications`；不得再建立带 `knowledge_` 表名前缀的第二套物理表。

### 8.16.1 来源、文档、不可变版本与结构化 Chunk

```sql
CREATE TABLE bridgeai_knowledge.knowledge_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    source_code TEXT NOT NULL,
    source_type TEXT NOT NULL,
    name TEXT NOT NULL,
    issuing_organization TEXT,
    authority_level TEXT NOT NULL,
    source_artifact_id UUID NOT NULL,
    source_artifact_version_id UUID NOT NULL,
    origin_uri TEXT,
    sensitivity_level TEXT NOT NULL DEFAULT 'internal',
    status TEXT NOT NULL DEFAULT 'registered',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_knowledge_sources_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_knowledge_sources_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_knowledge_sources_artifact_scope
        FOREIGN KEY (source_artifact_id, organization_id, project_id)
        REFERENCES bridgeai_core.artifacts (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_knowledge_sources_artifact_version
        FOREIGN KEY (
            source_artifact_version_id, organization_id, project_id, source_artifact_id
        ) REFERENCES bridgeai_core.artifact_versions
          (id, organization_id, project_id, artifact_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_knowledge_sources_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_knowledge_sources_project_code
        UNIQUE (organization_id, project_id, source_code),
    CONSTRAINT ck_knowledge_sources_code_nonblank CHECK (btrim(source_code) <> ''),
    CONSTRAINT ck_knowledge_sources_type CHECK (
        source_type IN (
            'official_standard', 'official_notice', 'project_contract', 'project_plan',
            'inspection_report', 'review_record', 'case_record', 'domain_manual',
            'equipment_manual', 'model_card'
        )
    ),
    CONSTRAINT ck_knowledge_sources_name_nonblank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_knowledge_sources_authority CHECK (authority_level IN ('A', 'B', 'C', 'D')),
    CONSTRAINT ck_knowledge_sources_origin_uri CHECK (
        origin_uri IS NULL OR btrim(origin_uri) <> ''
    ),
    CONSTRAINT ck_knowledge_sources_sensitivity CHECK (
        sensitivity_level IN ('public', 'internal', 'confidential', 'restricted')
    ),
    CONSTRAINT ck_knowledge_sources_status CHECK (
        status IN ('registered', 'active', 'suspended', 'revoked', 'archived')
    ),
    CONSTRAINT ck_knowledge_sources_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ck_knowledge_sources_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_knowledge.documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    knowledge_source_id UUID NOT NULL,
    document_code TEXT NOT NULL,
    title TEXT NOT NULL,
    document_number TEXT,
    knowledge_domain TEXT NOT NULL,
    asset_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    component_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    disease_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    region_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_documents_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_documents_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_documents_source_scope
        FOREIGN KEY (knowledge_source_id, organization_id, project_id)
        REFERENCES bridgeai_knowledge.knowledge_sources (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_documents_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_documents_id_scope_source
        UNIQUE (id, organization_id, project_id, knowledge_source_id),
    CONSTRAINT uq_documents_project_code
        UNIQUE (organization_id, project_id, document_code),
    CONSTRAINT ck_documents_code_nonblank CHECK (btrim(document_code) <> ''),
    CONSTRAINT ck_documents_title_nonblank CHECK (btrim(title) <> ''),
    CONSTRAINT ck_documents_number_nonblank CHECK (
        document_number IS NULL OR btrim(document_number) <> ''
    ),
    CONSTRAINT ck_documents_domain_nonblank CHECK (btrim(knowledge_domain) <> ''),
    CONSTRAINT ck_documents_asset_types_array CHECK (jsonb_typeof(asset_types) = 'array'),
    CONSTRAINT ck_documents_component_types_array CHECK (jsonb_typeof(component_types) = 'array'),
    CONSTRAINT ck_documents_disease_types_array CHECK (jsonb_typeof(disease_types) = 'array'),
    CONSTRAINT ck_documents_region_codes_array CHECK (jsonb_typeof(region_codes) = 'array'),
    CONSTRAINT ck_documents_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT ck_documents_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_knowledge.document_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    document_id UUID NOT NULL,
    version_no INTEGER NOT NULL,
    edition_label TEXT,
    status TEXT NOT NULL DEFAULT 'registered',
    content_sha256 TEXT NOT NULL,
    source_artifact_id UUID NOT NULL,
    source_artifact_version_id UUID NOT NULL,
    supersedes_version_id UUID,
    parser_name TEXT,
    parser_version TEXT,
    chunking_policy_version TEXT,
    embedding_contract_version TEXT,
    processing_contract_locked_at TIMESTAMPTZ,
    effective_from DATE,
    effective_to DATE,
    published_at TIMESTAMPTZ,
    superseded_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_document_versions_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_document_versions_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_document_versions_document_scope
        FOREIGN KEY (document_id, organization_id, project_id)
        REFERENCES bridgeai_knowledge.documents (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_document_versions_artifact_scope
        FOREIGN KEY (source_artifact_id, organization_id, project_id)
        REFERENCES bridgeai_core.artifacts (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_document_versions_artifact_version
        FOREIGN KEY (
            source_artifact_version_id, organization_id, project_id, source_artifact_id
        ) REFERENCES bridgeai_core.artifact_versions
          (id, organization_id, project_id, artifact_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_document_versions_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_document_versions_id_scope_document
        UNIQUE (id, organization_id, project_id, document_id),
    CONSTRAINT uq_document_versions_evidence_identity UNIQUE (
        id, organization_id, project_id, document_id,
        source_artifact_id, source_artifact_version_id
    ),
    CONSTRAINT uq_document_versions_number
        UNIQUE (organization_id, project_id, document_id, version_no),
    CONSTRAINT fk_document_versions_supersedes_same_document
        FOREIGN KEY (supersedes_version_id, organization_id, project_id, document_id)
        REFERENCES bridgeai_knowledge.document_versions
                   (id, organization_id, project_id, document_id)
        ON DELETE RESTRICT,
    CONSTRAINT ck_document_versions_number_positive CHECK (version_no > 0),
    CONSTRAINT ck_document_versions_status CHECK (
        status IN (
            'registered', 'parsing', 'validating', 'indexing', 'review_pending',
            'published', 'rejected', 'failed', 'superseded', 'archived'
        )
    ),
    CONSTRAINT ck_document_versions_sha256 CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_document_versions_effective_range CHECK (
        effective_to IS NULL OR (effective_from IS NOT NULL AND effective_to >= effective_from)
    ),
    CONSTRAINT ck_document_versions_lifecycle_times CHECK (
        (status <> 'published' OR published_at IS NOT NULL)
        AND (status <> 'superseded' OR (published_at IS NOT NULL AND superseded_at IS NOT NULL))
        AND (status <> 'archived' OR archived_at IS NOT NULL)
    ),
    CONSTRAINT ck_document_versions_processing_lock CHECK (
        status = 'registered'
        OR (
            processing_contract_locked_at IS NOT NULL
            AND parser_name IS NOT NULL AND btrim(parser_name) <> ''
            AND parser_version IS NOT NULL AND btrim(parser_version) <> ''
            AND chunking_policy_version IS NOT NULL AND btrim(chunking_policy_version) <> ''
            AND embedding_contract_version IS NOT NULL
            AND btrim(embedding_contract_version) <> ''
        )
    ),
    CONSTRAINT ck_document_versions_no_self_supersede CHECK (supersedes_version_id IS DISTINCT FROM id),
    CONSTRAINT ck_document_versions_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_knowledge.chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    document_id UUID NOT NULL,
    document_version_id UUID NOT NULL,
    ordinal_no INTEGER NOT NULL,
    chunk_type TEXT NOT NULL,
    content_text TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    token_count INTEGER,
    page_start INTEGER,
    page_end INTEGER,
    section_path JSONB NOT NULL DEFAULT '[]'::jsonb,
    clause_number TEXT,
    table_number TEXT,
    figure_number TEXT,
    char_start BIGINT,
    char_end BIGINT,
    source_bbox JSONB,
    parent_chunk_id UUID,
    previous_chunk_id UUID,
    next_chunk_id UUID,
    parser_version TEXT NOT NULL,
    chunking_policy_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    CONSTRAINT fk_chunks_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_chunks_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_chunks_document_version_scope
        FOREIGN KEY (document_version_id, organization_id, project_id, document_id)
        REFERENCES bridgeai_knowledge.document_versions
                   (id, organization_id, project_id, document_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_chunks_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_chunks_id_scope_version
        UNIQUE (id, organization_id, project_id, document_version_id),
    CONSTRAINT uq_chunks_ordinal
        UNIQUE (organization_id, project_id, document_version_id, ordinal_no),
    CONSTRAINT fk_chunks_parent_same_version
        FOREIGN KEY (parent_chunk_id, organization_id, project_id, document_version_id)
        REFERENCES bridgeai_knowledge.chunks
                   (id, organization_id, project_id, document_version_id)
        ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_chunks_previous_same_version
        FOREIGN KEY (previous_chunk_id, organization_id, project_id, document_version_id)
        REFERENCES bridgeai_knowledge.chunks
                   (id, organization_id, project_id, document_version_id)
        ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_chunks_next_same_version
        FOREIGN KEY (next_chunk_id, organization_id, project_id, document_version_id)
        REFERENCES bridgeai_knowledge.chunks
                   (id, organization_id, project_id, document_version_id)
        ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT ck_chunks_ordinal_nonnegative CHECK (ordinal_no >= 0),
    CONSTRAINT ck_chunks_type CHECK (
        chunk_type IN (
            'clause', 'paragraph', 'list', 'table', 'figure_caption',
            'case_summary', 'model_card'
        )
    ),
    CONSTRAINT ck_chunks_content_nonblank CHECK (btrim(content_text) <> ''),
    CONSTRAINT ck_chunks_sha256 CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_chunks_token_count CHECK (token_count IS NULL OR token_count >= 0),
    CONSTRAINT ck_chunks_page_range CHECK (
        page_start IS NULL OR (page_start > 0 AND page_end IS NOT NULL AND page_end >= page_start)
    ),
    CONSTRAINT ck_chunks_section_path_array CHECK (jsonb_typeof(section_path) = 'array'),
    CONSTRAINT ck_chunks_char_range CHECK (
        (char_start IS NULL AND char_end IS NULL)
        OR (char_start IS NOT NULL AND char_start >= 0 AND char_end > char_start)
    ),
    CONSTRAINT ck_chunks_bbox_object CHECK (
        source_bbox IS NULL OR jsonb_typeof(source_bbox) = 'object'
    ),
    CONSTRAINT ck_chunks_locator_present CHECK (
        page_start IS NOT NULL OR clause_number IS NOT NULL OR char_start IS NOT NULL
    ),
    CONSTRAINT ck_chunks_no_self_links CHECK (
        parent_chunk_id IS DISTINCT FROM id
        AND previous_chunk_id IS DISTINCT FROM id
        AND next_chunk_id IS DISTINCT FROM id
    ),
    CONSTRAINT ck_chunks_parser_nonblank CHECK (btrim(parser_version) <> ''),
    CONSTRAINT ck_chunks_policy_nonblank CHECK (btrim(chunking_policy_version) <> '')
);
```

`content_text` 保存发布时实际引用的原文片段，`content_sha256` 防止静默变化；页码、章节路径、条款号、字符区间和可选页面坐标使片段可以回到原文。Qdrant 的 collection、point_id、index_version 不进入 `chunks`，避免把派生索引身份误当成知识身份。

### 8.16.2 追加发布、引用快照与索引同步

```sql
CREATE TABLE bridgeai_knowledge.publications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    document_id UUID NOT NULL,
    document_version_id UUID NOT NULL,
    publication_no INTEGER NOT NULL,
    publication_action TEXT NOT NULL,
    superseded_by_version_id UUID,
    review_reference TEXT NOT NULL,
    release_policy_version TEXT NOT NULL,
    reason TEXT,
    published_at TIMESTAMPTZ NOT NULL,
    published_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    CONSTRAINT fk_publications_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_publications_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_publications_document_version_scope
        FOREIGN KEY (document_version_id, organization_id, project_id, document_id)
        REFERENCES bridgeai_knowledge.document_versions
                   (id, organization_id, project_id, document_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_publications_successor_scope
        FOREIGN KEY (superseded_by_version_id, organization_id, project_id, document_id)
        REFERENCES bridgeai_knowledge.document_versions
                   (id, organization_id, project_id, document_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_publications_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_publications_number
        UNIQUE (organization_id, project_id, document_id, publication_no),
    CONSTRAINT ck_publications_number_positive CHECK (publication_no > 0),
    CONSTRAINT ck_publications_action
        CHECK (publication_action IN ('publish', 'supersede', 'archive', 'withdraw')),
    CONSTRAINT ck_publications_supersede_shape CHECK (
        (publication_action = 'supersede' AND superseded_by_version_id IS NOT NULL)
        OR (publication_action <> 'supersede' AND superseded_by_version_id IS NULL)
    ),
    CONSTRAINT ck_publications_review_nonblank CHECK (btrim(review_reference) <> ''),
    CONSTRAINT ck_publications_policy_nonblank CHECK (btrim(release_policy_version) <> ''),
    CONSTRAINT ck_publications_reason CHECK (
        publication_action = 'publish' OR (reason IS NOT NULL AND btrim(reason) <> '')
    )
);

CREATE UNIQUE INDEX uq_publications_one_publish_per_version
    ON bridgeai_knowledge.publications
       (organization_id, project_id, document_version_id)
    WHERE publication_action = 'publish';

CREATE TABLE bridgeai_knowledge.citations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    document_id UUID NOT NULL,
    document_version_id UUID NOT NULL,
    chunk_id UUID NOT NULL,
    source_artifact_id UUID NOT NULL,
    source_artifact_version_id UUID NOT NULL,
    cited_by_type TEXT NOT NULL,
    cited_by_id TEXT NOT NULL,
    page_number INTEGER,
    section_path JSONB NOT NULL DEFAULT '[]'::jsonb,
    clause_number TEXT,
    table_number TEXT,
    figure_number TEXT,
    source_span JSONB NOT NULL DEFAULT '{}'::jsonb,
    excerpt TEXT NOT NULL,
    excerpt_sha256 TEXT NOT NULL,
    applicability TEXT NOT NULL,
    applicability_reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    CONSTRAINT fk_citations_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_citations_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_citations_chunk_version_scope
        FOREIGN KEY (chunk_id, organization_id, project_id, document_version_id)
        REFERENCES bridgeai_knowledge.chunks
                   (id, organization_id, project_id, document_version_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_citations_document_version_scope
        FOREIGN KEY (document_version_id, organization_id, project_id, document_id)
        REFERENCES bridgeai_knowledge.document_versions
                   (id, organization_id, project_id, document_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_citations_exact_version_artifact FOREIGN KEY (
        document_version_id, organization_id, project_id, document_id,
        source_artifact_id, source_artifact_version_id
    ) REFERENCES bridgeai_knowledge.document_versions (
        id, organization_id, project_id, document_id,
        source_artifact_id, source_artifact_version_id
    ) ON DELETE RESTRICT,
    CONSTRAINT fk_citations_artifact_scope
        FOREIGN KEY (source_artifact_id, organization_id, project_id)
        REFERENCES bridgeai_core.artifacts (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_citations_artifact_version
        FOREIGN KEY (
            source_artifact_version_id, organization_id, project_id, source_artifact_id
        ) REFERENCES bridgeai_core.artifact_versions
          (id, organization_id, project_id, artifact_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_citations_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT ck_citations_consumer_type CHECK (
        cited_by_type IN (
            'workflow_event', 'context_manifest', 'report_revision', 'external_export'
        )
    ),
    CONSTRAINT ck_citations_consumer_id_nonblank CHECK (btrim(cited_by_id) <> ''),
    CONSTRAINT ck_citations_page_positive CHECK (page_number IS NULL OR page_number > 0),
    CONSTRAINT ck_citations_section_path_array CHECK (jsonb_typeof(section_path) = 'array'),
    CONSTRAINT ck_citations_source_span_object CHECK (jsonb_typeof(source_span) = 'object'),
    CONSTRAINT ck_citations_locator_present CHECK (
        page_number IS NOT NULL OR clause_number IS NOT NULL
        OR jsonb_typeof(source_span) = 'object' AND source_span <> '{}'::jsonb
    ),
    CONSTRAINT ck_citations_excerpt_nonblank CHECK (btrim(excerpt) <> ''),
    CONSTRAINT ck_citations_excerpt_sha256 CHECK (excerpt_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_citations_applicability CHECK (
        applicability IN ('applicable', 'partially_applicable', 'not_confirmed', 'not_applicable')
    ),
    CONSTRAINT ck_citations_reason_nonblank CHECK (btrim(applicability_reason) <> '')
);

CREATE TABLE bridgeai_knowledge.knowledge_releases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    release_code TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    item_count INTEGER NOT NULL DEFAULT 0,
    production_collection TEXT,
    qdrant_index_version TEXT,
    acl_snapshot JSONB,
    acl_snapshot_sha256 TEXT,
    release_manifest JSONB,
    release_manifest_sha256 TEXT,
    published_at TIMESTAMPTZ,
    published_by UUID,
    withdrawn_at TIMESTAMPTZ,
    withdrawal_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_knowledge_releases_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_knowledge_releases_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT uq_knowledge_releases_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_knowledge_releases_project_code
        UNIQUE (organization_id, project_id, release_code),
    CONSTRAINT ck_knowledge_releases_code_nonblank CHECK (btrim(release_code) <> ''),
    CONSTRAINT ck_knowledge_releases_status
        CHECK (status IN ('draft', 'published', 'withdrawn')),
    CONSTRAINT ck_knowledge_releases_item_count CHECK (item_count >= 0),
    CONSTRAINT ck_knowledge_releases_published_shape CHECK (
        status = 'draft'
        OR (
            item_count > 0
            AND production_collection LIKE 'bridgeai_knowledge_prod_%'
            AND qdrant_index_version IS NOT NULL AND btrim(qdrant_index_version) <> ''
            AND acl_snapshot IS NOT NULL AND jsonb_typeof(acl_snapshot) = 'object'
            AND acl_snapshot_sha256 ~ '^[0-9a-f]{64}$'
            AND release_manifest IS NOT NULL AND jsonb_typeof(release_manifest) = 'array'
            AND release_manifest_sha256 ~ '^[0-9a-f]{64}$'
            AND published_at IS NOT NULL AND published_by IS NOT NULL
        )
    ),
    CONSTRAINT ck_knowledge_releases_withdrawn_shape CHECK (
        status <> 'withdrawn'
        OR (withdrawn_at IS NOT NULL AND withdrawal_reason IS NOT NULL
            AND btrim(withdrawal_reason) <> '')
    ),
    CONSTRAINT ck_knowledge_releases_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_knowledge.publication_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    release_id UUID NOT NULL,
    publication_id UUID NOT NULL,
    document_id UUID NOT NULL,
    document_version_id UUID NOT NULL,
    ordinal_no INTEGER NOT NULL,
    chunk_count INTEGER NOT NULL,
    chunk_manifest JSONB NOT NULL,
    chunk_manifest_sha256 TEXT NOT NULL,
    qdrant_collection TEXT NOT NULL,
    qdrant_index_version TEXT NOT NULL,
    acl_snapshot JSONB NOT NULL,
    acl_snapshot_sha256 TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    CONSTRAINT fk_publication_items_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_publication_items_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_publication_items_release_scope
        FOREIGN KEY (release_id, organization_id, project_id)
        REFERENCES bridgeai_knowledge.knowledge_releases (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_publication_items_publication_scope
        FOREIGN KEY (publication_id, organization_id, project_id)
        REFERENCES bridgeai_knowledge.publications (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_publication_items_document_version_scope
        FOREIGN KEY (document_version_id, organization_id, project_id, document_id)
        REFERENCES bridgeai_knowledge.document_versions
                   (id, organization_id, project_id, document_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_publication_items_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_publication_items_release_ordinal
        UNIQUE (organization_id, project_id, release_id, ordinal_no),
    CONSTRAINT uq_publication_items_release_version
        UNIQUE (organization_id, project_id, release_id, document_version_id),
    CONSTRAINT ck_publication_items_ordinal_nonnegative CHECK (ordinal_no >= 0),
    CONSTRAINT ck_publication_items_chunk_count_positive CHECK (chunk_count > 0),
    CONSTRAINT ck_publication_items_chunk_manifest_array
        CHECK (jsonb_typeof(chunk_manifest) = 'array'),
    CONSTRAINT ck_publication_items_chunk_manifest_sha256
        CHECK (chunk_manifest_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_publication_items_collection
        CHECK (qdrant_collection LIKE 'bridgeai_knowledge_prod_%'),
    CONSTRAINT ck_publication_items_index_version_nonblank
        CHECK (btrim(qdrant_index_version) <> ''),
    CONSTRAINT ck_publication_items_acl_object CHECK (jsonb_typeof(acl_snapshot) = 'object'),
    CONSTRAINT ck_publication_items_acl_sha256
        CHECK (acl_snapshot_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE bridgeai_knowledge.index_sync_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    chunk_id UUID,
    release_id UUID,
    sync_phase TEXT NOT NULL,
    operation TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    idempotency_key TEXT NOT NULL,
    qdrant_collection TEXT NOT NULL,
    qdrant_point_id TEXT,
    qdrant_index_version TEXT NOT NULL,
    source_revision_sha256 TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_index_sync_jobs_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_index_sync_jobs_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_index_sync_jobs_chunk_scope
        FOREIGN KEY (chunk_id, organization_id, project_id)
        REFERENCES bridgeai_knowledge.chunks (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_index_sync_jobs_release_scope
        FOREIGN KEY (release_id, organization_id, project_id)
        REFERENCES bridgeai_knowledge.knowledge_releases (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_index_sync_jobs_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_index_sync_jobs_idempotency
        UNIQUE (organization_id, project_id, idempotency_key),
    CONSTRAINT ck_index_sync_jobs_phase CHECK (sync_phase IN ('build', 'activate')),
    CONSTRAINT ck_index_sync_jobs_target_shape CHECK (
        (sync_phase = 'build'
         AND operation IN ('upsert', 'delete_point', 'verify_point')
         AND chunk_id IS NOT NULL AND release_id IS NULL)
        OR (sync_phase = 'activate'
            AND operation IN ('publish_collection', 'withdraw_collection', 'verify_collection')
            AND release_id IS NOT NULL AND chunk_id IS NULL)
    ),
    CONSTRAINT ck_index_sync_jobs_status CHECK (
        status IN ('queued', 'running', 'succeeded', 'failed', 'dead_letter', 'cancelled')
    ),
    CONSTRAINT ck_index_sync_jobs_key_nonblank CHECK (btrim(idempotency_key) <> ''),
    CONSTRAINT ck_index_sync_jobs_collection_namespace CHECK (
        (sync_phase = 'build' AND qdrant_collection LIKE 'bridgeai_knowledge_staging_%')
        OR (sync_phase = 'activate' AND qdrant_collection LIKE 'bridgeai_knowledge_prod_%')
    ),
    CONSTRAINT ck_index_sync_jobs_point_shape CHECK (
        operation IN ('publish_collection', 'withdraw_collection', 'verify_collection')
        OR qdrant_point_id IS NOT NULL
    ),
    CONSTRAINT ck_index_sync_jobs_index_version_nonblank
        CHECK (btrim(qdrant_index_version) <> ''),
    CONSTRAINT ck_index_sync_jobs_source_sha256
        CHECK (source_revision_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_index_sync_jobs_attempt_nonnegative CHECK (attempt_count >= 0),
    CONSTRAINT ck_index_sync_jobs_completion CHECK (
        (status = 'succeeded' AND completed_at IS NOT NULL AND last_error IS NULL)
        OR status <> 'succeeded'
    ),
    CONSTRAINT ck_index_sync_jobs_version_positive CHECK (version > 0)
);

CREATE INDEX ix_document_versions_scope_status
    ON bridgeai_knowledge.document_versions
       (organization_id, project_id, status, effective_from, effective_to);
CREATE INDEX ix_chunks_version_locator
    ON bridgeai_knowledge.chunks
       (organization_id, project_id, document_version_id, page_start, ordinal_no);
CREATE INDEX ix_citations_consumer
    ON bridgeai_knowledge.citations
       (organization_id, project_id, cited_by_type, cited_by_id);
CREATE INDEX ix_publication_items_release
    ON bridgeai_knowledge.publication_items
       (organization_id, project_id, release_id, ordinal_no);
CREATE INDEX ix_index_sync_jobs_claim
    ON bridgeai_knowledge.index_sync_jobs
       (organization_id, project_id, status, available_at)
    WHERE status IN ('queued', 'failed');
```

`cited_by_type + cited_by_id` 是受控的多态消费方引用，不伪装成数据库外键：允许类型只有上表 CHECK 中四种，写入入口统一为 Citation Service；该服务在同一请求中按类型解析目标表、校验组织/项目可见性并保存目标稳定 ID，删除/撤签事件再由一致性作业复核引用。强业务关系位于引用的证据一侧，因此 chunk、文档版本和 Artifact 版本全部使用可验证组合外键。`workflow_events.id` 是 BIGINT 且带分区键，报告修订与外部导出又有不同键形状，强行把这些消费方塞入一个 UUID 外键只会产生无法验证的伪关系。

`knowledge_releases` 是一次生产发布的聚合根，`publication_items` 冻结该 release 的文档版本集合、逐版本 Chunk ID/哈希清单、生产 collection/index version 和 ACL 快照；历史查询以 `release_id` 读取这些 item，不重新计算“当前发布版本”。`publications` 仍是单文档状态动作证据，不能单独替代集合快照。

`qdrant_collection`、`qdrant_point_id` 和 `qdrant_index_version` 明确是派生同步字段：只能由索引投影器在创建 `index_sync_jobs` 时登记，不得由 Qdrant 回写权威版本或发布快照。job 入队后 organization/project、chunk/release target、phase/operation、幂等键、collection/point/index version 与来源哈希均不可改写；worker 只能推进执行状态、次数和错误等运行字段。`sync_phase='build'` 只允许 `indexing/review_pending` 文档写入 `bridgeai_knowledge_staging_*`；`sync_phase='activate'` 只允许依据已发布/撤回 release 操作其冻结的 `bridgeai_knowledge_prod_*` 集合。registered/rejected/failed 不得进入生产投影。

### 8.16.3 版本与发布保护

已发布版本不可覆盖。文档版本允许状态推进；来源 Artifact、哈希、版本号和有效期在首次更新后保持不可变，解析器、切分策略与 embedding contract 则在首次离开 `registered`（正常路径即首次进入 `parsing`）时必须完整落盘并设置持久锁，之后即使 `failed → parsing` 重试也不得改写。正文片段、发布记录和引用快照均追加写。需要纠错时创建新的 `document_versions` 和 `chunks`，以 `supersedes_version_id` 关联旧版本，再追加 `publications(publication_action='supersede')`。

```sql
CREATE OR REPLACE FUNCTION bridgeai_knowledge.enforce_document_version_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'registered' OR NEW.processing_contract_locked_at IS NOT NULL THEN
            RAISE EXCEPTION 'document version must start registered with unlocked processing contract';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status <> 'registered' AND ROW(
        NEW.organization_id, NEW.project_id, NEW.document_id, NEW.version_no,
        NEW.content_sha256, NEW.source_artifact_id, NEW.source_artifact_version_id,
        NEW.supersedes_version_id, NEW.effective_from, NEW.effective_to
    ) IS DISTINCT FROM ROW(
        OLD.organization_id, OLD.project_id, OLD.document_id, OLD.version_no,
        OLD.content_sha256, OLD.source_artifact_id, OLD.source_artifact_version_id,
        OLD.supersedes_version_id, OLD.effective_from, OLD.effective_to
    ) THEN
        RAISE EXCEPTION 'document version identity and processing inputs are immutable';
    END IF;

    IF OLD.processing_contract_locked_at IS NOT NULL AND (
        NEW.processing_contract_locked_at IS DISTINCT FROM OLD.processing_contract_locked_at
        OR ROW(
            NEW.parser_name, NEW.parser_version, NEW.chunking_policy_version,
            NEW.embedding_contract_version
        ) IS DISTINCT FROM ROW(
            OLD.parser_name, OLD.parser_version, OLD.chunking_policy_version,
            OLD.embedding_contract_version
        )
    ) THEN
        RAISE EXCEPTION 'locked processing contract is immutable; create a new document version';
    END IF;

    IF OLD.status = 'registered' AND NEW.status <> 'registered' THEN
        IF NEW.parser_name IS NULL OR btrim(NEW.parser_name) = ''
           OR NEW.parser_version IS NULL OR btrim(NEW.parser_version) = ''
           OR NEW.chunking_policy_version IS NULL OR btrim(NEW.chunking_policy_version) = ''
           OR NEW.embedding_contract_version IS NULL
           OR btrim(NEW.embedding_contract_version) = '' THEN
            RAISE EXCEPTION 'leaving registered requires complete parser/chunker/embedding contract';
        END IF;
        NEW.processing_contract_locked_at := CURRENT_TIMESTAMP;
    END IF;

    IF OLD.status <> NEW.status AND NOT (
        (OLD.status = 'registered' AND NEW.status IN ('parsing', 'rejected', 'failed'))
        OR (OLD.status = 'parsing' AND NEW.status IN ('validating', 'failed'))
        OR (OLD.status = 'validating' AND NEW.status IN ('indexing', 'rejected', 'failed'))
        OR (OLD.status = 'indexing' AND NEW.status IN ('review_pending', 'failed'))
        OR (OLD.status = 'review_pending' AND NEW.status IN ('published', 'rejected'))
        OR (OLD.status = 'published' AND NEW.status IN ('superseded', 'archived'))
        OR (OLD.status = 'failed' AND NEW.status = 'parsing')
    ) THEN
        RAISE EXCEPTION 'invalid document version transition: % -> %', OLD.status, NEW.status;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_document_versions_transition
BEFORE INSERT OR UPDATE ON bridgeai_knowledge.document_versions
FOR EACH ROW EXECUTE FUNCTION bridgeai_knowledge.enforce_document_version_transition();

CREATE OR REPLACE FUNCTION bridgeai_knowledge.validate_publication_insert()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    version_status TEXT;
    successor_status TEXT;
BEGIN
    SELECT status INTO version_status
    FROM bridgeai_knowledge.document_versions
    WHERE id = NEW.document_version_id
      AND organization_id = NEW.organization_id
      AND project_id = NEW.project_id
      AND document_id = NEW.document_id;

    IF NEW.publication_action = 'publish' AND version_status <> 'published' THEN
        RAISE EXCEPTION 'publish record requires published document version';
    ELSIF NEW.publication_action = 'supersede' THEN
        SELECT status INTO successor_status
        FROM bridgeai_knowledge.document_versions
        WHERE id = NEW.superseded_by_version_id
          AND organization_id = NEW.organization_id
          AND project_id = NEW.project_id
          AND document_id = NEW.document_id;
        IF version_status <> 'superseded' OR successor_status <> 'published' THEN
            RAISE EXCEPTION 'supersede record requires superseded source and published successor';
        END IF;
    ELSIF NEW.publication_action = 'archive' AND version_status <> 'archived' THEN
        RAISE EXCEPTION 'archive record requires archived document version';
    ELSIF NEW.publication_action = 'withdraw'
          AND version_status NOT IN ('superseded', 'archived') THEN
        RAISE EXCEPTION 'withdraw record requires non-serving document version';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_publications_validate_insert
BEFORE INSERT ON bridgeai_knowledge.publications
FOR EACH ROW EXECUTE FUNCTION bridgeai_knowledge.validate_publication_insert();

CREATE OR REPLACE FUNCTION bridgeai_knowledge.validate_chunk_insert()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    version_status TEXT;
    locked_parser_version TEXT;
    locked_chunking_version TEXT;
BEGIN
    SELECT status, parser_version, chunking_policy_version
      INTO version_status, locked_parser_version, locked_chunking_version
    FROM bridgeai_knowledge.document_versions
    WHERE id = NEW.document_version_id
      AND organization_id = NEW.organization_id
      AND project_id = NEW.project_id
      AND document_id = NEW.document_id;

    IF version_status <> 'indexing' THEN
        RAISE EXCEPTION 'chunks may be inserted only while document version is indexing';
    END IF;
    IF NEW.parser_version <> locked_parser_version
       OR NEW.chunking_policy_version <> locked_chunking_version THEN
        RAISE EXCEPTION 'chunk processing versions differ from locked document contract';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_chunks_validate_insert
BEFORE INSERT ON bridgeai_knowledge.chunks
FOR EACH ROW EXECUTE FUNCTION bridgeai_knowledge.validate_chunk_insert();

CREATE OR REPLACE FUNCTION bridgeai_knowledge.validate_citation_insert()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    version_status TEXT;
BEGIN
    SELECT status INTO version_status
    FROM bridgeai_knowledge.document_versions
    WHERE id = NEW.document_version_id
      AND organization_id = NEW.organization_id
      AND project_id = NEW.project_id
      AND document_id = NEW.document_id;
    IF version_status <> 'published' THEN
        RAISE EXCEPTION 'new citation requires a published document version';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_citations_validate_insert
BEFORE INSERT ON bridgeai_knowledge.citations
FOR EACH ROW EXECUTE FUNCTION bridgeai_knowledge.validate_citation_insert();

CREATE OR REPLACE FUNCTION bridgeai_knowledge.enforce_publication_item_snapshot()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    release_status TEXT;
    old_release_status TEXT;
    publication_action TEXT;
    publication_version_id UUID;
    version_status TEXT;
    actual_chunk_count INTEGER;
    actual_chunk_manifest JSONB;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        SELECT status INTO old_release_status
        FROM bridgeai_knowledge.knowledge_releases
        WHERE id = OLD.release_id
          AND organization_id = OLD.organization_id
          AND project_id = OLD.project_id
        FOR UPDATE;
        IF old_release_status <> 'draft' THEN
            RAISE EXCEPTION 'publication item snapshot is immutable after release publication';
        END IF;
    END IF;

    SELECT status INTO release_status
    FROM bridgeai_knowledge.knowledge_releases
    WHERE id = COALESCE(NEW.release_id, OLD.release_id)
      AND organization_id = COALESCE(NEW.organization_id, OLD.organization_id)
      AND project_id = COALESCE(NEW.project_id, OLD.project_id)
    FOR UPDATE;

    IF release_status <> 'draft' THEN
        RAISE EXCEPTION 'publication item snapshot is immutable after release publication';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    SELECT p.publication_action, p.document_version_id, dv.status
      INTO publication_action, publication_version_id, version_status
    FROM bridgeai_knowledge.publications AS p
    JOIN bridgeai_knowledge.document_versions AS dv
      ON dv.id = p.document_version_id
     AND dv.organization_id = p.organization_id
     AND dv.project_id = p.project_id
     AND dv.document_id = p.document_id
    WHERE p.id = NEW.publication_id
      AND p.organization_id = NEW.organization_id
      AND p.project_id = NEW.project_id;

    IF publication_action <> 'publish'
       OR publication_version_id <> NEW.document_version_id
       OR version_status <> 'published' THEN
        RAISE EXCEPTION 'release item requires the matching publish action and published version';
    END IF;

    SELECT count(*)::integer,
           jsonb_agg(
               jsonb_build_object(
                   'chunk_id', c.id::text,
                   'content_sha256', c.content_sha256
               ) ORDER BY c.ordinal_no
           )
      INTO actual_chunk_count, actual_chunk_manifest
    FROM bridgeai_knowledge.chunks AS c
    WHERE c.organization_id = NEW.organization_id
      AND c.project_id = NEW.project_id
      AND c.document_version_id = NEW.document_version_id;

    IF actual_chunk_count <> NEW.chunk_count
       OR actual_chunk_manifest IS DISTINCT FROM NEW.chunk_manifest
       OR encode(digest(NEW.chunk_manifest::text, 'sha256'), 'hex')
          <> NEW.chunk_manifest_sha256 THEN
        RAISE EXCEPTION 'release item chunk manifest does not match authoritative chunks';
    END IF;
    IF encode(digest(NEW.acl_snapshot::text, 'sha256'), 'hex')
       <> NEW.acl_snapshot_sha256 THEN
        RAISE EXCEPTION 'release item ACL snapshot hash mismatch';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_publication_items_snapshot
BEFORE INSERT OR UPDATE OR DELETE ON bridgeai_knowledge.publication_items
FOR EACH ROW EXECUTE FUNCTION bridgeai_knowledge.enforce_publication_item_snapshot();

CREATE OR REPLACE FUNCTION bridgeai_knowledge.enforce_knowledge_release_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    actual_item_count INTEGER;
    actual_manifest JSONB;
    incompatible_item_count INTEGER;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'draft' THEN
            RAISE EXCEPTION 'knowledge release initial status must be draft';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status IN ('published', 'withdrawn') AND ROW(
        NEW.organization_id, NEW.project_id, NEW.release_code, NEW.item_count,
        NEW.production_collection, NEW.qdrant_index_version, NEW.acl_snapshot,
        NEW.acl_snapshot_sha256, NEW.release_manifest, NEW.release_manifest_sha256,
        NEW.published_at, NEW.published_by
    ) IS DISTINCT FROM ROW(
        OLD.organization_id, OLD.project_id, OLD.release_code, OLD.item_count,
        OLD.production_collection, OLD.qdrant_index_version, OLD.acl_snapshot,
        OLD.acl_snapshot_sha256, OLD.release_manifest, OLD.release_manifest_sha256,
        OLD.published_at, OLD.published_by
    ) THEN
        RAISE EXCEPTION 'published release aggregate is immutable';
    END IF;

    IF OLD.status <> NEW.status AND NOT (
        (OLD.status = 'draft' AND NEW.status = 'published')
        OR (OLD.status = 'published' AND NEW.status = 'withdrawn')
    ) THEN
        RAISE EXCEPTION 'invalid knowledge release transition: % -> %', OLD.status, NEW.status;
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'published' THEN
        SELECT count(*)::integer,
               jsonb_agg(
                   jsonb_build_object(
                       'publication_item_id', i.id::text,
                       'document_version_id', i.document_version_id::text,
                       'chunk_manifest_sha256', i.chunk_manifest_sha256,
                       'qdrant_index_version', i.qdrant_index_version,
                       'qdrant_collection', i.qdrant_collection,
                       'acl_snapshot_sha256', i.acl_snapshot_sha256
                   ) ORDER BY i.ordinal_no
               ),
               count(*) FILTER (
                   WHERE i.qdrant_collection <> NEW.production_collection
                      OR i.qdrant_index_version <> NEW.qdrant_index_version
               )::integer
          INTO actual_item_count, actual_manifest, incompatible_item_count
        FROM bridgeai_knowledge.publication_items AS i
        WHERE i.release_id = NEW.id
          AND i.organization_id = NEW.organization_id
          AND i.project_id = NEW.project_id;

        IF actual_item_count <> NEW.item_count
           OR actual_item_count = 0
           OR actual_manifest IS DISTINCT FROM NEW.release_manifest
           OR encode(digest(NEW.release_manifest::text, 'sha256'), 'hex')
              <> NEW.release_manifest_sha256
           OR encode(digest(NEW.acl_snapshot::text, 'sha256'), 'hex')
              <> NEW.acl_snapshot_sha256
           OR incompatible_item_count <> 0 THEN
            RAISE EXCEPTION 'release aggregate does not match publication item snapshots';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_knowledge_releases_transition
BEFORE INSERT OR UPDATE ON bridgeai_knowledge.knowledge_releases
FOR EACH ROW EXECUTE FUNCTION bridgeai_knowledge.enforce_knowledge_release_transition();

CREATE OR REPLACE FUNCTION bridgeai_knowledge.enforce_index_sync_job_identity()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF ROW(
        NEW.id, NEW.organization_id, NEW.project_id, NEW.chunk_id, NEW.release_id,
        NEW.sync_phase, NEW.operation, NEW.idempotency_key,
        NEW.qdrant_collection, NEW.qdrant_point_id, NEW.qdrant_index_version,
        NEW.source_revision_sha256, NEW.created_at, NEW.created_by
    ) IS DISTINCT FROM ROW(
        OLD.id, OLD.organization_id, OLD.project_id, OLD.chunk_id, OLD.release_id,
        OLD.sync_phase, OLD.operation, OLD.idempotency_key,
        OLD.qdrant_collection, OLD.qdrant_point_id, OLD.qdrant_index_version,
        OLD.source_revision_sha256, OLD.created_at, OLD.created_by
    ) THEN
        RAISE EXCEPTION 'queued index job target, phase and source identity are immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_index_sync_jobs_identity
BEFORE UPDATE ON bridgeai_knowledge.index_sync_jobs
FOR EACH ROW EXECUTE FUNCTION bridgeai_knowledge.enforce_index_sync_job_identity();

CREATE OR REPLACE FUNCTION bridgeai_knowledge.validate_index_sync_job_insert()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    version_status TEXT;
    authoritative_sha256 TEXT;
    release_status TEXT;
    release_collection TEXT;
    release_index_version TEXT;
    authoritative_release_manifest_sha256 TEXT;
BEGIN
    IF NEW.sync_phase = 'build' THEN
        SELECT dv.status, c.content_sha256
          INTO version_status, authoritative_sha256
        FROM bridgeai_knowledge.chunks AS c
        JOIN bridgeai_knowledge.document_versions AS dv
          ON dv.id = c.document_version_id
         AND dv.organization_id = c.organization_id
         AND dv.project_id = c.project_id
         AND dv.document_id = c.document_id
        WHERE c.id = NEW.chunk_id
          AND c.organization_id = NEW.organization_id
          AND c.project_id = NEW.project_id;
        IF version_status NOT IN ('indexing', 'review_pending')
           OR authoritative_sha256 <> NEW.source_revision_sha256 THEN
            RAISE EXCEPTION 'staging build requires indexing/review_pending version and current chunk hash';
        END IF;
    ELSE
        SELECT status, production_collection, qdrant_index_version,
               kr.release_manifest_sha256
          INTO release_status, release_collection, release_index_version,
               authoritative_release_manifest_sha256
        FROM bridgeai_knowledge.knowledge_releases AS kr
        WHERE kr.id = NEW.release_id
          AND kr.organization_id = NEW.organization_id
          AND kr.project_id = NEW.project_id;
        IF (
            NEW.operation IN ('publish_collection', 'verify_collection')
            AND release_status <> 'published'
        ) OR (
            NEW.operation = 'withdraw_collection' AND release_status <> 'withdrawn'
        ) OR NEW.qdrant_collection <> release_collection
          OR NEW.qdrant_index_version <> release_index_version
          OR NEW.source_revision_sha256 <> authoritative_release_manifest_sha256 THEN
            RAISE EXCEPTION 'production activation must match published/withdrawn release snapshot';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_index_sync_jobs_validate_insert
BEFORE INSERT ON bridgeai_knowledge.index_sync_jobs
FOR EACH ROW EXECUTE FUNCTION bridgeai_knowledge.validate_index_sync_job_insert();

CREATE OR REPLACE FUNCTION bridgeai_knowledge.reject_immutable_row_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% rows are append-only', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER trg_chunks_append_only
BEFORE UPDATE OR DELETE ON bridgeai_knowledge.chunks
FOR EACH ROW EXECUTE FUNCTION bridgeai_knowledge.reject_immutable_row_change();
CREATE TRIGGER trg_publications_append_only
BEFORE UPDATE OR DELETE ON bridgeai_knowledge.publications
FOR EACH ROW EXECUTE FUNCTION bridgeai_knowledge.reject_immutable_row_change();
CREATE TRIGGER trg_citations_append_only
BEFORE UPDATE OR DELETE ON bridgeai_knowledge.citations
FOR EACH ROW EXECUTE FUNCTION bridgeai_knowledge.reject_immutable_row_change();
CREATE TRIGGER trg_knowledge_releases_no_delete
BEFORE DELETE ON bridgeai_knowledge.knowledge_releases
FOR EACH ROW EXECUTE FUNCTION bridgeai_knowledge.reject_immutable_row_change();
```

### 8.16.4 RLS 与一致性验证

```sql
DO $knowledge_rls$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'knowledge_sources', 'documents', 'document_versions', 'chunks',
        'publications', 'citations', 'knowledge_releases', 'publication_items',
        'index_sync_jobs'
    ]
    LOOP
        EXECUTE format('ALTER TABLE bridgeai_knowledge.%I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE bridgeai_knowledge.%I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format(
            'CREATE POLICY %I ON bridgeai_knowledge.%I USING (
                organization_id = NULLIF(current_setting(''app.organization_id'', true), '''')::uuid
                AND project_id = NULLIF(current_setting(''app.project_id'', true), '''')::uuid
             ) WITH CHECK (
                organization_id = NULLIF(current_setting(''app.organization_id'', true), '''')::uuid
                AND project_id = NULLIF(current_setting(''app.project_id'', true), '''')::uuid
             )',
            'pl_' || table_name || '_scope', table_name
        );
    END LOOP;
END
$knowledge_rls$;
```

发布切换前后至少执行以下验证；任何一项非零都禁止切换生产别名：

```sql
-- 发布版本必须存在唯一 publish 记录，且所有 chunk 均可定位。
SELECT dv.id
FROM bridgeai_knowledge.document_versions AS dv
LEFT JOIN bridgeai_knowledge.publications AS p
  ON p.document_version_id = dv.id
 AND p.organization_id = dv.organization_id
 AND p.project_id = dv.project_id
 AND p.publication_action = 'publish'
WHERE dv.status = 'published'
GROUP BY dv.id
HAVING count(p.id) <> 1;

SELECT c.id
FROM bridgeai_knowledge.chunks AS c
WHERE c.page_start IS NULL
  AND c.clause_number IS NULL
  AND c.char_start IS NULL;

-- Qdrant 只能是可重建投影；成功 build job 的来源哈希须仍等于权威 chunk 哈希。
SELECT j.id
FROM bridgeai_knowledge.index_sync_jobs AS j
JOIN bridgeai_knowledge.chunks AS c
  ON (c.id,c.organization_id,c.project_id) = (j.chunk_id,j.organization_id,j.project_id)
WHERE j.status = 'succeeded'
  AND j.sync_phase = 'build'
  AND j.operation IN ('upsert', 'verify_point')
  AND j.source_revision_sha256 <> c.content_sha256;

-- published release 必须可仅靠冻结 item 恢复，且生产激活参数与 aggregate 完全一致。
SELECT r.id
FROM bridgeai_knowledge.knowledge_releases AS r
LEFT JOIN bridgeai_knowledge.publication_items AS i
  ON (i.release_id,i.organization_id,i.project_id) = (r.id,r.organization_id,r.project_id)
WHERE r.status = 'published'
GROUP BY r.id, r.item_count, r.production_collection, r.qdrant_index_version,
         r.release_manifest_sha256
HAVING count(i.id) <> r.item_count
    OR count(*) FILTER (
        WHERE i.qdrant_collection <> r.production_collection
           OR i.qdrant_index_version <> r.qdrant_index_version
    ) <> 0
    OR NOT EXISTS (
        SELECT 1 FROM bridgeai_knowledge.index_sync_jobs AS j
        WHERE j.release_id = r.id
          AND j.organization_id = r.organization_id
          AND j.project_id = r.project_id
          AND j.sync_phase = 'activate'
          AND j.operation IN ('publish_collection','verify_collection')
          AND j.qdrant_collection = r.production_collection
          AND j.qdrant_index_version = r.qdrant_index_version
          AND j.source_revision_sha256 = r.release_manifest_sha256
    );
```

## 8.17 Memory 与 Context 数据模型

Memory 不是 RAG 知识的副本，也不是 LangGraph Checkpoint。`memory_records` 保存作用域、治理状态和当前修订指针，`memory_revisions` 保存内容修订，`memory_sources` 保存可复核来源版本，`context_manifests/context_manifest_items` 冻结每次实际召回和裁剪清单。普通 Agent 只能读取 Context Pack，不能直连这些表或 Qdrant。

完整生命周期覆盖 `candidate → validating → review_pending → active → superseded/expired/revoked/quarantined → tombstoned → deleted`，并保留 `conflicted/rejected` 分支；只有 `active` 可默认召回。

第七章同时要求 task/project/user/organization 作用域，因此 `memory_records` 是 8.7 表类别矩阵的一个明确“受控和类型”：`organization_id` 始终非空；`project_id` 只在 project/task 分支非空，且由组合外键验证；`scope_type` 和互斥列共同决定唯一主作用域，**绝不只凭 `project_id IS NULL` 推断组织级**，也不再增加含义重复且无法强校验的通用 `scope_id`。`system` 产品默认值属于真正全局配置，不写入承载租户内容的业务 Memory 表。

### 8.17.1 Memory 权威记录、修订与来源

```sql
CREATE TABLE bridgeai_memory.memory_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID,
    scope_type TEXT NOT NULL,
    task_id UUID,
    user_id UUID,
    memory_family_id UUID NOT NULL,
    memory_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'candidate',
    risk_level TEXT NOT NULL,
    confidence NUMERIC(5, 4) NOT NULL,
    validation_status TEXT NOT NULL DEFAULT 'unverified',
    owner_subject_id UUID NOT NULL,
    visibility TEXT NOT NULL,
    sensitivity TEXT NOT NULL DEFAULT 'internal',
    current_revision_id UUID,
    current_revision_no INTEGER,
    supersedes_memory_id UUID,
    valid_from TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_until TIMESTAMPTZ,
    retention_policy_version TEXT NOT NULL,
    deletion_status TEXT NOT NULL DEFAULT 'none',
    activated_at TIMESTAMPTZ,
    terminal_at TIMESTAMPTZ,
    terminal_reason TEXT,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_memory_records_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_memory_records_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_memory_records_task_scope
        FOREIGN KEY (task_id, organization_id, project_id)
        REFERENCES bridgeai_workflow.workflow_tasks (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_memory_records_user_scope
        FOREIGN KEY (user_id, organization_id)
        REFERENCES bridgeai_identity.users (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT uq_memory_records_id_organization UNIQUE (id, organization_id),
    CONSTRAINT uq_memory_records_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT fk_memory_records_supersedes_same_organization
        FOREIGN KEY (supersedes_memory_id, organization_id)
        REFERENCES bridgeai_memory.memory_records (id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT ck_memory_records_scope_type
        CHECK (scope_type IN ('organization', 'project', 'task', 'user')),
    CONSTRAINT ck_memory_records_single_primary_scope CHECK (
        (scope_type = 'organization'
         AND project_id IS NULL AND task_id IS NULL AND user_id IS NULL)
        OR (scope_type = 'project'
            AND project_id IS NOT NULL AND task_id IS NULL AND user_id IS NULL)
        OR (scope_type = 'task'
            AND project_id IS NOT NULL AND task_id IS NOT NULL AND user_id IS NULL)
        OR (scope_type = 'user'
            AND project_id IS NULL AND task_id IS NULL AND user_id IS NOT NULL)
    ),
    CONSTRAINT ck_memory_records_type CHECK (
        memory_type IN ('task_memory', 'project_memory', 'preference_memory', 'operational_memory')
    ),
    CONSTRAINT ck_memory_records_status CHECK (
        status IN (
            'candidate', 'validating', 'review_pending', 'active', 'conflicted',
            'rejected', 'superseded', 'expired', 'revoked', 'quarantined',
            'tombstoned', 'deleted'
        )
    ),
    CONSTRAINT ck_memory_records_risk CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    CONSTRAINT ck_memory_records_confidence CHECK (confidence BETWEEN 0 AND 1),
    CONSTRAINT ck_memory_records_validation CHECK (
        validation_status IN ('unverified', 'rule_validated', 'source_verified', 'human_confirmed')
    ),
    CONSTRAINT ck_memory_records_visibility CHECK (
        visibility IN ('private', 'project', 'organization')
        AND ((scope_type = 'user' AND visibility = 'private') OR scope_type <> 'user')
    ),
    CONSTRAINT ck_memory_records_sensitivity CHECK (
        sensitivity IN ('public', 'internal', 'confidential', 'restricted')
    ),
    CONSTRAINT ck_memory_records_current_revision_shape CHECK (
        (current_revision_id IS NULL AND current_revision_no IS NULL)
        OR (current_revision_id IS NOT NULL AND current_revision_no > 0)
    ),
    CONSTRAINT ck_memory_records_no_self_supersede CHECK (supersedes_memory_id IS DISTINCT FROM id),
    CONSTRAINT ck_memory_records_valid_range CHECK (
        valid_until IS NULL OR valid_until > valid_from
    ),
    CONSTRAINT ck_memory_records_retention_nonblank CHECK (btrim(retention_policy_version) <> ''),
    CONSTRAINT ck_memory_records_deletion_status CHECK (
        deletion_status IN ('none', 'pending', 'partial', 'complete', 'blocked')
    ),
    CONSTRAINT ck_memory_records_activation CHECK (
        (status = 'active' AND activated_at IS NOT NULL AND current_revision_id IS NOT NULL)
        OR status <> 'active'
    ),
    CONSTRAINT ck_memory_records_terminal CHECK (
        (status IN ('superseded', 'expired', 'revoked', 'quarantined', 'tombstoned', 'deleted')
         AND terminal_at IS NOT NULL AND terminal_reason IS NOT NULL
         AND btrim(terminal_reason) <> '')
        OR status NOT IN ('superseded', 'expired', 'revoked', 'quarantined', 'tombstoned', 'deleted')
    ),
    CONSTRAINT ck_memory_records_deleted_state CHECK (
        status <> 'deleted' OR deletion_status = 'complete'
    ),
    CONSTRAINT ck_memory_records_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_memory.memory_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID,
    memory_id UUID NOT NULL,
    revision_no INTEGER NOT NULL,
    content_text TEXT,
    summary TEXT,
    structured_facts JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_sha256 TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    embedding_model_version TEXT,
    qdrant_collection TEXT,
    qdrant_point_id TEXT,
    qdrant_index_version TEXT,
    index_status TEXT NOT NULL DEFAULT 'not_requested',
    indexed_at TIMESTAMPTZ,
    redacted_at TIMESTAMPTZ,
    redacted_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    CONSTRAINT fk_memory_revisions_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_memory_revisions_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_memory_revisions_memory_organization
        FOREIGN KEY (memory_id, organization_id)
        REFERENCES bridgeai_memory.memory_records (id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_memory_revisions_id_organization UNIQUE (id, organization_id),
    CONSTRAINT uq_memory_revisions_id_memory
        UNIQUE (id, organization_id, memory_id),
    CONSTRAINT uq_memory_revisions_number
        UNIQUE (organization_id, memory_id, revision_no),
    CONSTRAINT ck_memory_revisions_number_positive CHECK (revision_no > 0),
    CONSTRAINT ck_memory_revisions_content_shape CHECK (
        (redacted_at IS NULL AND content_text IS NOT NULL AND btrim(content_text) <> '')
        OR (redacted_at IS NOT NULL AND content_text IS NULL AND summary IS NULL
            AND structured_facts = '{}'::jsonb AND redacted_by IS NOT NULL)
    ),
    CONSTRAINT ck_memory_revisions_facts_object CHECK (jsonb_typeof(structured_facts) = 'object'),
    CONSTRAINT ck_memory_revisions_sha256 CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_memory_revisions_schema_nonblank CHECK (btrim(schema_version) <> ''),
    CONSTRAINT ck_memory_revisions_index_status CHECK (
        index_status IN ('not_requested', 'queued', 'ready', 'failed', 'deleting', 'deleted')
    ),
    CONSTRAINT ck_memory_revisions_index_fields CHECK (
        (qdrant_collection IS NULL AND qdrant_point_id IS NULL AND qdrant_index_version IS NULL)
        OR (qdrant_collection LIKE 'bridgeai_memory_%'
            AND qdrant_point_id IS NOT NULL AND btrim(qdrant_point_id) <> ''
            AND qdrant_index_version IS NOT NULL AND btrim(qdrant_index_version) <> '')
    ),
    CONSTRAINT ck_memory_revisions_ready_index CHECK (
        index_status <> 'ready'
        OR (qdrant_collection IS NOT NULL AND indexed_at IS NOT NULL AND redacted_at IS NULL)
    ),
    CONSTRAINT ck_memory_revisions_redacted_index CHECK (
        redacted_at IS NULL OR index_status IN ('deleting', 'deleted')
    )
);

ALTER TABLE bridgeai_memory.memory_records
    ADD CONSTRAINT fk_memory_records_current_revision
    FOREIGN KEY (current_revision_id, organization_id, id)
    REFERENCES bridgeai_memory.memory_revisions (id, organization_id, memory_id)
    ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE bridgeai_memory.memory_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID,
    memory_id UUID NOT NULL,
    memory_revision_id UUID NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_version TEXT NOT NULL,
    source_locator JSONB NOT NULL DEFAULT '{}'::jsonb,
    relation_type TEXT NOT NULL,
    source_sha256 TEXT,
    availability_status TEXT NOT NULL DEFAULT 'active',
    captured_at TIMESTAMPTZ NOT NULL,
    last_verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    CONSTRAINT fk_memory_sources_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_memory_sources_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_memory_sources_revision_memory
        FOREIGN KEY (memory_revision_id, organization_id, memory_id)
        REFERENCES bridgeai_memory.memory_revisions (id, organization_id, memory_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_memory_sources_id_organization UNIQUE (id, organization_id),
    CONSTRAINT uq_memory_sources_identity UNIQUE (
        organization_id, memory_revision_id, source_type, source_id, source_version, relation_type
    ),
    CONSTRAINT ck_memory_sources_type CHECK (
        source_type IN (
            'business_record', 'workflow_event', 'tool_result', 'human_review',
            'signed_report', 'user_action', 'evaluation_report', 'rag_evidence'
        )
    ),
    CONSTRAINT ck_memory_sources_id_nonblank CHECK (btrim(source_id) <> ''),
    CONSTRAINT ck_memory_sources_version_nonblank CHECK (btrim(source_version) <> ''),
    CONSTRAINT ck_memory_sources_locator_object CHECK (jsonb_typeof(source_locator) = 'object'),
    CONSTRAINT ck_memory_sources_relation CHECK (
        relation_type IN ('supports', 'corrects', 'supersedes', 'derived_from')
    ),
    CONSTRAINT ck_memory_sources_sha256 CHECK (
        source_sha256 IS NULL OR source_sha256 ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT ck_memory_sources_availability CHECK (
        availability_status IN ('active', 'unavailable', 'revoked', 'deleted')
    ),
    CONSTRAINT ck_memory_sources_verify_time CHECK (
        last_verified_at IS NULL OR last_verified_at >= captured_at
    )
);

CREATE TABLE bridgeai_memory.memory_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID,
    memory_id UUID NOT NULL,
    memory_revision_id UUID NOT NULL,
    feedback_type TEXT NOT NULL,
    actor_subject_id UUID NOT NULL,
    review_id UUID,
    reason TEXT NOT NULL,
    correction_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_memory_feedback_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_memory_feedback_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_memory_feedback_revision_memory
        FOREIGN KEY (memory_revision_id, organization_id, memory_id)
        REFERENCES bridgeai_memory.memory_revisions (id, organization_id, memory_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_memory_feedback_review_organization
        FOREIGN KEY (review_id, organization_id)
        REFERENCES bridgeai_workflow.workflow_reviews (id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_memory_feedback_id_organization UNIQUE (id, organization_id),
    CONSTRAINT ck_memory_feedback_type CHECK (
        feedback_type IN ('accepted', 'ignored', 'corrected', 'negated', 'reported')
    ),
    CONSTRAINT ck_memory_feedback_reason_nonblank CHECK (btrim(reason) <> ''),
    CONSTRAINT ck_memory_feedback_correction_shape CHECK (
        (feedback_type = 'corrected' AND correction_payload IS NOT NULL
         AND jsonb_typeof(correction_payload) = 'object')
        OR (feedback_type <> 'corrected' AND
            (correction_payload IS NULL OR jsonb_typeof(correction_payload) = 'object'))
    )
);
```

`memory_sources` 使用受控多态来源，因为业务记录、分区 Workflow Event、ToolResult、复核、签发报告、用户操作、评测和 RAG citation 的键形状不同；`source_id` 不是数据库强外键。唯一写入入口是 Memory Write Service：它按 `source_type` 调用相应领域只读服务或表适配器，校验 `organization_id`、可选 `project_id`、稳定 ID、`source_version` 和哈希；Workflow Event 还在 `source_locator` 保存 `occurred_at` 分区键，RAG 来源解析到 `citations` 的强版本链。Source Monitor 在来源撤回/删改事件和周期巡检中重复验证。允许类型仅限 CHECK 列表，无法验证的输入进入 `quarantined`，不得伪装成已由数据库证明的业务强关系。

### 8.17.2 Context Manifest 与实际召回清单

```sql
CREATE TABLE bridgeai_memory.context_manifests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    user_id UUID NOT NULL,
    task_id UUID NOT NULL,
    run_id UUID NOT NULL,
    thread_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    current_node TEXT NOT NULL,
    as_of TIMESTAMPTZ NOT NULL,
    query_fingerprint TEXT NOT NULL,
    retrieval_config_version TEXT NOT NULL,
    context_policy_version TEXT NOT NULL,
    candidate_item_count INTEGER NOT NULL,
    used_item_count INTEGER NOT NULL,
    omitted_item_count INTEGER NOT NULL,
    input_token_count INTEGER NOT NULL,
    memory_token_count INTEGER NOT NULL,
    reserved_token_count INTEGER NOT NULL,
    context_hash TEXT NOT NULL,
    schema_version TEXT NOT NULL DEFAULT 'context-manifest.v1',
    degraded BOOLEAN NOT NULL DEFAULT false,
    degradation_reason TEXT,
    requires_review BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    CONSTRAINT fk_context_manifests_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_context_manifests_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_context_manifests_user_scope
        FOREIGN KEY (user_id, organization_id)
        REFERENCES bridgeai_identity.users (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_context_manifests_task_scope
        FOREIGN KEY (task_id, organization_id, project_id)
        REFERENCES bridgeai_workflow.workflow_tasks (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_context_manifests_run_thread
        FOREIGN KEY (run_id, organization_id, project_id, task_id, thread_id)
        REFERENCES bridgeai_workflow.workflow_runs
                   (id, organization_id, project_id, task_id, thread_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_context_manifests_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT ck_context_manifests_thread_nonblank CHECK (btrim(thread_id) <> ''),
    CONSTRAINT ck_context_manifests_trace_nonblank CHECK (btrim(trace_id) <> ''),
    CONSTRAINT ck_context_manifests_node_nonblank CHECK (btrim(current_node) <> ''),
    CONSTRAINT ck_context_manifests_query_hash CHECK (query_fingerprint ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_context_manifests_context_hash CHECK (context_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_context_manifests_counts CHECK (
        candidate_item_count >= 0 AND used_item_count >= 0 AND omitted_item_count >= 0
        AND used_item_count + omitted_item_count <= candidate_item_count
    ),
    CONSTRAINT ck_context_manifests_tokens CHECK (
        input_token_count >= 0 AND memory_token_count >= 0 AND reserved_token_count >= 0
    ),
    CONSTRAINT ck_context_manifests_degradation CHECK (
        (degraded AND degradation_reason IS NOT NULL AND btrim(degradation_reason) <> '')
        OR (NOT degraded AND degradation_reason IS NULL)
    ),
    CONSTRAINT ck_context_manifests_policy_nonblank CHECK (
        btrim(retrieval_config_version) <> '' AND btrim(context_policy_version) <> ''
    )
);

CREATE TABLE bridgeai_memory.context_manifest_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    context_manifest_id UUID NOT NULL,
    ordinal_no INTEGER NOT NULL,
    item_kind TEXT NOT NULL,
    memory_id UUID,
    memory_revision_id UUID,
    citation_id UUID,
    business_ref_type TEXT,
    business_ref_id TEXT,
    disposition TEXT NOT NULL,
    omission_reason TEXT,
    candidate_rank INTEGER,
    token_count INTEGER NOT NULL,
    content_sha256 TEXT NOT NULL,
    compression_record JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    CONSTRAINT fk_context_manifest_items_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_context_manifest_items_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_context_manifest_items_manifest_scope
        FOREIGN KEY (context_manifest_id, organization_id, project_id)
        REFERENCES bridgeai_memory.context_manifests (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_context_manifest_items_memory_revision
        FOREIGN KEY (memory_revision_id, organization_id, memory_id)
        REFERENCES bridgeai_memory.memory_revisions (id, organization_id, memory_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_context_manifest_items_citation_scope
        FOREIGN KEY (citation_id, organization_id, project_id)
        REFERENCES bridgeai_knowledge.citations (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_context_manifest_items_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_context_manifest_items_ordinal
        UNIQUE (organization_id, project_id, context_manifest_id, ordinal_no),
    CONSTRAINT ck_context_manifest_items_ordinal_nonnegative CHECK (ordinal_no >= 0),
    CONSTRAINT ck_context_manifest_items_kind CHECK (
        item_kind IN ('memory_revision', 'rag_evidence', 'business_fact')
    ),
    CONSTRAINT ck_context_manifest_items_target_shape CHECK (
        (item_kind = 'memory_revision'
         AND memory_id IS NOT NULL AND memory_revision_id IS NOT NULL
         AND citation_id IS NULL AND business_ref_type IS NULL AND business_ref_id IS NULL)
        OR (item_kind = 'rag_evidence'
            AND memory_id IS NULL AND memory_revision_id IS NULL
            AND citation_id IS NOT NULL AND business_ref_type IS NULL AND business_ref_id IS NULL)
        OR (item_kind = 'business_fact'
            AND memory_id IS NULL AND memory_revision_id IS NULL AND citation_id IS NULL
            AND business_ref_type IS NOT NULL AND btrim(business_ref_type) <> ''
            AND business_ref_id IS NOT NULL AND btrim(business_ref_id) <> '')
    ),
    CONSTRAINT ck_context_manifest_items_disposition CHECK (
        disposition IN ('used', 'omitted', 'compressed')
    ),
    CONSTRAINT ck_context_manifest_items_omission CHECK (
        (disposition = 'omitted' AND omission_reason IN (
            'unauthorized', 'expired', 'duplicate', 'budget_exceeded',
            'conflicted', 'source_unavailable', 'revoked', 'quarantined'
        )) OR (disposition <> 'omitted' AND omission_reason IS NULL)
    ),
    CONSTRAINT ck_context_manifest_items_rank CHECK (
        candidate_rank IS NULL OR candidate_rank > 0
    ),
    CONSTRAINT ck_context_manifest_items_tokens CHECK (token_count >= 0),
    CONSTRAINT ck_context_manifest_items_sha256 CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_context_manifest_items_compression CHECK (
        (disposition = 'compressed' AND compression_record IS NOT NULL
         AND jsonb_typeof(compression_record) = 'object')
        OR (disposition <> 'compressed' AND compression_record IS NULL)
    )
);
```

每条 `context_manifest_items` 都是候选清单的一项，`candidate_rank` 保存进入裁剪前的位置，`disposition` 冻结最终 used/omitted/compressed 结果，且引用具体 `memory_revision_id` 或 RAG `citation_id`，不会在历史复现时漂移到“最新版本”。Manifest 同时冻结调用者 `user_id`；task 记忆必须与 manifest 的 task 和 project 都一致，project 记忆必须同 project，user 记忆必须同 user，organization 记忆只继承同组织。只有在 `as_of` 时仍为 active、有效且指向当前修订的记忆可标为 used/compressed；失效候选只能作为带原因的 omitted 审计项。`business_ref_type/id` 与 Citation 消费端一样只是受控外部引用，由 Context Builder 通过领域服务校验，不宣称数据库强关系。

### 8.17.3 删除传播与最小墓碑

```sql
CREATE TABLE bridgeai_memory.deletion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID,
    memory_id UUID NOT NULL,
    request_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    idempotency_key TEXT NOT NULL,
    requested_by UUID NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    legal_basis TEXT NOT NULL,
    postgres_redaction_status TEXT NOT NULL DEFAULT 'pending',
    qdrant_delete_status TEXT NOT NULL DEFAULT 'pending',
    cache_invalidation_status TEXT NOT NULL DEFAULT 'pending',
    artifact_cleanup_status TEXT NOT NULL DEFAULT 'pending',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    blocked_reason TEXT,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_deletion_jobs_organization
        FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_deletion_jobs_project_scope
        FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_deletion_jobs_memory_organization
        FOREIGN KEY (memory_id, organization_id)
        REFERENCES bridgeai_memory.memory_records (id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_deletion_jobs_id_organization UNIQUE (id, organization_id),
    CONSTRAINT uq_deletion_jobs_idempotency
        UNIQUE (organization_id, idempotency_key),
    CONSTRAINT ck_deletion_jobs_request_type
        CHECK (request_type IN ('revoke', 'retention_expiry', 'subject_request', 'source_deleted')),
    CONSTRAINT ck_deletion_jobs_status CHECK (
        status IN ('pending', 'running', 'blocked', 'failed', 'complete')
    ),
    CONSTRAINT ck_deletion_jobs_key_nonblank CHECK (btrim(idempotency_key) <> ''),
    CONSTRAINT ck_deletion_jobs_basis_nonblank CHECK (btrim(legal_basis) <> ''),
    CONSTRAINT ck_deletion_jobs_postgres_status CHECK (
        postgres_redaction_status IN ('pending', 'running', 'succeeded', 'not_required', 'failed')
    ),
    CONSTRAINT ck_deletion_jobs_qdrant_status CHECK (
        qdrant_delete_status IN ('pending', 'running', 'succeeded', 'not_required', 'failed')
    ),
    CONSTRAINT ck_deletion_jobs_cache_status CHECK (
        cache_invalidation_status IN ('pending', 'running', 'succeeded', 'not_required', 'failed')
    ),
    CONSTRAINT ck_deletion_jobs_artifact_status CHECK (
        artifact_cleanup_status IN ('pending', 'running', 'succeeded', 'not_required', 'failed')
    ),
    CONSTRAINT ck_deletion_jobs_attempt_nonnegative CHECK (attempt_count >= 0),
    CONSTRAINT ck_deletion_jobs_blocked_reason CHECK (
        (status = 'blocked' AND blocked_reason IS NOT NULL AND btrim(blocked_reason) <> '')
        OR status <> 'blocked'
    ),
    CONSTRAINT ck_deletion_jobs_complete CHECK (
        status <> 'complete'
        OR (
            completed_at IS NOT NULL
            AND postgres_redaction_status IN ('succeeded', 'not_required')
            AND qdrant_delete_status IN ('succeeded', 'not_required')
            AND cache_invalidation_status IN ('succeeded', 'not_required')
            AND artifact_cleanup_status IN ('succeeded', 'not_required')
            AND last_error IS NULL
        )
    ),
    CONSTRAINT ck_deletion_jobs_version_positive CHECK (version > 0)
);

CREATE INDEX ix_memory_records_recall
    ON bridgeai_memory.memory_records
       (organization_id, project_id, scope_type, status, memory_type, valid_until)
    WHERE status = 'active';
CREATE INDEX ix_memory_sources_revalidation
    ON bridgeai_memory.memory_sources
       (organization_id, availability_status, last_verified_at);
CREATE INDEX ix_context_manifests_task_time
    ON bridgeai_memory.context_manifests
       (organization_id, project_id, task_id, created_at DESC);
CREATE INDEX ix_deletion_jobs_claim
    ON bridgeai_memory.deletion_jobs
       (organization_id, status, requested_at)
    WHERE status IN ('pending', 'failed');
```

删除顺序固定为：同一 PostgreSQL 事务先将 active 记录转为 `revoked` 并以 `pending` 创建幂等 job → job 进入 `running` 后使缓存失效 → 只从 `bridgeai_memory_*` 集合删除 Memory point → 按保留/法律冻结策略清理 Artifact → 将记录转为 `tombstoned` 并通过受控过程清除全部修订正文 → 四个传播目标逐项核对成功后先把 job 标记 `complete`，再把记录标记 `deletion_status='complete'/status='deleted'`。记录的完成转换会再次验证同范围 complete job 与所有修订均已脱敏，不能靠直接更新状态绕过。`context_manifest_items`、原内容哈希、来源 ID/版本、删除依据、主体和时间作为不含正文的最小墓碑保留，使历史运行能说明“来源已删除”而不是静默换用新记忆。

Memory 与 RAG 的 Qdrant 集合强制隔离：Memory 仅允许 `bridgeai_memory_*`，知识同步仅允许 `bridgeai_knowledge_*`；不得共享集合或生产别名，Memory 命中不得冒充 `citations`/RAG Evidence。

### 8.17.4 作用域、状态和不可变行为

数据库函数补上普通外键无法表达的“可空项目仍必须与父记录完全一致”和版本状态机。只有 `active` 可进入普通 Context Pack；模型或自动归纳只能创建 `candidate`。每次写回后只要记录仍为 active，就重新验证当前修订、来源与 high/critical 资格，不能先以 low/tool result 激活后再升级风险，或事后降低 validation。对 `memory_sources` 的 UPDATE/DELETE 也在数据库内复核父记录：active high/critical 不能撤回、删除或降级其最后一个权威来源。记录资格更新和来源失效共用 memory 级事务 advisory lock，避免“风险升级”和“最后来源撤回”并发各自基于旧快照通过。

```sql
CREATE OR REPLACE FUNCTION bridgeai_memory.enforce_memory_record_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    source_count INTEGER;
    authoritative_source_count INTEGER;
    complete_deletion_job_count INTEGER;
    unredacted_revision_count INTEGER;
    predecessor bridgeai_memory.memory_records%ROWTYPE;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'candidate' THEN
            RAISE EXCEPTION 'memory initial status must be candidate';
        END IF;
    ELSE
        IF ROW(NEW.organization_id, NEW.project_id, NEW.scope_type, NEW.task_id,
               NEW.user_id, NEW.memory_family_id, NEW.memory_type)
           IS DISTINCT FROM
           ROW(OLD.organization_id, OLD.project_id, OLD.scope_type, OLD.task_id,
               OLD.user_id, OLD.memory_family_id, OLD.memory_type) THEN
            RAISE EXCEPTION 'memory primary scope, family and type are immutable';
        END IF;
        IF OLD.status = 'active'
           AND NEW.current_revision_id IS DISTINCT FROM OLD.current_revision_id THEN
            RAISE EXCEPTION 'active memory revision cannot be replaced in place';
        END IF;
    END IF;

    IF TG_OP = 'UPDATE' AND OLD.status <> NEW.status AND NOT (
        (OLD.status = 'candidate' AND NEW.status IN ('validating', 'rejected', 'quarantined', 'revoked'))
        OR (OLD.status = 'validating' AND NEW.status IN (
            'review_pending', 'conflicted', 'rejected', 'quarantined', 'revoked'
        ))
        OR (OLD.status = 'review_pending' AND NEW.status IN ('active', 'rejected', 'quarantined', 'revoked'))
        OR (OLD.status = 'conflicted' AND NEW.status IN ('review_pending', 'rejected', 'quarantined'))
        OR (OLD.status = 'active' AND NEW.status IN (
            'superseded', 'expired', 'revoked', 'quarantined'
        ))
        OR (OLD.status IN ('superseded', 'expired', 'revoked', 'quarantined')
            AND NEW.status = 'tombstoned')
        OR (OLD.status = 'tombstoned' AND NEW.status = 'deleted')
    ) THEN
        RAISE EXCEPTION 'invalid memory transition: % -> %', OLD.status, NEW.status;
    END IF;

    IF NEW.status = 'active' THEN
        PERFORM pg_advisory_xact_lock(
            hashtextextended(
                NEW.organization_id::text || E'\\x1f' || NEW.id::text,
                1
            )
        );
        IF NEW.current_revision_id IS NULL OR NEW.activated_at IS NULL THEN
            RAISE EXCEPTION 'active memory requires current revision and activated_at';
        END IF;
        SELECT count(*) INTO source_count
        FROM bridgeai_memory.memory_sources AS s
        WHERE s.memory_id = NEW.id
          AND s.organization_id = NEW.organization_id
          AND s.memory_revision_id = NEW.current_revision_id
          AND s.availability_status = 'active';
        IF source_count = 0 THEN
            RAISE EXCEPTION 'active memory requires an active versioned source';
        END IF;
        IF NEW.risk_level IN ('high', 'critical') THEN
            IF NEW.validation_status NOT IN ('source_verified', 'human_confirmed') THEN
                RAISE EXCEPTION 'high/critical memory requires confirmed validation status';
            END IF;
            SELECT count(*) INTO authoritative_source_count
            FROM bridgeai_memory.memory_sources AS s
            WHERE s.memory_id = NEW.id
              AND s.organization_id = NEW.organization_id
              AND s.memory_revision_id = NEW.current_revision_id
              AND s.availability_status = 'active'
              AND s.source_type IN (
                  'business_record', 'human_review', 'signed_report', 'evaluation_report'
              )
              AND (
                  s.source_type <> 'evaluation_report'
                  OR s.source_locator ->> 'publication_status' = 'published'
              );
            IF authoritative_source_count = 0 THEN
                RAISE EXCEPTION 'high/critical memory requires authoritative active source';
            END IF;
        END IF;
    END IF;

    IF NEW.supersedes_memory_id IS NOT NULL THEN
        SELECT * INTO predecessor
        FROM bridgeai_memory.memory_records
        WHERE id = NEW.supersedes_memory_id AND organization_id = NEW.organization_id;
        IF predecessor.id IS NULL
           OR predecessor.scope_type <> NEW.scope_type
           OR predecessor.project_id IS DISTINCT FROM NEW.project_id
           OR predecessor.task_id IS DISTINCT FROM NEW.task_id
           OR predecessor.user_id IS DISTINCT FROM NEW.user_id
           OR predecessor.memory_family_id <> NEW.memory_family_id THEN
            RAISE EXCEPTION 'superseded memory must have identical scope and family';
        END IF;
    END IF;

    IF TG_OP = 'UPDATE' AND (
        NEW.status = 'deleted'
        OR (NEW.deletion_status = 'complete' AND OLD.deletion_status <> 'complete')
    ) THEN
        SELECT count(*) INTO complete_deletion_job_count
        FROM bridgeai_memory.deletion_jobs AS d
        WHERE d.memory_id = NEW.id
          AND d.organization_id = NEW.organization_id
          AND d.project_id IS NOT DISTINCT FROM NEW.project_id
          AND d.status = 'complete'
          AND d.postgres_redaction_status IN ('succeeded', 'not_required')
          AND d.qdrant_delete_status IN ('succeeded', 'not_required')
          AND d.cache_invalidation_status IN ('succeeded', 'not_required')
          AND d.artifact_cleanup_status IN ('succeeded', 'not_required');

        SELECT count(*) INTO unredacted_revision_count
        FROM bridgeai_memory.memory_revisions AS r
        WHERE r.memory_id = NEW.id
          AND r.organization_id = NEW.organization_id
          AND (
              r.redacted_at IS NULL OR r.content_text IS NOT NULL
              OR r.summary IS NOT NULL OR r.structured_facts <> '{}'::jsonb
          );

        IF complete_deletion_job_count = 0 OR unredacted_revision_count <> 0 THEN
            RAISE EXCEPTION 'deleted/complete memory requires completed propagation job and all revisions redacted';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_memory_records_transition
BEFORE INSERT OR UPDATE ON bridgeai_memory.memory_records
FOR EACH ROW EXECUTE FUNCTION bridgeai_memory.enforce_memory_record_transition();

CREATE OR REPLACE FUNCTION bridgeai_memory.enforce_memory_revision_scope_and_content()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    parent_project_id UUID;
    parent_status TEXT;
    has_deletion_job BOOLEAN;
BEGIN
    SELECT project_id, status INTO parent_project_id, parent_status
    FROM bridgeai_memory.memory_records
    WHERE id = NEW.memory_id AND organization_id = NEW.organization_id;

    IF NOT FOUND OR parent_project_id IS DISTINCT FROM NEW.project_id THEN
        RAISE EXCEPTION 'memory revision project scope differs from parent';
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF ROW(
            NEW.organization_id, NEW.project_id, NEW.memory_id, NEW.revision_no,
            NEW.content_sha256, NEW.schema_version
        ) IS DISTINCT FROM ROW(
            OLD.organization_id, OLD.project_id, OLD.memory_id, OLD.revision_no,
            OLD.content_sha256, OLD.schema_version
        ) THEN
            RAISE EXCEPTION 'memory revision identity and digest are immutable';
        END IF;

        IF ROW(NEW.content_text, NEW.summary, NEW.structured_facts)
           IS DISTINCT FROM ROW(OLD.content_text, OLD.summary, OLD.structured_facts) THEN
            SELECT EXISTS (
                SELECT 1 FROM bridgeai_memory.deletion_jobs AS d
                WHERE d.memory_id = NEW.memory_id
                  AND d.organization_id = NEW.organization_id
                  AND d.status IN ('running', 'blocked')
            ) INTO has_deletion_job;
            IF NOT (
                OLD.redacted_at IS NULL AND NEW.redacted_at IS NOT NULL
                AND NEW.content_text IS NULL AND NEW.summary IS NULL
                AND NEW.structured_facts = '{}'::jsonb
                AND parent_status = 'tombstoned' AND has_deletion_job
            ) THEN
                RAISE EXCEPTION 'memory revision content is immutable except controlled redaction';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_memory_revisions_scope_content
BEFORE INSERT OR UPDATE ON bridgeai_memory.memory_revisions
FOR EACH ROW EXECUTE FUNCTION bridgeai_memory.enforce_memory_revision_scope_and_content();

CREATE OR REPLACE FUNCTION bridgeai_memory.enforce_memory_child_scope()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    parent_project_id UUID;
    review_project_id UUID;
BEGIN
    SELECT project_id INTO parent_project_id
    FROM bridgeai_memory.memory_records
    WHERE id = NEW.memory_id AND organization_id = NEW.organization_id;

    IF NOT FOUND OR parent_project_id IS DISTINCT FROM NEW.project_id THEN
        RAISE EXCEPTION '% project scope differs from memory parent', TG_TABLE_NAME;
    END IF;

    IF TG_TABLE_NAME = 'memory_feedback'
       AND (to_jsonb(NEW) ->> 'review_id') IS NOT NULL THEN
        SELECT project_id INTO review_project_id
        FROM bridgeai_workflow.workflow_reviews
        WHERE id = (to_jsonb(NEW) ->> 'review_id')::uuid
          AND organization_id = NEW.organization_id;
        IF parent_project_id IS NULL OR review_project_id IS DISTINCT FROM parent_project_id THEN
            RAISE EXCEPTION 'feedback review must belong to the same project-scoped memory';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_memory_sources_parent_scope
BEFORE INSERT OR UPDATE ON bridgeai_memory.memory_sources
FOR EACH ROW EXECUTE FUNCTION bridgeai_memory.enforce_memory_child_scope();
CREATE TRIGGER trg_memory_feedback_parent_scope
BEFORE INSERT OR UPDATE ON bridgeai_memory.memory_feedback
FOR EACH ROW EXECUTE FUNCTION bridgeai_memory.enforce_memory_child_scope();
CREATE TRIGGER trg_deletion_jobs_parent_scope
BEFORE INSERT OR UPDATE ON bridgeai_memory.deletion_jobs
FOR EACH ROW EXECUTE FUNCTION bridgeai_memory.enforce_memory_child_scope();

CREATE OR REPLACE FUNCTION bridgeai_memory.protect_active_authoritative_source()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    parent_status TEXT;
    parent_risk_level TEXT;
    parent_current_revision_id UUID;
    authoritative_source_count INTEGER;
BEGIN
    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            OLD.organization_id::text || E'\\x1f' || OLD.memory_id::text,
            1
        )
    );

    SELECT status, risk_level, current_revision_id
      INTO parent_status, parent_risk_level, parent_current_revision_id
    FROM bridgeai_memory.memory_records
    WHERE id = OLD.memory_id AND organization_id = OLD.organization_id;

    IF parent_status = 'active'
       AND parent_risk_level IN ('high', 'critical')
       AND parent_current_revision_id = OLD.memory_revision_id THEN
        SELECT count(*) INTO authoritative_source_count
        FROM bridgeai_memory.memory_sources AS s
        WHERE s.memory_id = OLD.memory_id
          AND s.organization_id = OLD.organization_id
          AND s.memory_revision_id = parent_current_revision_id
          AND s.id <> OLD.id
          AND s.availability_status = 'active'
          AND s.source_type IN (
              'business_record', 'human_review', 'signed_report', 'evaluation_report'
          )
          AND (
              s.source_type <> 'evaluation_report'
              OR s.source_locator ->> 'publication_status' = 'published'
          );
        IF TG_OP = 'UPDATE'
           AND NEW.memory_id = OLD.memory_id
           AND NEW.organization_id = OLD.organization_id
           AND NEW.memory_revision_id = parent_current_revision_id
           AND NEW.availability_status = 'active'
           AND NEW.source_type IN (
               'business_record', 'human_review', 'signed_report', 'evaluation_report'
           )
           AND (
               NEW.source_type <> 'evaluation_report'
               OR NEW.source_locator ->> 'publication_status' = 'published'
           ) THEN
            authoritative_source_count := authoritative_source_count + 1;
        END IF;
        IF authoritative_source_count = 0 THEN
            RAISE EXCEPTION 'active high/critical memory cannot lose its last authoritative source';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_memory_sources_active_eligibility
BEFORE UPDATE OR DELETE ON bridgeai_memory.memory_sources
FOR EACH ROW EXECUTE FUNCTION bridgeai_memory.protect_active_authoritative_source();

CREATE OR REPLACE FUNCTION bridgeai_memory.enforce_deletion_job_transition()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    unredacted_revision_count INTEGER;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'pending' THEN
            RAISE EXCEPTION 'deletion job initial status must be pending';
        END IF;
    ELSIF OLD.status <> NEW.status AND NOT (
        (OLD.status = 'pending' AND NEW.status IN ('running', 'blocked', 'failed'))
        OR (OLD.status IN ('blocked', 'failed') AND NEW.status = 'running')
        OR (OLD.status = 'running' AND NEW.status IN ('complete', 'blocked', 'failed'))
    ) THEN
        RAISE EXCEPTION 'invalid deletion job transition: % -> %', OLD.status, NEW.status;
    END IF;

    IF TG_OP = 'UPDATE' AND OLD.status <> 'complete' AND NEW.status = 'complete' THEN
        SELECT count(*) INTO unredacted_revision_count
        FROM bridgeai_memory.memory_revisions AS r
        WHERE r.memory_id = NEW.memory_id
          AND r.organization_id = NEW.organization_id
          AND (
              r.redacted_at IS NULL OR r.content_text IS NOT NULL
              OR r.summary IS NOT NULL OR r.structured_facts <> '{}'::jsonb
          );
        IF unredacted_revision_count <> 0 THEN
            RAISE EXCEPTION 'deletion job cannot complete before every revision is redacted';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_deletion_jobs_transition
BEFORE INSERT OR UPDATE ON bridgeai_memory.deletion_jobs
FOR EACH ROW EXECUTE FUNCTION bridgeai_memory.enforce_deletion_job_transition();

CREATE OR REPLACE FUNCTION bridgeai_memory.enforce_manifest_memory_scope()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    memory_scope_type TEXT;
    memory_project_id UUID;
    memory_task_id UUID;
    memory_user_id UUID;
    memory_status TEXT;
    memory_current_revision_id UUID;
    memory_valid_from TIMESTAMPTZ;
    memory_valid_until TIMESTAMPTZ;
    manifest_project_id UUID;
    manifest_task_id UUID;
    manifest_user_id UUID;
    manifest_as_of TIMESTAMPTZ;
BEGIN
    IF NEW.item_kind = 'memory_revision' THEN
        SELECT scope_type, project_id, task_id, user_id, status,
               current_revision_id, valid_from, valid_until
          INTO memory_scope_type, memory_project_id, memory_task_id, memory_user_id,
               memory_status, memory_current_revision_id, memory_valid_from,
               memory_valid_until
        FROM bridgeai_memory.memory_records
        WHERE id = NEW.memory_id AND organization_id = NEW.organization_id;

        SELECT project_id, task_id, user_id, as_of
          INTO manifest_project_id, manifest_task_id, manifest_user_id, manifest_as_of
        FROM bridgeai_memory.context_manifests
        WHERE id = NEW.context_manifest_id
          AND organization_id = NEW.organization_id
          AND project_id = NEW.project_id;

        IF NOT FOUND OR (
            memory_scope_type = 'task'
            AND (memory_project_id <> manifest_project_id OR memory_task_id <> manifest_task_id)
        ) OR (
            memory_scope_type = 'project' AND memory_project_id <> manifest_project_id
        ) OR (
            memory_scope_type = 'user' AND memory_user_id <> manifest_user_id
        ) OR memory_scope_type NOT IN ('task', 'project', 'user', 'organization') THEN
            RAISE EXCEPTION 'memory primary scope is not inherited by this manifest';
        END IF;

        IF NEW.disposition IN ('used', 'compressed') AND (
            memory_status <> 'active'
            OR memory_current_revision_id <> NEW.memory_revision_id
            OR memory_valid_from > manifest_as_of
            OR (memory_valid_until IS NOT NULL AND memory_valid_until <= manifest_as_of)
        ) THEN
            RAISE EXCEPTION 'used/compressed item requires active current memory revision at manifest as_of';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_context_manifest_items_memory_scope
BEFORE INSERT ON bridgeai_memory.context_manifest_items
FOR EACH ROW EXECUTE FUNCTION bridgeai_memory.enforce_manifest_memory_scope();

CREATE OR REPLACE FUNCTION bridgeai_memory.reject_manifest_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% rows are append-only', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER trg_context_manifests_append_only
BEFORE UPDATE OR DELETE ON bridgeai_memory.context_manifests
FOR EACH ROW EXECUTE FUNCTION bridgeai_memory.reject_manifest_mutation();
CREATE TRIGGER trg_context_manifest_items_append_only
BEFORE UPDATE OR DELETE ON bridgeai_memory.context_manifest_items
FOR EACH ROW EXECUTE FUNCTION bridgeai_memory.reject_manifest_mutation();
CREATE TRIGGER trg_memory_feedback_append_only
BEFORE UPDATE OR DELETE ON bridgeai_memory.memory_feedback
FOR EACH ROW EXECUTE FUNCTION bridgeai_memory.reject_manifest_mutation();
```

### 8.17.5 RLS 与验证查询

混合作用域表的 RLS 先验证组织，再允许“组织/用户分支”或当前项目；组织管理员跨项目读取必须显式设置受审计的 `app.all_projects=true`。用户私有记忆再以 RESTRICTIVE policy 限制到 `app.subject_id`，除非受控 Memory 管理入口设置 `app.memory_admin=true`。服务层仍负责用途、角色、敏感级别和 ACL 版本判断。

```sql
DO $memory_rls$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'memory_records', 'memory_revisions', 'memory_sources',
        'memory_feedback', 'deletion_jobs'
    ]
    LOOP
        EXECUTE format('ALTER TABLE bridgeai_memory.%I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE bridgeai_memory.%I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format(
            'CREATE POLICY %I ON bridgeai_memory.%I USING (
                organization_id = NULLIF(current_setting(''app.organization_id'', true), '''')::uuid
                AND (
                    project_id IS NULL
                    OR current_setting(''app.all_projects'', true) = ''true''
                    OR project_id = NULLIF(current_setting(''app.project_id'', true), '''')::uuid
                )
             ) WITH CHECK (
                organization_id = NULLIF(current_setting(''app.organization_id'', true), '''')::uuid
                AND (
                    project_id IS NULL
                    OR current_setting(''app.all_projects'', true) = ''true''
                    OR project_id = NULLIF(current_setting(''app.project_id'', true), '''')::uuid
                )
             )',
            'pl_' || table_name || '_scope', table_name
        );
    END LOOP;

    CREATE POLICY pl_memory_records_private_user
        ON bridgeai_memory.memory_records AS RESTRICTIVE
        USING (
            scope_type <> 'user'
            OR user_id = NULLIF(current_setting('app.subject_id', true), '')::uuid
            OR current_setting('app.memory_admin', true) = 'true'
        )
        WITH CHECK (
            scope_type <> 'user'
            OR user_id = NULLIF(current_setting('app.subject_id', true), '')::uuid
            OR current_setting('app.memory_admin', true) = 'true'
        );

    FOREACH table_name IN ARRAY ARRAY[
        'memory_revisions', 'memory_sources', 'memory_feedback', 'deletion_jobs'
    ]
    LOOP
        EXECUTE format(
            'CREATE POLICY %I ON bridgeai_memory.%I AS RESTRICTIVE USING (
                EXISTS (
                    SELECT 1 FROM bridgeai_memory.memory_records AS m
                    WHERE m.id = %I.memory_id
                      AND m.organization_id = %I.organization_id
                      AND (
                          m.scope_type <> ''user''
                          OR m.user_id = NULLIF(current_setting(''app.subject_id'', true), '''')::uuid
                          OR current_setting(''app.memory_admin'', true) = ''true''
                      )
                )
             ) WITH CHECK (
                EXISTS (
                    SELECT 1 FROM bridgeai_memory.memory_records AS m
                    WHERE m.id = %I.memory_id
                      AND m.organization_id = %I.organization_id
                      AND (
                          m.scope_type <> ''user''
                          OR m.user_id = NULLIF(current_setting(''app.subject_id'', true), '''')::uuid
                          OR current_setting(''app.memory_admin'', true) = ''true''
                      )
                )
             )',
            'pl_' || table_name || '_private_user', table_name,
            table_name, table_name, table_name, table_name
        );
    END LOOP;
END
$memory_rls$;

DO $manifest_rls$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['context_manifests', 'context_manifest_items']
    LOOP
        EXECUTE format('ALTER TABLE bridgeai_memory.%I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE bridgeai_memory.%I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format(
            'CREATE POLICY %I ON bridgeai_memory.%I USING (
                organization_id = NULLIF(current_setting(''app.organization_id'', true), '''')::uuid
                AND project_id = NULLIF(current_setting(''app.project_id'', true), '''')::uuid
             ) WITH CHECK (
                organization_id = NULLIF(current_setting(''app.organization_id'', true), '''')::uuid
                AND project_id = NULLIF(current_setting(''app.project_id'', true), '''')::uuid
             )',
            'pl_' || table_name || '_scope', table_name
        );
    END LOOP;
END
$manifest_rls$;
```

上线门禁至少包括以下查询，均应返回 0 行：

```sql
-- 当前修订必须真正属于该 memory；task scope 已由强组合 FK 绑定同一项目。
SELECT m.id
FROM bridgeai_memory.memory_records AS m
LEFT JOIN bridgeai_memory.memory_revisions AS r
  ON (r.id,r.organization_id,r.memory_id) = (m.current_revision_id,m.organization_id,m.id)
WHERE m.current_revision_id IS NOT NULL AND r.id IS NULL;

-- 普通召回资格：只有 active、有效、来源 active、当前修订索引版本一致。
SELECT m.id
FROM bridgeai_memory.memory_records AS m
JOIN bridgeai_memory.memory_revisions AS r
  ON (r.id,r.organization_id,r.memory_id) = (m.current_revision_id,m.organization_id,m.id)
WHERE m.status = 'active'
  AND (
      (m.valid_until IS NOT NULL AND m.valid_until <= CURRENT_TIMESTAMP)
      OR NOT EXISTS (
          SELECT 1 FROM bridgeai_memory.memory_sources AS s
          WHERE s.memory_revision_id = r.id
            AND s.organization_id = r.organization_id
            AND s.availability_status = 'active'
      )
      OR (
          m.risk_level IN ('high', 'critical')
          AND (
              m.validation_status NOT IN ('source_verified', 'human_confirmed')
              OR NOT EXISTS (
                  SELECT 1 FROM bridgeai_memory.memory_sources AS s
                  WHERE s.memory_revision_id = r.id
                    AND s.organization_id = r.organization_id
                    AND s.availability_status = 'active'
                    AND s.source_type IN (
                        'business_record', 'human_review', 'signed_report',
                        'evaluation_report'
                    )
                    AND (
                        s.source_type <> 'evaluation_report'
                        OR s.source_locator ->> 'publication_status' = 'published'
                    )
              )
          )
      )
      OR (r.index_status = 'ready' AND r.qdrant_collection NOT LIKE 'bridgeai_memory_%')
  );

-- Manifest 声明数与实际清单必须相等；删除完成必须已跨存储收敛。
SELECT m.id
FROM bridgeai_memory.context_manifests AS m
LEFT JOIN bridgeai_memory.context_manifest_items AS i
  ON (i.context_manifest_id,i.organization_id,i.project_id) = (m.id,m.organization_id,m.project_id)
GROUP BY m.id, m.candidate_item_count, m.used_item_count, m.omitted_item_count
HAVING count(i.id) <> m.candidate_item_count
    OR count(i.id) FILTER (WHERE i.disposition IN ('used','compressed')) <> m.used_item_count
    OR count(i.id) FILTER (WHERE i.disposition = 'omitted') <> m.omitted_item_count;

SELECT d.id
FROM bridgeai_memory.deletion_jobs AS d
JOIN bridgeai_memory.memory_records AS m
  ON (m.id,m.organization_id) = (d.memory_id,d.organization_id)
WHERE d.status = 'complete'
  AND (m.status <> 'deleted' OR m.deletion_status <> 'complete');
```

## 8.18 报告、引用、复核与签发模型

## 8.19 审计、安全事件与数据血缘

## 8.20 事务、并发、幂等与 Outbox

## 8.21 RLS、数据库角色与权限隔离

## 8.22 索引、查询与空间检索优化

## 8.23 分区、归档、保留与删除传播

## 8.24 数据迁移、兼容与发布流程

## 8.25 备份、恢复与灾难演练

## 8.26 性能、容量、可观测性与测试

## 8.27 第一阶段实施范围与架构决策

## 8.28 本章结论

## 参考资料

1. [PostgreSQL 官方文档：Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
2. [PostgreSQL 官方文档：Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)
3. [PostgreSQL 官方文档：Index Types](https://www.postgresql.org/docs/current/indexes-types.html)
4. [PostgreSQL 官方文档：Partial Indexes](https://www.postgresql.org/docs/current/indexes-partial.html)
5. [PostgreSQL 官方文档：Declarative Partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html)
6. [PostgreSQL 官方文档：Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
7. [PostgreSQL 官方文档：Explicit Locking](https://www.postgresql.org/docs/current/explicit-locking.html)
8. [PostgreSQL 官方文档：Continuous Archiving and PITR](https://www.postgresql.org/docs/current/continuous-archiving.html)
9. [PostgreSQL 官方文档：pgcrypto](https://www.postgresql.org/docs/current/pgcrypto.html)
10. [PostGIS Reference](https://postgis.net/docs/reference.html)
11. [PostGIS 官方文档：Spatial Reference Systems](https://postgis.net/docs/using_postgis_dbmanagement.html#spatial_ref_sys)
12. [PostGIS 官方教程：Spatial Indexing](https://postgis.net/workshops/postgis-intro/indexing.html)
13. [Alembic Documentation](https://alembic.sqlalchemy.org/en/latest/)
14. [Qdrant 官方文档：Payload](https://qdrant.tech/documentation/concepts/payload/)
15. [Qdrant 官方文档：Filtering](https://qdrant.tech/documentation/concepts/filtering/)
16. [MinIO AIStor 官方文档：Object Versioning](https://docs.min.io/aistor/administration/objects-and-versioning/versioning/)
17. [LangGraph 官方文档：Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)

## 修订记录

| 版本 | 日期 | 修订说明 |
|---|---|---|
| V1.0 | 2026-07-29 | 创建第八章《数据与数据库设计》正文骨架，并建立官方资料核验基线与跨章物理映射准备范围 |
