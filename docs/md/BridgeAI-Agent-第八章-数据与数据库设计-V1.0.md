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

报告是可重建的工程记录，不是一个可反复覆盖的 PDF 文件。`reports` 保存稳定业务身份和当前指针，`report_revisions` 固定生成时的 Workflow run、模型运行、知识发布和 Context Manifest；`report_items`、`report_citations` 和 `report_artifacts` 分别固定病害/Memory 修订、RAG 证据和对象字节版本。这些关系共同组成报告修订的不可变快照，不依赖“当前版本”查询来回放历史。

```sql
-- Context Manifest 必须以同一 Task/Run 身份被报告修订引用，不允许只按项目误绑。
ALTER TABLE bridgeai_memory.context_manifests
    ADD CONSTRAINT uq_context_manifests_report_binding
    UNIQUE (id, organization_id, project_id, task_id, run_id);

CREATE TABLE bridgeai_report.reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    report_code TEXT NOT NULL,
    report_type TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    current_revision_id UUID,
    current_revision_no INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_reports_organization FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_reports_project_scope FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT uq_reports_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_reports_project_code UNIQUE (organization_id, project_id, report_code),
    CONSTRAINT ck_reports_code_nonblank CHECK (btrim(report_code) <> ''),
    CONSTRAINT ck_reports_type_nonblank CHECK (btrim(report_type) <> ''),
    CONSTRAINT ck_reports_title_nonblank CHECK (btrim(title) <> ''),
    CONSTRAINT ck_reports_status
        CHECK (status IN ('draft', 'in_review', 'issued', 'withdrawn', 'superseded')),
    CONSTRAINT ck_reports_current_pair CHECK (
        (current_revision_id IS NULL AND current_revision_no IS NULL)
        OR (current_revision_id IS NOT NULL AND current_revision_no > 0)
    ),
    CONSTRAINT ck_reports_issued_pointer CHECK (
        status IN ('draft', 'in_review') OR current_revision_id IS NOT NULL
    ),
    CONSTRAINT ck_reports_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_report.report_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    report_id UUID NOT NULL,
    revision_no INTEGER NOT NULL,
    predecessor_revision_id UUID,
    predecessor_revision_no INTEGER,
    revision_status TEXT NOT NULL DEFAULT 'draft',
    workflow_task_id UUID NOT NULL,
    workflow_run_id UUID NOT NULL,
    model_inference_run_id UUID NOT NULL,
    knowledge_release_id UUID NOT NULL,
    context_manifest_id UUID NOT NULL,
    template_code TEXT NOT NULL,
    template_version TEXT NOT NULL,
    snapshot_schema_version TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    snapshot_manifest JSONB NOT NULL,
    snapshot_manifest_sha256 TEXT NOT NULL,
    change_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    CONSTRAINT fk_report_revisions_organization FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_report_revisions_project_scope FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_report_revisions_report_scope
        FOREIGN KEY (report_id, organization_id, project_id)
        REFERENCES bridgeai_report.reports (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_report_revisions_workflow_run
        FOREIGN KEY (workflow_run_id, organization_id, project_id, workflow_task_id)
        REFERENCES bridgeai_workflow.workflow_runs
                   (id, organization_id, project_id, task_id) ON DELETE RESTRICT,
    CONSTRAINT fk_report_revisions_model_run
        FOREIGN KEY (model_inference_run_id, organization_id, project_id)
        REFERENCES bridgeai_inspection.model_inference_runs
                   (id, organization_id, project_id) ON DELETE RESTRICT,
    CONSTRAINT fk_report_revisions_knowledge_release
        FOREIGN KEY (knowledge_release_id, organization_id, project_id)
        REFERENCES bridgeai_knowledge.knowledge_releases
                   (id, organization_id, project_id) ON DELETE RESTRICT,
    CONSTRAINT fk_report_revisions_context_manifest
        FOREIGN KEY (
            context_manifest_id, organization_id, project_id,
            workflow_task_id, workflow_run_id
        )
        REFERENCES bridgeai_memory.context_manifests
                   (id, organization_id, project_id, task_id, run_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_report_revisions_id_scope_report_revision
        UNIQUE (id, organization_id, project_id, report_id, revision_no),
    CONSTRAINT uq_report_revisions_report_revision
        UNIQUE (organization_id, project_id, report_id, revision_no),
    CONSTRAINT fk_report_revisions_predecessor_same_report
        FOREIGN KEY (
            predecessor_revision_id, organization_id, project_id,
            report_id, predecessor_revision_no
        ) REFERENCES bridgeai_report.report_revisions
          (id, organization_id, project_id, report_id, revision_no)
        DEFERRABLE INITIALLY IMMEDIATE,
    CONSTRAINT ck_report_revisions_number_positive CHECK (revision_no > 0),
    CONSTRAINT ck_report_revisions_predecessor_shape CHECK (
        (revision_no = 1 AND predecessor_revision_id IS NULL
         AND predecessor_revision_no IS NULL)
        OR (revision_no > 1 AND predecessor_revision_id IS NOT NULL
            AND predecessor_revision_no = revision_no - 1
            AND predecessor_revision_id <> id)
    ),
    CONSTRAINT ck_report_revisions_status
        CHECK (revision_status IN ('draft', 'ready', 'abandoned')),
    CONSTRAINT ck_report_revisions_template_nonblank
        CHECK (btrim(template_code) <> '' AND btrim(template_version) <> ''),
    CONSTRAINT ck_report_revisions_schema_nonblank
        CHECK (btrim(snapshot_schema_version) <> ''),
    CONSTRAINT ck_report_revisions_content_sha256
        CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_report_revisions_manifest_object
        CHECK (jsonb_typeof(snapshot_manifest) = 'object'),
    CONSTRAINT ck_report_revisions_manifest_sha256
        CHECK (snapshot_manifest_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_report_revisions_change_reason CHECK (
        revision_no = 1 OR (change_reason IS NOT NULL AND btrim(change_reason) <> '')
    )
);

ALTER TABLE bridgeai_report.reports
    ADD CONSTRAINT fk_reports_current_revision
    FOREIGN KEY (current_revision_id, organization_id, project_id, id, current_revision_no)
    REFERENCES bridgeai_report.report_revisions
               (id, organization_id, project_id, report_id, revision_no)
    ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE bridgeai_report.report_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    report_id UUID NOT NULL,
    report_revision_id UUID NOT NULL,
    report_revision_no INTEGER NOT NULL,
    ordinal_no INTEGER NOT NULL,
    item_kind TEXT NOT NULL,
    damage_observation_id UUID,
    damage_revision_id UUID,
    damage_revision_no INTEGER,
    memory_id UUID,
    memory_revision_id UUID,
    item_payload JSONB NOT NULL,
    item_sha256 TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    CONSTRAINT fk_report_items_revision FOREIGN KEY (
        report_revision_id, organization_id, project_id, report_id, report_revision_no
    ) REFERENCES bridgeai_report.report_revisions
      (id, organization_id, project_id, report_id, revision_no) ON DELETE RESTRICT,
    CONSTRAINT fk_report_items_damage_revision FOREIGN KEY (
        damage_revision_id, organization_id, project_id,
        damage_observation_id, damage_revision_no
    ) REFERENCES bridgeai_inspection.damage_revisions
      (id, organization_id, project_id, observation_id, revision_no)
      ON DELETE RESTRICT,
    CONSTRAINT fk_report_items_memory_revision
        FOREIGN KEY (memory_revision_id, organization_id, memory_id)
        REFERENCES bridgeai_memory.memory_revisions (id, organization_id, memory_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_report_items_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_report_items_id_revision_scope
        UNIQUE (id, organization_id, project_id, report_revision_id),
    CONSTRAINT uq_report_items_ordinal
        UNIQUE (organization_id, project_id, report_revision_id, ordinal_no),
    CONSTRAINT ck_report_items_ordinal_nonnegative CHECK (ordinal_no >= 0),
    CONSTRAINT ck_report_items_kind
        CHECK (item_kind IN ('damage_revision', 'memory_revision', 'summary', 'table', 'figure')),
    CONSTRAINT ck_report_items_target_shape CHECK (
        (item_kind = 'damage_revision'
         AND damage_observation_id IS NOT NULL AND damage_revision_id IS NOT NULL
         AND damage_revision_no IS NOT NULL
         AND memory_id IS NULL AND memory_revision_id IS NULL)
        OR (item_kind = 'memory_revision'
            AND memory_id IS NOT NULL AND memory_revision_id IS NOT NULL
            AND damage_observation_id IS NULL AND damage_revision_id IS NULL
            AND damage_revision_no IS NULL)
        OR (item_kind IN ('summary', 'table', 'figure')
            AND damage_observation_id IS NULL AND damage_revision_id IS NULL
            AND damage_revision_no IS NULL
            AND memory_id IS NULL AND memory_revision_id IS NULL)
    ),
    CONSTRAINT ck_report_items_payload_object CHECK (jsonb_typeof(item_payload) = 'object'),
    CONSTRAINT ck_report_items_sha256 CHECK (item_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE bridgeai_report.report_citations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    report_id UUID NOT NULL,
    report_revision_id UUID NOT NULL,
    report_revision_no INTEGER NOT NULL,
    report_item_id UUID,
    knowledge_citation_id UUID NOT NULL,
    ordinal_no INTEGER NOT NULL,
    claim_code TEXT NOT NULL,
    knowledge_excerpt_sha256 TEXT NOT NULL,
    citation_snapshot JSONB NOT NULL,
    citation_snapshot_sha256 TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    CONSTRAINT fk_report_citations_revision FOREIGN KEY (
        report_revision_id, organization_id, project_id, report_id, report_revision_no
    ) REFERENCES bridgeai_report.report_revisions
      (id, organization_id, project_id, report_id, revision_no) ON DELETE RESTRICT,
    CONSTRAINT fk_report_citations_item_scope
        FOREIGN KEY (
            report_item_id, organization_id, project_id, report_revision_id
        ) REFERENCES bridgeai_report.report_items
          (id, organization_id, project_id, report_revision_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_report_citations_knowledge_scope
        FOREIGN KEY (knowledge_citation_id, organization_id, project_id)
        REFERENCES bridgeai_knowledge.citations (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_report_citations_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_report_citations_ordinal
        UNIQUE (organization_id, project_id, report_revision_id, ordinal_no),
    CONSTRAINT uq_report_citations_claim_evidence
        UNIQUE (report_revision_id, claim_code, knowledge_citation_id),
    CONSTRAINT ck_report_citations_ordinal_nonnegative CHECK (ordinal_no >= 0),
    CONSTRAINT ck_report_citations_claim_nonblank CHECK (btrim(claim_code) <> ''),
    CONSTRAINT ck_report_citations_excerpt_sha256
        CHECK (knowledge_excerpt_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_report_citations_snapshot_object
        CHECK (jsonb_typeof(citation_snapshot) = 'object'),
    CONSTRAINT ck_report_citations_snapshot_sha256
        CHECK (citation_snapshot_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE bridgeai_report.report_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    report_id UUID NOT NULL,
    report_revision_id UUID NOT NULL,
    report_revision_no INTEGER NOT NULL,
    artifact_id UUID NOT NULL,
    artifact_version_id UUID NOT NULL,
    artifact_role TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    CONSTRAINT fk_report_artifacts_revision FOREIGN KEY (
        report_revision_id, organization_id, project_id, report_id, report_revision_no
    ) REFERENCES bridgeai_report.report_revisions
      (id, organization_id, project_id, report_id, revision_no) ON DELETE RESTRICT,
    CONSTRAINT fk_report_artifacts_artifact_scope
        FOREIGN KEY (artifact_id, organization_id, project_id)
        REFERENCES bridgeai_core.artifacts (id, organization_id, project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_report_artifacts_artifact_version FOREIGN KEY (
        artifact_version_id, organization_id, project_id, artifact_id
    ) REFERENCES bridgeai_core.artifact_versions
      (id, organization_id, project_id, artifact_id) ON DELETE RESTRICT,
    CONSTRAINT uq_report_artifacts_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_report_artifacts_revision_version_role
        UNIQUE (report_revision_id, artifact_version_id, artifact_role),
    CONSTRAINT ck_report_artifacts_role
        CHECK (artifact_role IN ('rendered_report', 'source', 'attachment', 'preview'))
);

CREATE TABLE bridgeai_report.report_signatures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    report_id UUID NOT NULL,
    report_revision_id UUID NOT NULL,
    report_revision_no INTEGER NOT NULL,
    signature_action TEXT NOT NULL,
    signature_status TEXT NOT NULL DEFAULT 'valid',
    content_sha256 TEXT NOT NULL,
    signed_by UUID NOT NULL,
    signing_membership_id UUID NOT NULL,
    signer_role_code TEXT NOT NULL,
    signed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    reason TEXT,
    prior_signature_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT fk_report_signatures_revision FOREIGN KEY (
        report_revision_id, organization_id, project_id, report_id, report_revision_no
    ) REFERENCES bridgeai_report.report_revisions
      (id, organization_id, project_id, report_id, revision_no) ON DELETE RESTRICT,
    CONSTRAINT fk_report_signatures_user_scope FOREIGN KEY (signed_by, organization_id)
        REFERENCES bridgeai_identity.users (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_report_signatures_membership_scope FOREIGN KEY (
        signing_membership_id, organization_id, project_id
    ) REFERENCES bridgeai_core.project_memberships
      (id, organization_id, project_id) ON DELETE RESTRICT,
    CONSTRAINT uq_report_signatures_id_revision_scope
        UNIQUE (id, organization_id, project_id, report_revision_id),
    CONSTRAINT fk_report_signatures_prior_same_revision FOREIGN KEY (
        prior_signature_id, organization_id, project_id, report_revision_id
    ) REFERENCES bridgeai_report.report_signatures
      (id, organization_id, project_id, report_revision_id) ON DELETE RESTRICT,
    CONSTRAINT ck_report_signatures_action CHECK (signature_action IN ('issue', 'withdraw')),
    CONSTRAINT ck_report_signatures_status CHECK (signature_status = 'valid'),
    CONSTRAINT ck_report_signatures_hash CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_report_signatures_role_nonblank CHECK (btrim(signer_role_code) <> ''),
    CONSTRAINT ck_report_signatures_time CHECK (created_at >= signed_at),
    CONSTRAINT ck_report_signatures_action_shape CHECK (
        (signature_action = 'issue' AND prior_signature_id IS NULL AND reason IS NULL)
        OR (signature_action = 'withdraw' AND prior_signature_id IS NOT NULL
            AND reason IS NOT NULL AND btrim(reason) <> '')
    )
);

CREATE UNIQUE INDEX uq_report_signatures_one_issue
    ON bridgeai_report.report_signatures (report_revision_id)
    WHERE signature_action = 'issue';

CREATE UNIQUE INDEX uq_report_signatures_one_withdrawal
    ON bridgeai_report.report_signatures (prior_signature_id)
    WHERE signature_action = 'withdraw';
```

`memory_revisions` 的上游物理唯一键是 `(id, organization_id, memory_id)`，且组织/`user` 作用域的 `project_id` 合法为空；因此 `report_items` 不伪造一个不存在的 Memory 项目复合键。精确 Memory 修订由上述强外键固定，项目相容性由下列门禁再校验：只允许 `memory_records.project_id IS NULL` 或与报告项目相同。知识 `citation` 强外键固定原文版本和 Artifact；引用所属文档版本还必须存在于报告固定的 `knowledge_release` 中。

```sql
CREATE OR REPLACE FUNCTION bridgeai_report.validate_report_memory_item()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_report, bridgeai_memory
AS $$
DECLARE
    v_memory_project_id UUID;
BEGIN
    IF NEW.item_kind = 'memory_revision' THEN
        SELECT mr.project_id INTO STRICT v_memory_project_id
        FROM bridgeai_memory.memory_records AS mr
        WHERE mr.id = NEW.memory_id AND mr.organization_id = NEW.organization_id;
        IF v_memory_project_id IS NOT NULL AND v_memory_project_id <> NEW.project_id THEN
            RAISE EXCEPTION 'memory revision belongs to another project';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_report_items_validate_member
BEFORE INSERT OR UPDATE ON bridgeai_report.report_items
FOR EACH ROW EXECUTE FUNCTION bridgeai_report.validate_report_memory_item();

CREATE OR REPLACE FUNCTION bridgeai_report.validate_report_citation()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_report, bridgeai_knowledge
AS $$
DECLARE
    v_release_id UUID;
    v_document_version_id UUID;
    v_excerpt_sha256 TEXT;
BEGIN
    SELECT rr.knowledge_release_id, kc.document_version_id, kc.excerpt_sha256
      INTO STRICT v_release_id, v_document_version_id, v_excerpt_sha256
    FROM bridgeai_report.report_revisions AS rr
    JOIN bridgeai_knowledge.citations AS kc
      ON kc.id = NEW.knowledge_citation_id
     AND kc.organization_id = NEW.organization_id
     AND kc.project_id = NEW.project_id
    WHERE rr.id = NEW.report_revision_id
      AND rr.organization_id = NEW.organization_id
      AND rr.project_id = NEW.project_id;
    IF v_excerpt_sha256 <> NEW.knowledge_excerpt_sha256 THEN
        RAISE EXCEPTION 'citation excerpt hash does not match frozen knowledge citation';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM bridgeai_knowledge.publication_items AS pi
        WHERE pi.release_id = v_release_id
          AND pi.organization_id = NEW.organization_id
          AND pi.project_id = NEW.project_id
          AND pi.document_version_id = v_document_version_id
    ) THEN
        RAISE EXCEPTION 'citation document version is outside frozen knowledge release';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_report_citations_validate_member
BEFORE INSERT OR UPDATE ON bridgeai_report.report_citations
FOR EACH ROW EXECUTE FUNCTION bridgeai_report.validate_report_citation();

REVOKE ALL ON FUNCTION bridgeai_report.validate_report_memory_item() FROM PUBLIC;
REVOKE ALL ON FUNCTION bridgeai_report.validate_report_citation() FROM PUBLIC;

CREATE OR REPLACE FUNCTION bridgeai_report.reject_issued_snapshot_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_revision_id UUID;
BEGIN
    IF TG_TABLE_NAME = 'report_revisions' THEN
        v_revision_id := COALESCE(OLD.id, NEW.id);
    ELSE
        v_revision_id := COALESCE(
            (to_jsonb(OLD) ->> 'report_revision_id')::uuid,
            (to_jsonb(NEW) ->> 'report_revision_id')::uuid
        );
    END IF;
    -- 修订、子项和签发共用同一事务级锁；先到者决定快照边界。
    PERFORM pg_advisory_xact_lock(hashtextextended(v_revision_id::text, 0));
    IF EXISTS (
        SELECT 1 FROM bridgeai_report.report_signatures
        WHERE report_revision_id = v_revision_id AND signature_action = 'issue'
    ) THEN
        RAISE EXCEPTION 'issued report snapshot % is immutable', v_revision_id;
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;

CREATE TRIGGER trg_report_revisions_freeze
BEFORE INSERT OR UPDATE OR DELETE ON bridgeai_report.report_revisions
FOR EACH ROW EXECUTE FUNCTION bridgeai_report.reject_issued_snapshot_change();
CREATE TRIGGER trg_report_items_freeze
BEFORE INSERT OR UPDATE OR DELETE ON bridgeai_report.report_items
FOR EACH ROW EXECUTE FUNCTION bridgeai_report.reject_issued_snapshot_change();
CREATE TRIGGER trg_report_citations_freeze
BEFORE INSERT OR UPDATE OR DELETE ON bridgeai_report.report_citations
FOR EACH ROW EXECUTE FUNCTION bridgeai_report.reject_issued_snapshot_change();
CREATE TRIGGER trg_report_artifacts_freeze
BEFORE INSERT OR UPDATE OR DELETE ON bridgeai_report.report_artifacts
FOR EACH ROW EXECUTE FUNCTION bridgeai_report.reject_issued_snapshot_change();

CREATE OR REPLACE FUNCTION bridgeai_report.compute_snapshot_manifest(p_revision_id UUID)
RETURNS JSONB
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_report, bridgeai_core
AS $$
    SELECT jsonb_build_object(
        'items', COALESCE((
            SELECT jsonb_agg(jsonb_build_object(
                'id', ri.id, 'ordinal_no', ri.ordinal_no,
                'item_kind', ri.item_kind, 'item_sha256', ri.item_sha256
            ) ORDER BY ri.ordinal_no, ri.id)
            FROM bridgeai_report.report_items AS ri
            WHERE ri.report_revision_id = p_revision_id
        ), '[]'::jsonb),
        'citations', COALESCE((
            SELECT jsonb_agg(jsonb_build_object(
                'id', rc.id, 'ordinal_no', rc.ordinal_no,
                'claim_code', rc.claim_code,
                'knowledge_citation_id', rc.knowledge_citation_id,
                'knowledge_excerpt_sha256', rc.knowledge_excerpt_sha256,
                'citation_snapshot_sha256', rc.citation_snapshot_sha256
            ) ORDER BY rc.ordinal_no, rc.id)
            FROM bridgeai_report.report_citations AS rc
            WHERE rc.report_revision_id = p_revision_id
        ), '[]'::jsonb),
        'artifacts', COALESCE((
            SELECT jsonb_agg(jsonb_build_object(
                'id', ra.id, 'artifact_role', ra.artifact_role,
                'artifact_id', ra.artifact_id,
                'artifact_version_id', ra.artifact_version_id,
                'sha256', av.sha256
            ) ORDER BY ra.artifact_role, ra.id)
            FROM bridgeai_report.report_artifacts AS ra
            JOIN bridgeai_core.artifact_versions AS av
              ON av.id = ra.artifact_version_id
             AND av.organization_id = ra.organization_id
             AND av.project_id = ra.project_id
             AND av.artifact_id = ra.artifact_id
            WHERE ra.report_revision_id = p_revision_id
        ), '[]'::jsonb)
    );
$$;

CREATE OR REPLACE FUNCTION bridgeai_report.validate_report_signature()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_report, bridgeai_core, bridgeai_identity
AS $$
DECLARE
    v_revision bridgeai_report.report_revisions%ROWTYPE;
    v_prior bridgeai_report.report_signatures%ROWTYPE;
    v_actor_id UUID;
    v_manifest JSONB;
BEGIN
    IF current_user <> 'bridgeai_migration_owner' THEN
        RAISE EXCEPTION 'direct report signature insert is forbidden';
    END IF;
    IF current_setting('app.actor_type', true) IS DISTINCT FROM 'user' THEN
        RAISE EXCEPTION 'only a trusted user context may sign reports';
    END IF;
    v_actor_id := NULLIF(current_setting('app.actor_id', true), '')::uuid;
    IF v_actor_id IS NULL OR v_actor_id <> NEW.signed_by THEN
        RAISE EXCEPTION 'signature actor must be derived from trusted session context';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended(NEW.report_revision_id::text, 0));
    SELECT * INTO STRICT v_revision
    FROM bridgeai_report.report_revisions
    WHERE id = NEW.report_revision_id
      AND organization_id = NEW.organization_id
      AND project_id = NEW.project_id
    FOR UPDATE;
    PERFORM 1 FROM bridgeai_report.reports
    WHERE id = NEW.report_id AND organization_id = NEW.organization_id
      AND project_id = NEW.project_id FOR UPDATE;
    v_manifest := bridgeai_report.compute_snapshot_manifest(NEW.report_revision_id);
    IF v_revision.revision_status <> 'ready'
       OR v_revision.content_sha256 <> NEW.content_sha256
       OR v_revision.snapshot_manifest <> v_manifest
       OR v_revision.snapshot_manifest_sha256 <>
          encode(public.digest(convert_to(v_manifest::text, 'UTF8'), 'sha256'), 'hex') THEN
        RAISE EXCEPTION 'signature must bind the ready revision content hash';
    END IF;
    NEW.signed_at := clock_timestamp();
    NEW.created_at := NEW.signed_at;
    IF NOT EXISTS (
        SELECT 1 FROM bridgeai_core.project_memberships AS pm
        JOIN bridgeai_identity.users AS u
          ON u.id = pm.user_id AND u.organization_id = pm.organization_id
        JOIN bridgeai_identity.organization_memberships AS om
          ON om.organization_id = pm.organization_id AND om.user_id = pm.user_id
        WHERE pm.id = NEW.signing_membership_id
          AND pm.organization_id = NEW.organization_id
          AND pm.project_id = NEW.project_id
          AND pm.principal_type = 'user' AND pm.user_id = NEW.signed_by
          AND pm.role_code = NEW.signer_role_code
          AND pm.role_code IN ('report_issuer', 'project_admin')
          AND pm.status = 'active' AND u.status = 'active' AND om.status = 'active'
          AND om.valid_from <= NEW.signed_at
          AND (om.valid_to IS NULL OR om.valid_to > NEW.signed_at)
          AND pm.valid_from <= NEW.signed_at
          AND (pm.valid_to IS NULL OR pm.valid_to > NEW.signed_at)
    ) THEN
        RAISE EXCEPTION 'signer is not an active project member in the asserted role';
    END IF;
    IF NEW.signature_action = 'issue' THEN
        IF NOT EXISTS (
            SELECT 1 FROM bridgeai_report.report_artifacts AS ra
            JOIN bridgeai_core.artifact_versions AS av
              ON av.id = ra.artifact_version_id
             AND av.organization_id = ra.organization_id
             AND av.project_id = ra.project_id
             AND av.artifact_id = ra.artifact_id
            WHERE ra.report_revision_id = NEW.report_revision_id
              AND ra.artifact_role = 'rendered_report'
              AND av.sha256 = NEW.content_sha256
              AND av.status IN ('active', 'archived')
        ) THEN
            RAISE EXCEPTION 'issued revision requires a verified rendered Artifact with matching hash';
        END IF;
    ELSE
        SELECT * INTO STRICT v_prior
        FROM bridgeai_report.report_signatures
        WHERE id = NEW.prior_signature_id
          AND organization_id = NEW.organization_id
          AND project_id = NEW.project_id
          AND report_revision_id = NEW.report_revision_id;
        IF v_prior.signature_action <> 'issue'
           OR v_prior.content_sha256 <> NEW.content_sha256 THEN
            RAISE EXCEPTION 'withdrawal must append to the matching issue signature';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_report_signatures_validate
BEFORE INSERT ON bridgeai_report.report_signatures
FOR EACH ROW EXECUTE FUNCTION bridgeai_report.validate_report_signature();

CREATE OR REPLACE FUNCTION bridgeai_report.issue_report_revision(p_revision_id UUID)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_report, bridgeai_core, bridgeai_identity
AS $$
DECLARE
    v_revision bridgeai_report.report_revisions%ROWTYPE;
    v_actor_id UUID;
    v_membership bridgeai_core.project_memberships%ROWTYPE;
    v_signature_id UUID;
    v_manifest JSONB;
BEGIN
    IF current_setting('app.actor_type', true) IS DISTINCT FROM 'user' THEN
        RAISE EXCEPTION 'only a user may issue a report';
    END IF;
    v_actor_id := NULLIF(current_setting('app.actor_id', true), '')::uuid;
    IF v_actor_id IS NULL THEN RAISE EXCEPTION 'missing trusted actor context'; END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended(p_revision_id::text, 0));
    SELECT * INTO STRICT v_revision
      FROM bridgeai_report.report_revisions
     WHERE id = p_revision_id FOR UPDATE;
    PERFORM 1 FROM bridgeai_report.reports
     WHERE id = v_revision.report_id
       AND organization_id = v_revision.organization_id
       AND project_id = v_revision.project_id FOR UPDATE;

    IF v_revision.organization_id::text <> current_setting('app.organization_id', true)
       OR v_revision.project_id::text <> current_setting('app.project_id', true) THEN
        RAISE EXCEPTION 'report revision is outside trusted tenant context';
    END IF;
    SELECT pm.* INTO STRICT v_membership
      FROM bridgeai_core.project_memberships AS pm
      JOIN bridgeai_identity.users AS u
        ON u.id = pm.user_id AND u.organization_id = pm.organization_id
      JOIN bridgeai_identity.organization_memberships AS om
        ON om.organization_id = pm.organization_id AND om.user_id = pm.user_id
     WHERE pm.organization_id = v_revision.organization_id
       AND pm.project_id = v_revision.project_id
       AND pm.principal_type = 'user' AND pm.user_id = v_actor_id
       AND pm.status = 'active' AND pm.role_code IN ('report_issuer', 'project_admin')
       AND u.status = 'active' AND om.status = 'active'
       AND om.valid_from <= clock_timestamp()
       AND (om.valid_to IS NULL OR om.valid_to > clock_timestamp())
       AND pm.valid_from <= clock_timestamp()
       AND (pm.valid_to IS NULL OR pm.valid_to > clock_timestamp());

    SELECT id INTO v_signature_id
      FROM bridgeai_report.report_signatures
     WHERE report_revision_id = p_revision_id AND signature_action = 'issue';
    IF v_signature_id IS NOT NULL THEN RETURN v_signature_id; END IF;

    v_manifest := bridgeai_report.compute_snapshot_manifest(p_revision_id);
    IF v_revision.revision_status <> 'ready'
       OR v_revision.snapshot_manifest <> v_manifest
       OR v_revision.snapshot_manifest_sha256 <>
          encode(public.digest(convert_to(v_manifest::text, 'UTF8'), 'sha256'), 'hex') THEN
        RAISE EXCEPTION 'stored report snapshot no longer matches all frozen children';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM bridgeai_report.report_artifacts AS ra
        JOIN bridgeai_core.artifact_versions AS av
          ON av.id = ra.artifact_version_id
         AND av.organization_id = ra.organization_id
         AND av.project_id = ra.project_id AND av.artifact_id = ra.artifact_id
        WHERE ra.report_revision_id = p_revision_id
          AND ra.artifact_role = 'rendered_report'
          AND av.sha256 = v_revision.content_sha256
          AND av.status IN ('active', 'archived')
    ) THEN
        RAISE EXCEPTION 'verified rendered artifact does not match report content hash';
    END IF;

    INSERT INTO bridgeai_report.report_signatures (
        organization_id, project_id, report_id, report_revision_id,
        report_revision_no, signature_action, content_sha256, signed_by,
        signing_membership_id, signer_role_code
    ) VALUES (
        v_revision.organization_id, v_revision.project_id, v_revision.report_id,
        v_revision.id, v_revision.revision_no, 'issue', v_revision.content_sha256,
        v_actor_id, v_membership.id, v_membership.role_code
    ) RETURNING id INTO v_signature_id;

    UPDATE bridgeai_report.reports
       SET status = 'issued', current_revision_id = v_revision.id,
           current_revision_no = v_revision.revision_no,
           updated_at = clock_timestamp(), updated_by = v_actor_id, version = version + 1
     WHERE id = v_revision.report_id;
    INSERT INTO bridgeai_audit.audit_events (
        organization_id, project_id, actor_user_id, action, object_schema,
        object_table, object_id, object_version, result, request_id, trace_id,
        occurred_at, policy_version, after_sha256, details
    ) VALUES (
        v_revision.organization_id, v_revision.project_id, v_actor_id,
        'report.issue', 'bridgeai_report', 'reports', v_revision.report_id::text,
        v_revision.revision_no::text, 'succeeded',
        COALESCE(NULLIF(current_setting('app.request_id', true), ''),
                 'report-issue:' || v_signature_id::text),
        COALESCE(NULLIF(current_setting('app.trace_id', true), ''),
                 'report-issue:' || v_signature_id::text),
        clock_timestamp(), 'report-signature-v1', v_revision.content_sha256,
        jsonb_build_object('revision_id', v_revision.id,
                           'signature_id', v_signature_id)
    );
    PERFORM bridgeai_core.enqueue_outbox_event(
        v_revision.organization_id, v_revision.project_id, 'report',
        v_revision.report_id::text, v_revision.revision_no::text, 'report.issued', '1',
        jsonb_build_object('report_id', v_revision.report_id,
                           'revision_id', v_revision.id,
                           'signature_id', v_signature_id),
        'report.issue:' || v_revision.id::text, 8
    );
    RETURN v_signature_id;
END;
$$;

CREATE OR REPLACE FUNCTION bridgeai_report.withdraw_report_revision(
    p_issue_signature_id UUID, p_reason TEXT
) RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_report, bridgeai_core, bridgeai_identity
AS $$
DECLARE
    v_issue bridgeai_report.report_signatures%ROWTYPE;
    v_actor_id UUID;
    v_membership bridgeai_core.project_memberships%ROWTYPE;
    v_signature_id UUID;
BEGIN
    IF current_setting('app.actor_type', true) IS DISTINCT FROM 'user'
       OR p_reason IS NULL OR btrim(p_reason) = '' THEN
        RAISE EXCEPTION 'withdrawal requires a trusted user and nonblank reason';
    END IF;
    v_actor_id := NULLIF(current_setting('app.actor_id', true), '')::uuid;
    SELECT * INTO STRICT v_issue FROM bridgeai_report.report_signatures
     WHERE id = p_issue_signature_id AND signature_action = 'issue';
    PERFORM pg_advisory_xact_lock(hashtextextended(v_issue.report_revision_id::text, 0));
    PERFORM 1 FROM bridgeai_report.reports WHERE id = v_issue.report_id FOR UPDATE;
    IF v_issue.organization_id::text <> current_setting('app.organization_id', true)
       OR v_issue.project_id::text <> current_setting('app.project_id', true) THEN
        RAISE EXCEPTION 'signature is outside trusted tenant context';
    END IF;
    SELECT pm.* INTO STRICT v_membership
      FROM bridgeai_core.project_memberships AS pm
      JOIN bridgeai_identity.users AS u
        ON u.id = pm.user_id AND u.organization_id = pm.organization_id
      JOIN bridgeai_identity.organization_memberships AS om
        ON om.organization_id = pm.organization_id AND om.user_id = pm.user_id
     WHERE pm.organization_id = v_issue.organization_id
       AND pm.project_id = v_issue.project_id
       AND pm.principal_type = 'user' AND pm.user_id = v_actor_id
       AND pm.status = 'active' AND pm.role_code IN ('report_issuer', 'project_admin')
       AND u.status = 'active' AND om.status = 'active'
       AND om.valid_from <= clock_timestamp()
       AND (om.valid_to IS NULL OR om.valid_to > clock_timestamp())
       AND pm.valid_from <= clock_timestamp()
       AND (pm.valid_to IS NULL OR pm.valid_to > clock_timestamp());
    IF EXISTS (SELECT 1 FROM bridgeai_report.report_signatures
               WHERE prior_signature_id = p_issue_signature_id) THEN
        RAISE EXCEPTION 'issue signature is already withdrawn';
    END IF;
    INSERT INTO bridgeai_report.report_signatures (
        organization_id, project_id, report_id, report_revision_id,
        report_revision_no, signature_action, content_sha256, signed_by,
        signing_membership_id, signer_role_code, reason, prior_signature_id
    ) VALUES (
        v_issue.organization_id, v_issue.project_id, v_issue.report_id,
        v_issue.report_revision_id, v_issue.report_revision_no, 'withdraw',
        v_issue.content_sha256, v_actor_id, v_membership.id,
        v_membership.role_code, p_reason, v_issue.id
    ) RETURNING id INTO v_signature_id;
    UPDATE bridgeai_report.reports
       SET status = 'withdrawn', current_revision_id = v_issue.report_revision_id,
           current_revision_no = v_issue.report_revision_no,
           updated_at = clock_timestamp(), updated_by = v_actor_id, version = version + 1
     WHERE id = v_issue.report_id;
    INSERT INTO bridgeai_audit.audit_events (
        organization_id, project_id, actor_user_id, action, object_schema,
        object_table, object_id, object_version, result, request_id, trace_id,
        occurred_at, policy_version, before_sha256, details
    ) VALUES (
        v_issue.organization_id, v_issue.project_id, v_actor_id,
        'report.withdraw', 'bridgeai_report', 'reports', v_issue.report_id::text,
        v_issue.report_revision_no::text, 'succeeded',
        COALESCE(NULLIF(current_setting('app.request_id', true), ''),
                 'report-withdraw:' || v_signature_id::text),
        COALESCE(NULLIF(current_setting('app.trace_id', true), ''),
                 'report-withdraw:' || v_signature_id::text),
        clock_timestamp(), 'report-signature-v1', v_issue.content_sha256,
        jsonb_build_object('revision_id', v_issue.report_revision_id,
                           'signature_id', v_signature_id,
                           'prior_signature_id', v_issue.id)
    );
    PERFORM bridgeai_core.enqueue_outbox_event(
        v_issue.organization_id, v_issue.project_id, 'report', v_issue.report_id,
        v_issue.report_revision_no::text, 'report.withdrawn', '1',
        jsonb_build_object('report_id', v_issue.report_id,
                           'revision_id', v_issue.report_revision_id,
                           'signature_id', v_signature_id,
                           'prior_signature_id', v_issue.id),
        'report.withdraw:' || v_issue.id::text, 8
    );
    RETURN v_signature_id;
END;
$$;

CREATE OR REPLACE FUNCTION bridgeai_report.reject_signature_rewrite()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'report signatures are append-only; append a withdrawal instead';
END;
$$;

CREATE TRIGGER trg_report_signatures_append_only
BEFORE UPDATE OR DELETE ON bridgeai_report.report_signatures
FOR EACH ROW EXECUTE FUNCTION bridgeai_report.reject_signature_rewrite();

CREATE OR REPLACE FUNCTION bridgeai_report.assert_report_signature_state()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_report
AS $$
DECLARE
    v_report bridgeai_report.reports%ROWTYPE;
    v_latest bridgeai_report.report_signatures%ROWTYPE;
    v_report_id UUID;
BEGIN
    IF TG_TABLE_NAME = 'reports' THEN
        v_report_id := NEW.id;
    ELSE
        v_report_id := NEW.report_id;
    END IF;
    SELECT * INTO STRICT v_report FROM bridgeai_report.reports WHERE id = v_report_id;
    SELECT * INTO v_latest FROM bridgeai_report.report_signatures
     WHERE report_id = v_report_id
     ORDER BY signed_at DESC, id DESC LIMIT 1;
    IF v_report.status IN ('draft', 'in_review') THEN
        IF v_latest.id IS NOT NULL THEN
            RAISE EXCEPTION 'unsigned report state cannot have a signature history';
        END IF;
    ELSIF v_report.status = 'issued' THEN
        IF v_latest.id IS NULL OR v_latest.signature_action <> 'issue'
           OR v_report.current_revision_id <> v_latest.report_revision_id
           OR v_report.current_revision_no <> v_latest.report_revision_no THEN
            RAISE EXCEPTION 'issued report pointer must match its latest issue signature';
        END IF;
    ELSIF v_report.status IN ('withdrawn', 'superseded') THEN
        IF v_latest.id IS NULL OR v_latest.signature_action <> 'withdraw'
           OR v_report.current_revision_id <> v_latest.report_revision_id
           OR v_report.current_revision_no <> v_latest.report_revision_no THEN
            RAISE EXCEPTION 'withdrawn report pointer must match its latest withdrawal';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE CONSTRAINT TRIGGER trg_reports_signature_state
AFTER INSERT OR UPDATE ON bridgeai_report.reports
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION bridgeai_report.assert_report_signature_state();
CREATE CONSTRAINT TRIGGER trg_signatures_report_state
AFTER INSERT ON bridgeai_report.report_signatures
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION bridgeai_report.assert_report_signature_state();

REVOKE ALL ON FUNCTION bridgeai_report.validate_report_signature() FROM PUBLIC;
REVOKE ALL ON FUNCTION bridgeai_report.compute_snapshot_manifest(UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION bridgeai_report.issue_report_revision(UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION bridgeai_report.withdraw_report_revision(UUID, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION bridgeai_report.assert_report_signature_state() FROM PUBLIC;
```

应用不直接写签名或报告状态/当前指针；只调用 `issue_report_revision` 或 `withdraw_report_revision`。函数从受信会话上下文取用户，校验账号、组织和项目成员有效性及白名单角色，以服务器时间签发。共享 advisory lock 将子项变更与签发串行化；签发在锁内重算完整 Manifest/哈希并校验渲染 Artifact，再原子推进指针与 Outbox。撤签只追加 `withdraw`；再次签发必须新建修订。

## 8.19 审计、安全事件与数据血缘

审计域只保存“谁/哪个服务在什么作用域对哪个版本做了什么，结果如何”。密码、令牌、私钥、连接串、完整 Prompt、受限原文和大体积正文不得进入事件；只记录稳定标识、版本、有界摘要和 SHA-256。`occurred_at` 是业务事件时间，`server_recorded_at` 由数据库服务器写入，是审计排序和分区键。PostgreSQL 分区表的主键/唯一约束必须包含分区键，因此事件引用使用 `(id, server_recorded_at)`，不宣称跨分区 `id` 单列唯一。

```sql
CREATE OR REPLACE FUNCTION bridgeai_audit.event_details_are_safe(p_details JSONB)
RETURNS BOOLEAN
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    WITH RECURSIVE nodes(value) AS (
        SELECT p_details
        UNION ALL
        SELECT child.value
        FROM nodes AS n
        CROSS JOIN LATERAL (
            SELECT e.value FROM jsonb_each(
                CASE WHEN jsonb_typeof(n.value) = 'object' THEN n.value ELSE '{}'::jsonb END
            ) AS e(key, value)
            WHERE regexp_replace(lower(e.key), '[^a-z0-9]', '', 'g') = ANY (ARRAY[
                'password', 'secret', 'token', 'accesstoken', 'refreshtoken',
                'privatekey', 'connectionstring', 'authorization', 'cookie',
                'prompt', 'fullprompt', 'body', 'content'
            ]) IS FALSE
            UNION ALL
            SELECT a.value FROM jsonb_array_elements(
                CASE WHEN jsonb_typeof(n.value) = 'array' THEN n.value ELSE '[]'::jsonb END
            ) AS a(value)
        ) AS child
    ), unsafe AS (
        SELECT 1
        FROM nodes AS n
        CROSS JOIN LATERAL jsonb_object_keys(
            CASE WHEN jsonb_typeof(n.value) = 'object' THEN n.value ELSE '{}'::jsonb END
        ) AS k(key)
        WHERE regexp_replace(lower(k.key), '[^a-z0-9]', '', 'g') = ANY (ARRAY[
            'password', 'secret', 'token', 'accesstoken', 'refreshtoken',
            'privatekey', 'connectionstring', 'authorization', 'cookie',
            'prompt', 'fullprompt', 'body', 'content'
        ])
    )
    SELECT p_details IS NOT NULL
       AND jsonb_typeof(p_details) = 'object'
       AND NOT EXISTS (SELECT 1 FROM unsafe);
$$;

CREATE TABLE bridgeai_audit.audit_events (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID,
    actor_user_id UUID,
    service_principal_id UUID,
    action TEXT NOT NULL,
    object_schema TEXT NOT NULL,
    object_table TEXT NOT NULL,
    object_id TEXT NOT NULL,
    object_version TEXT,
    result TEXT NOT NULL,
    before_sha256 TEXT,
    after_sha256 TEXT,
    request_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    server_recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    policy_version TEXT NOT NULL,
    reason_code TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (id, server_recorded_at),
    CONSTRAINT fk_audit_events_organization FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_audit_events_project_scope FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_audit_events_actor_scope FOREIGN KEY (actor_user_id, organization_id)
        REFERENCES bridgeai_identity.users (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_audit_events_service_scope
        FOREIGN KEY (service_principal_id, organization_id)
        REFERENCES bridgeai_identity.service_principals (id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT ck_audit_events_subject_shape CHECK (
        (actor_user_id IS NOT NULL)::integer
        + (service_principal_id IS NOT NULL)::integer = 1
    ),
    CONSTRAINT ck_audit_events_names_nonblank CHECK (
        btrim(action) <> '' AND btrim(object_schema) <> ''
        AND btrim(object_table) <> '' AND btrim(object_id) <> ''
    ),
    CONSTRAINT ck_audit_events_result CHECK (result IN ('succeeded', 'denied', 'failed')),
    CONSTRAINT ck_audit_events_hashes CHECK (
        (before_sha256 IS NULL OR before_sha256 ~ '^[0-9a-f]{64}$')
        AND (after_sha256 IS NULL OR after_sha256 ~ '^[0-9a-f]{64}$')
    ),
    CONSTRAINT ck_audit_events_correlation_nonblank
        CHECK (btrim(request_id) <> '' AND btrim(trace_id) <> ''),
    CONSTRAINT ck_audit_events_policy_nonblank CHECK (btrim(policy_version) <> ''),
    CONSTRAINT ck_audit_events_details_safe CHECK (
        jsonb_typeof(details) = 'object'
        AND octet_length(details::text) <= 8192
        AND bridgeai_audit.event_details_are_safe(details)
    )
) PARTITION BY RANGE (server_recorded_at);

CREATE TABLE bridgeai_audit.audit_events_default
    PARTITION OF bridgeai_audit.audit_events DEFAULT;

CREATE TABLE bridgeai_audit.data_access_events (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID,
    actor_user_id UUID,
    service_principal_id UUID,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    access_action TEXT NOT NULL,
    purpose_code TEXT NOT NULL,
    result TEXT NOT NULL,
    row_count BIGINT,
    bytes_returned BIGINT,
    request_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    server_recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    policy_version TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (id, server_recorded_at),
    CONSTRAINT fk_data_access_events_organization FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_data_access_events_project_scope FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_data_access_events_actor_scope FOREIGN KEY (actor_user_id, organization_id)
        REFERENCES bridgeai_identity.users (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_data_access_events_service_scope
        FOREIGN KEY (service_principal_id, organization_id)
        REFERENCES bridgeai_identity.service_principals (id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT ck_data_access_events_subject_shape CHECK (
        (actor_user_id IS NOT NULL)::integer
        + (service_principal_id IS NOT NULL)::integer = 1
    ),
    CONSTRAINT ck_data_access_events_names_nonblank CHECK (
        btrim(resource_type) <> '' AND btrim(resource_id) <> ''
        AND btrim(access_action) <> '' AND btrim(purpose_code) <> ''
    ),
    CONSTRAINT ck_data_access_events_result CHECK (result IN ('allowed', 'denied', 'failed')),
    CONSTRAINT ck_data_access_events_counts CHECK (
        (row_count IS NULL OR row_count >= 0) AND (bytes_returned IS NULL OR bytes_returned >= 0)
    ),
    CONSTRAINT ck_data_access_events_correlation_nonblank
        CHECK (btrim(request_id) <> '' AND btrim(trace_id) <> ''),
    CONSTRAINT ck_data_access_events_policy_nonblank CHECK (btrim(policy_version) <> ''),
    CONSTRAINT ck_data_access_events_details_safe CHECK (
        jsonb_typeof(details) = 'object' AND octet_length(details::text) <= 4096
        AND bridgeai_audit.event_details_are_safe(details)
    )
) PARTITION BY RANGE (server_recorded_at);

CREATE TABLE bridgeai_audit.data_access_events_default
    PARTITION OF bridgeai_audit.data_access_events DEFAULT;

CREATE TABLE bridgeai_audit.security_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID,
    audit_event_id UUID,
    audit_server_recorded_at TIMESTAMPTZ,
    actor_user_id UUID,
    service_principal_id UUID,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    detection_source TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    disposition TEXT NOT NULL,
    request_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    server_recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    evidence_sha256 TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT fk_security_events_organization FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_security_events_project_scope FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_security_events_audit_event
        FOREIGN KEY (audit_event_id, audit_server_recorded_at)
        REFERENCES bridgeai_audit.audit_events (id, server_recorded_at)
        ON DELETE RESTRICT,
    CONSTRAINT fk_security_events_actor_scope FOREIGN KEY (actor_user_id, organization_id)
        REFERENCES bridgeai_identity.users (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_security_events_service_scope
        FOREIGN KEY (service_principal_id, organization_id)
        REFERENCES bridgeai_identity.service_principals (id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT ck_security_events_audit_pair CHECK (
        (audit_event_id IS NULL) = (audit_server_recorded_at IS NULL)
    ),
    CONSTRAINT ck_security_events_subject_present CHECK (
        actor_user_id IS NOT NULL OR service_principal_id IS NOT NULL
    ),
    CONSTRAINT ck_security_events_type_nonblank
        CHECK (btrim(event_type) <> '' AND btrim(detection_source) <> ''),
    CONSTRAINT ck_security_events_severity CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),
    CONSTRAINT ck_security_events_disposition
        CHECK (disposition IN ('observed', 'blocked', 'quarantined', 'investigating', 'resolved')),
    CONSTRAINT ck_security_events_correlation_nonblank
        CHECK (btrim(request_id) <> '' AND btrim(trace_id) <> ''),
    CONSTRAINT ck_security_events_evidence_sha256
        CHECK (evidence_sha256 IS NULL OR evidence_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_security_events_details_safe CHECK (
        jsonb_typeof(details) = 'object' AND octet_length(details::text) <= 8192
        AND bridgeai_audit.event_details_are_safe(details)
    )
);

CREATE TABLE bridgeai_audit.retention_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID,
    policy_code TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_version TEXT,
    target_sha256 TEXT,
    action TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    legal_hold_checked BOOLEAN NOT NULL DEFAULT false,
    shared_reference_count INTEGER,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    requested_by UUID NOT NULL,
    executed_by_service_id UUID,
    failure_code TEXT,
    result_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    version BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_retention_executions_organization FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_retention_executions_project_scope FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_retention_executions_requester FOREIGN KEY (requested_by, organization_id)
        REFERENCES bridgeai_identity.users (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_retention_executions_worker
        FOREIGN KEY (executed_by_service_id, organization_id)
        REFERENCES bridgeai_identity.service_principals (id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT ck_retention_executions_names_nonblank CHECK (
        btrim(policy_code) <> '' AND btrim(policy_version) <> ''
        AND btrim(target_type) <> '' AND btrim(target_id) <> ''
    ),
    CONSTRAINT ck_retention_executions_sha256
        CHECK (target_sha256 IS NULL OR target_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_retention_executions_action
        CHECK (action IN ('archive', 'revoke', 'delete_derived', 'delete_object', 'tombstone')),
    CONSTRAINT ck_retention_executions_status
        CHECK (status IN ('pending', 'running', 'succeeded', 'failed', 'blocked')),
    CONSTRAINT ck_retention_executions_reference_count
        CHECK (shared_reference_count IS NULL OR shared_reference_count >= 0),
    CONSTRAINT ck_retention_executions_result_object
        CHECK (jsonb_typeof(result_summary) = 'object' AND octet_length(result_summary::text) <= 8192),
    CONSTRAINT ck_retention_executions_version_positive CHECK (version > 0)
);

CREATE TABLE bridgeai_audit.lineage_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_version TEXT NOT NULL,
    source_sha256 TEXT,
    source_artifact_id UUID,
    source_artifact_version_id UUID,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_version TEXT NOT NULL,
    target_sha256 TEXT,
    target_artifact_id UUID,
    target_artifact_version_id UUID,
    relation_type TEXT NOT NULL,
    transformation_code TEXT,
    transformation_version TEXT,
    workflow_run_id UUID,
    workflow_task_id UUID,
    occurred_at TIMESTAMPTZ NOT NULL,
    server_recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    created_by_service_id UUID NOT NULL,
    CONSTRAINT fk_lineage_edges_organization FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_lineage_edges_project_scope FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_lineage_edges_source_artifact FOREIGN KEY (
        source_artifact_version_id, organization_id, project_id, source_artifact_id
    ) REFERENCES bridgeai_core.artifact_versions
      (id, organization_id, project_id, artifact_id) ON DELETE RESTRICT,
    CONSTRAINT fk_lineage_edges_target_artifact FOREIGN KEY (
        target_artifact_version_id, organization_id, project_id, target_artifact_id
    ) REFERENCES bridgeai_core.artifact_versions
      (id, organization_id, project_id, artifact_id) ON DELETE RESTRICT,
    CONSTRAINT fk_lineage_edges_workflow_run FOREIGN KEY (
        workflow_run_id, organization_id, project_id, workflow_task_id
    ) REFERENCES bridgeai_workflow.workflow_runs
      (id, organization_id, project_id, task_id) ON DELETE RESTRICT,
    CONSTRAINT fk_lineage_edges_service_scope
        FOREIGN KEY (created_by_service_id, organization_id)
        REFERENCES bridgeai_identity.service_principals (id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_lineage_edges_identity UNIQUE (
        organization_id, project_id, source_type, source_id, source_version,
        target_type, target_id, target_version, relation_type
    ),
    CONSTRAINT ck_lineage_edges_names_nonblank CHECK (
        btrim(source_type) <> '' AND btrim(source_id) <> '' AND btrim(source_version) <> ''
        AND btrim(target_type) <> '' AND btrim(target_id) <> '' AND btrim(target_version) <> ''
    ),
    CONSTRAINT ck_lineage_edges_hashes CHECK (
        (source_sha256 IS NULL OR source_sha256 ~ '^[0-9a-f]{64}$')
        AND (target_sha256 IS NULL OR target_sha256 ~ '^[0-9a-f]{64}$')
    ),
    CONSTRAINT ck_lineage_edges_artifact_shape CHECK (
        ((source_type = 'artifact_version')
         = (source_artifact_id IS NOT NULL AND source_artifact_version_id IS NOT NULL))
        AND ((target_type = 'artifact_version')
         = (target_artifact_id IS NOT NULL AND target_artifact_version_id IS NOT NULL))
    ),
    CONSTRAINT ck_lineage_edges_workflow_pair
        CHECK ((workflow_run_id IS NULL) = (workflow_task_id IS NULL)),
    CONSTRAINT ck_lineage_edges_relation
        CHECK (relation_type IN ('derived_from', 'rendered_from', 'cites', 'transformed_from', 'supersedes')),
    CONSTRAINT ck_lineage_edges_transform_pair CHECK (
        (transformation_code IS NULL) = (transformation_version IS NULL)
    )
);

CREATE OR REPLACE FUNCTION bridgeai_audit.reject_event_rewrite()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$;

CREATE OR REPLACE FUNCTION bridgeai_audit.force_server_recorded_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.server_recorded_at := clock_timestamp();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_audit_events_server_time
BEFORE INSERT ON bridgeai_audit.audit_events
FOR EACH ROW EXECUTE FUNCTION bridgeai_audit.force_server_recorded_at();
CREATE TRIGGER trg_data_access_events_server_time
BEFORE INSERT ON bridgeai_audit.data_access_events
FOR EACH ROW EXECUTE FUNCTION bridgeai_audit.force_server_recorded_at();
CREATE TRIGGER trg_security_events_server_time
BEFORE INSERT ON bridgeai_audit.security_events
FOR EACH ROW EXECUTE FUNCTION bridgeai_audit.force_server_recorded_at();
CREATE TRIGGER trg_lineage_edges_server_time
BEFORE INSERT ON bridgeai_audit.lineage_edges
FOR EACH ROW EXECUTE FUNCTION bridgeai_audit.force_server_recorded_at();

CREATE TRIGGER trg_audit_events_append_only
BEFORE UPDATE OR DELETE ON bridgeai_audit.audit_events
FOR EACH ROW EXECUTE FUNCTION bridgeai_audit.reject_event_rewrite();
CREATE TRIGGER trg_data_access_events_append_only
BEFORE UPDATE OR DELETE ON bridgeai_audit.data_access_events
FOR EACH ROW EXECUTE FUNCTION bridgeai_audit.reject_event_rewrite();
CREATE TRIGGER trg_security_events_append_only
BEFORE UPDATE OR DELETE ON bridgeai_audit.security_events
FOR EACH ROW EXECUTE FUNCTION bridgeai_audit.reject_event_rewrite();
CREATE TRIGGER trg_lineage_edges_append_only
BEFORE UPDATE OR DELETE ON bridgeai_audit.lineage_edges
FOR EACH ROW EXECUTE FUNCTION bridgeai_audit.reject_event_rewrite();
```

`lineage_edges` 的两端可以是多种领域对象，不可用单个多态 UUID 伪造强外键。Artifact 端有稳定键形时使用强组合外键；其余 `type/id/version/hash` 由领域写入器在同一事务内校验，并由血缘核对任务周期解析。无法解析的边记为完整性异常，不得对外声称已由数据库证明。

## 8.20 事务、并发、幂等与 Outbox

普通 CRUD 使用 PostgreSQL `READ COMMITTED`；修改带 `version` 的可变聚合时使用 `UPDATE ... WHERE id = $1 AND version = $2`，影响行数为零即返回乐观冲突。报告签发、知识发布和当前修订切换必须先 `SELECT ... FOR UPDATE` 锁定聚合；只有在跨多聚合不变式确实无法用行锁表达时，才在受控入口使用 `SERIALIZABLE` 并对 `40001` 限次、全抖动重试。

```sql
CREATE TABLE bridgeai_core.idempotency_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    operation_code TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_progress',
    response_code TEXT,
    response_sha256 TEXT,
    result_artifact_id UUID,
    result_artifact_version_id UUID,
    failure_code TEXT,
    locked_by TEXT,
    locked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT fk_idempotency_requests_organization FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_idempotency_requests_project_scope FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_idempotency_requests_result_artifact FOREIGN KEY (
        result_artifact_version_id, organization_id, project_id, result_artifact_id
    ) REFERENCES bridgeai_core.artifact_versions
      (id, organization_id, project_id, artifact_id) ON DELETE RESTRICT,
    CONSTRAINT uq_idempotency_requests_scope_key
        UNIQUE (organization_id, project_id, operation_code, idempotency_key),
    CONSTRAINT ck_idempotency_requests_names_nonblank
        CHECK (btrim(operation_code) <> '' AND btrim(idempotency_key) <> ''),
    CONSTRAINT ck_idempotency_requests_request_sha256
        CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_idempotency_requests_status CHECK (
        status IN ('in_progress', 'succeeded', 'failed_retryable', 'failed_terminal')
    ),
    CONSTRAINT ck_idempotency_requests_response_sha256
        CHECK (response_sha256 IS NULL OR response_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_idempotency_requests_artifact_pair
        CHECK ((result_artifact_id IS NULL) = (result_artifact_version_id IS NULL)),
    CONSTRAINT ck_idempotency_requests_terminal_shape CHECK (
        (status = 'in_progress' AND completed_at IS NULL)
        OR (status <> 'in_progress' AND completed_at IS NOT NULL)
    ),
    CONSTRAINT ck_idempotency_requests_failure_shape CHECK (
        (status LIKE 'failed_%' AND failure_code IS NOT NULL AND btrim(failure_code) <> '')
        OR (status NOT LIKE 'failed_%' AND failure_code IS NULL)
    ),
    CONSTRAINT ck_idempotency_requests_expiry CHECK (expires_at > created_at)
);

CREATE OR REPLACE FUNCTION bridgeai_core.register_idempotency_request(
    p_organization_id UUID,
    p_project_id UUID,
    p_operation_code TEXT,
    p_idempotency_key TEXT,
    p_request_sha256 TEXT,
    p_expires_at TIMESTAMPTZ
) RETURNS bridgeai_core.idempotency_requests
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_core
AS $$
DECLARE
    v_request bridgeai_core.idempotency_requests%ROWTYPE;
BEGIN
    IF p_organization_id IS DISTINCT FROM
       NULLIF(current_setting('app.organization_id', true), '')::uuid
       OR p_project_id IS DISTINCT FROM
       NULLIF(current_setting('app.project_id', true), '')::uuid THEN
        RAISE EXCEPTION 'idempotency scope differs from trusted transaction context';
    END IF;
    IF p_request_sha256 !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'request hash must be lowercase SHA-256';
    END IF;
    INSERT INTO bridgeai_core.idempotency_requests (
        organization_id, project_id, operation_code, idempotency_key,
        request_sha256, expires_at
    ) VALUES (
        p_organization_id, p_project_id, p_operation_code, p_idempotency_key,
        p_request_sha256, p_expires_at
    ) ON CONFLICT (organization_id, project_id, operation_code, idempotency_key)
      DO NOTHING
    RETURNING * INTO v_request;

    IF FOUND THEN
        RETURN v_request;
    END IF;
    SELECT * INTO STRICT v_request
      FROM bridgeai_core.idempotency_requests
     WHERE organization_id = p_organization_id AND project_id = p_project_id
       AND operation_code = p_operation_code AND idempotency_key = p_idempotency_key
     FOR UPDATE;
    IF v_request.request_sha256 <> p_request_sha256 THEN
        RAISE EXCEPTION 'idempotency key reused with a different request hash'
            USING ERRCODE = '22000';
    END IF;
    RETURN v_request;
END;
$$;

CREATE OR REPLACE FUNCTION bridgeai_core.protect_idempotency_identity()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF ROW(NEW.organization_id, NEW.project_id, NEW.operation_code,
           NEW.idempotency_key, NEW.request_sha256)
       IS DISTINCT FROM
       ROW(OLD.organization_id, OLD.project_id, OLD.operation_code,
           OLD.idempotency_key, OLD.request_sha256) THEN
        RAISE EXCEPTION 'idempotency request identity and hash are immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_idempotency_requests_identity
BEFORE UPDATE ON bridgeai_core.idempotency_requests
FOR EACH ROW EXECUTE FUNCTION bridgeai_core.protect_idempotency_identity();

REVOKE ALL ON FUNCTION bridgeai_core.register_idempotency_request(
    UUID, UUID, TEXT, TEXT, TEXT, TIMESTAMPTZ
) FROM PUBLIC;

CREATE OR REPLACE FUNCTION bridgeai_core.complete_idempotency_request(
    p_request_id UUID, p_response_code TEXT, p_response_sha256 TEXT,
    p_result_artifact_id UUID DEFAULT NULL,
    p_result_artifact_version_id UUID DEFAULT NULL
) RETURNS bridgeai_core.idempotency_requests
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_core
AS $$
DECLARE v_request bridgeai_core.idempotency_requests%ROWTYPE;
BEGIN
    SELECT * INTO STRICT v_request FROM bridgeai_core.idempotency_requests
     WHERE id = p_request_id FOR UPDATE;
    IF v_request.organization_id::text <> current_setting('app.organization_id', true)
       OR v_request.project_id::text <> current_setting('app.project_id', true)
       OR v_request.status <> 'in_progress' THEN
        RAISE EXCEPTION 'idempotency request is not completable in this context';
    END IF;
    UPDATE bridgeai_core.idempotency_requests
       SET status = 'succeeded', response_code = p_response_code,
           response_sha256 = p_response_sha256,
           result_artifact_id = p_result_artifact_id,
           result_artifact_version_id = p_result_artifact_version_id,
           failure_code = NULL, completed_at = clock_timestamp()
     WHERE id = p_request_id RETURNING * INTO v_request;
    RETURN v_request;
END;
$$;

CREATE OR REPLACE FUNCTION bridgeai_core.fail_idempotency_request(
    p_request_id UUID, p_failure_code TEXT, p_retryable BOOLEAN
) RETURNS bridgeai_core.idempotency_requests
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_core
AS $$
DECLARE v_request bridgeai_core.idempotency_requests%ROWTYPE;
BEGIN
    SELECT * INTO STRICT v_request FROM bridgeai_core.idempotency_requests
     WHERE id = p_request_id FOR UPDATE;
    IF v_request.organization_id::text <> current_setting('app.organization_id', true)
       OR v_request.project_id::text <> current_setting('app.project_id', true)
       OR v_request.status <> 'in_progress' OR btrim(p_failure_code) = '' THEN
        RAISE EXCEPTION 'idempotency request is not fail-able in this context';
    END IF;
    UPDATE bridgeai_core.idempotency_requests
       SET status = CASE WHEN p_retryable THEN 'failed_retryable' ELSE 'failed_terminal' END,
           failure_code = p_failure_code, completed_at = clock_timestamp()
     WHERE id = p_request_id RETURNING * INTO v_request;
    RETURN v_request;
END;
$$;

REVOKE ALL ON FUNCTION bridgeai_core.complete_idempotency_request(
    UUID, TEXT, TEXT, UUID, UUID
) FROM PUBLIC;
REVOKE ALL ON FUNCTION bridgeai_core.fail_idempotency_request(UUID, TEXT, BOOLEAN)
    FROM PUBLIC;

CREATE OR REPLACE FUNCTION bridgeai_core.outbox_event_semantic_sha256(
    p_organization_id UUID, p_project_id UUID, p_aggregate_type TEXT,
    p_aggregate_id TEXT, p_aggregate_version TEXT, p_event_type TEXT,
    p_event_schema_version TEXT, p_payload JSONB, p_max_attempts INTEGER
) RETURNS TEXT
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
SET search_path = pg_catalog, bridgeai_core
AS $$
    SELECT encode(public.digest(convert_to(jsonb_build_object(
        'organization_id', p_organization_id,
        'project_id', p_project_id,
        'aggregate_type', p_aggregate_type,
        'aggregate_id', p_aggregate_id,
        'aggregate_version', p_aggregate_version,
        'event_type', p_event_type,
        'event_schema_version', p_event_schema_version,
        'payload', p_payload,
        'max_attempts', p_max_attempts
    )::text, 'UTF8'), 'sha256'), 'hex');
$$;

CREATE TABLE bridgeai_core.outbox_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    aggregate_version TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_schema_version TEXT NOT NULL,
    payload JSONB NOT NULL,
    event_semantic_sha256 TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 8,
    available_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    locked_by TEXT,
    locked_at TIMESTAMPTZ,
    claim_token UUID,
    lease_expires_at TIMESTAMPTZ,
    last_error_code TEXT,
    last_error_summary TEXT,
    published_at TIMESTAMPTZ,
    dead_lettered_at TIMESTAMPTZ,
    replay_of_event_id UUID,
    replay_requested_by UUID,
    replay_requested_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT fk_outbox_events_organization FOREIGN KEY (organization_id)
        REFERENCES bridgeai_identity.organizations (id) ON DELETE RESTRICT,
    CONSTRAINT fk_outbox_events_project_scope FOREIGN KEY (project_id, organization_id)
        REFERENCES bridgeai_core.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT fk_outbox_events_replay_source FOREIGN KEY (
        replay_of_event_id, organization_id, project_id
    ) REFERENCES bridgeai_core.outbox_events (id, organization_id, project_id)
      ON DELETE RESTRICT,
    CONSTRAINT fk_outbox_events_replay_actor FOREIGN KEY (replay_requested_by, organization_id)
        REFERENCES bridgeai_identity.users (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT uq_outbox_events_id_scope UNIQUE (id, organization_id, project_id),
    CONSTRAINT uq_outbox_events_idempotency
        UNIQUE (organization_id, project_id, idempotency_key),
    CONSTRAINT ck_outbox_events_names_nonblank CHECK (
        btrim(aggregate_type) <> '' AND btrim(aggregate_id) <> ''
        AND btrim(aggregate_version) <> '' AND btrim(event_type) <> ''
        AND btrim(event_schema_version) <> '' AND btrim(idempotency_key) <> ''
    ),
    CONSTRAINT ck_outbox_events_payload_object CHECK (jsonb_typeof(payload) = 'object'),
    CONSTRAINT ck_outbox_events_semantic_sha256
        CHECK (event_semantic_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_outbox_events_semantic_digest CHECK (
        event_semantic_sha256 = bridgeai_core.outbox_event_semantic_sha256(
            organization_id, project_id, aggregate_type, aggregate_id,
            aggregate_version, event_type, event_schema_version, payload,
            max_attempts
        )
    ),
    CONSTRAINT ck_outbox_events_status
        CHECK (status IN ('pending', 'processing', 'retry', 'published', 'dead_letter')),
    CONSTRAINT ck_outbox_events_attempts
        CHECK (attempt_count >= 0 AND max_attempts > 0 AND attempt_count <= max_attempts),
    CONSTRAINT ck_outbox_events_lock_shape CHECK (
        (status = 'processing' AND locked_by IS NOT NULL AND btrim(locked_by) <> ''
         AND locked_at IS NOT NULL AND claim_token IS NOT NULL
         AND lease_expires_at > locked_at)
        OR (status <> 'processing' AND locked_by IS NULL AND locked_at IS NULL
            AND claim_token IS NULL AND lease_expires_at IS NULL)
    ),
    CONSTRAINT ck_outbox_events_terminal_shape CHECK (
        (status = 'published' AND published_at IS NOT NULL AND dead_lettered_at IS NULL)
        OR (status = 'dead_letter' AND dead_lettered_at IS NOT NULL AND published_at IS NULL)
        OR (status NOT IN ('published', 'dead_letter')
            AND published_at IS NULL AND dead_lettered_at IS NULL)
    ),
    CONSTRAINT ck_outbox_events_error_shape CHECK (
        status NOT IN ('retry', 'dead_letter')
        OR (last_error_code IS NOT NULL AND btrim(last_error_code) <> ''
            AND last_error_summary IS NOT NULL AND btrim(last_error_summary) <> '')
    ),
    CONSTRAINT ck_outbox_events_replay_shape CHECK (
        (replay_of_event_id IS NULL AND replay_requested_by IS NULL
         AND replay_requested_at IS NULL)
        OR (replay_of_event_id IS NOT NULL AND replay_requested_by IS NOT NULL
            AND replay_requested_at IS NOT NULL AND replay_of_event_id <> id)
    )
);

CREATE INDEX ix_outbox_events_claim
    ON bridgeai_core.outbox_events (available_at, created_at, id)
    WHERE status IN ('pending', 'retry');

CREATE OR REPLACE FUNCTION bridgeai_core.enforce_outbox_transition()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF current_user <> 'bridgeai_migration_owner' THEN
        RAISE EXCEPTION 'outbox rows may only be changed through controlled functions';
    END IF;
    IF ROW(NEW.organization_id, NEW.project_id, NEW.aggregate_type, NEW.aggregate_id,
           NEW.aggregate_version, NEW.event_type, NEW.event_schema_version,
           NEW.payload, NEW.event_semantic_sha256, NEW.idempotency_key, NEW.max_attempts,
           NEW.replay_of_event_id, NEW.replay_requested_by,
           NEW.replay_requested_at, NEW.created_at)
       IS DISTINCT FROM
       ROW(OLD.organization_id, OLD.project_id, OLD.aggregate_type, OLD.aggregate_id,
           OLD.aggregate_version, OLD.event_type, OLD.event_schema_version,
           OLD.payload, OLD.event_semantic_sha256, OLD.idempotency_key, OLD.max_attempts,
           OLD.replay_of_event_id, OLD.replay_requested_by,
           OLD.replay_requested_at, OLD.created_at) THEN
        RAISE EXCEPTION 'outbox event identity and payload are immutable';
    END IF;
    IF OLD.status <> NEW.status AND NOT (
        (OLD.status IN ('pending', 'retry') AND NEW.status = 'processing')
        OR (OLD.status = 'processing' AND NEW.status IN ('retry', 'published', 'dead_letter'))
    ) THEN
        RAISE EXCEPTION 'invalid outbox transition: % -> %', OLD.status, NEW.status;
    END IF;
    IF NEW.attempt_count < OLD.attempt_count
       OR NEW.attempt_count > OLD.attempt_count + 1 THEN
        RAISE EXCEPTION 'invalid outbox attempt change';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_outbox_events_transition
BEFORE UPDATE ON bridgeai_core.outbox_events
FOR EACH ROW EXECUTE FUNCTION bridgeai_core.enforce_outbox_transition();
```

Outbox 表不向运行时角色授予直接 `INSERT/UPDATE`。应用和 Worker 只能使用下列受控函数；Claim 同时产生不可猜的 token 和有限 lease，Ack/Fail 必须匹配事件、owner、token 且 lease 未过期。

```sql
CREATE OR REPLACE FUNCTION bridgeai_core.enqueue_outbox_event(
    p_organization_id UUID, p_project_id UUID, p_aggregate_type TEXT,
    p_aggregate_id TEXT, p_aggregate_version TEXT,
    p_event_type TEXT, p_event_schema_version TEXT, p_payload JSONB,
    p_idempotency_key TEXT, p_max_attempts INTEGER DEFAULT 8
) RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_core
AS $$
DECLARE
    v_id UUID;
    v_semantic_sha256 TEXT;
    v_existing bridgeai_core.outbox_events%ROWTYPE;
BEGIN
    IF p_organization_id::text <> current_setting('app.organization_id', true)
       OR p_project_id::text <> current_setting('app.project_id', true) THEN
        RAISE EXCEPTION 'outbox scope differs from trusted transaction context';
    END IF;
    v_semantic_sha256 := bridgeai_core.outbox_event_semantic_sha256(
        p_organization_id, p_project_id, p_aggregate_type, p_aggregate_id,
        p_aggregate_version, p_event_type, p_event_schema_version, p_payload,
        p_max_attempts
    );
    INSERT INTO bridgeai_core.outbox_events (
        organization_id, project_id, aggregate_type, aggregate_id,
        aggregate_version, event_type, event_schema_version, payload,
        event_semantic_sha256, idempotency_key, max_attempts
    ) VALUES (
        p_organization_id, p_project_id, p_aggregate_type, p_aggregate_id,
        p_aggregate_version, p_event_type, p_event_schema_version, p_payload,
        v_semantic_sha256, p_idempotency_key, p_max_attempts
    ) ON CONFLICT (organization_id, project_id, idempotency_key)
      DO NOTHING
    RETURNING id INTO v_id;
    IF FOUND THEN
        RETURN v_id;
    END IF;

    -- 唯一键冲突在并发事务下会等待获胜者；随后锁定已存行再比较语义。
    SELECT * INTO STRICT v_existing
      FROM bridgeai_core.outbox_events
     WHERE organization_id = p_organization_id AND project_id = p_project_id
       AND idempotency_key = p_idempotency_key
     FOR UPDATE;
    IF v_existing.event_semantic_sha256 <> v_semantic_sha256
       OR ROW(
           v_existing.aggregate_type, v_existing.aggregate_id,
           v_existing.aggregate_version, v_existing.event_type,
           v_existing.event_schema_version, v_existing.payload,
           v_existing.max_attempts
       ) IS DISTINCT FROM ROW(
           p_aggregate_type, p_aggregate_id, p_aggregate_version, p_event_type,
           p_event_schema_version, p_payload, p_max_attempts
       )
       OR v_existing.replay_of_event_id IS NOT NULL THEN
        RAISE EXCEPTION 'outbox idempotency key reused with different event semantics'
            USING ERRCODE = '22000';
    END IF;
    RETURN v_existing.id;
END;
$$;

CREATE OR REPLACE FUNCTION bridgeai_core.claim_outbox_events(
    p_organization_id UUID, p_project_id UUID, p_worker TEXT,
    p_limit INTEGER, p_lease INTERVAL
) RETURNS SETOF bridgeai_core.outbox_events
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_core
AS $$
BEGIN
    IF p_organization_id::text <> current_setting('app.organization_id', true)
       OR p_project_id::text <> current_setting('app.project_id', true)
       OR btrim(p_worker) = '' OR p_limit < 1
       OR p_lease <= INTERVAL '0 seconds' OR p_lease > INTERVAL '15 minutes' THEN
        RAISE EXCEPTION 'invalid outbox claim context or lease';
    END IF;
    RETURN QUERY
    WITH candidates AS (
        SELECT id FROM bridgeai_core.outbox_events
        WHERE organization_id = p_organization_id AND project_id = p_project_id
          AND status IN ('pending', 'retry') AND available_at <= clock_timestamp()
          AND attempt_count < max_attempts
        ORDER BY available_at, created_at, id
        FOR UPDATE SKIP LOCKED LIMIT p_limit
    )
    UPDATE bridgeai_core.outbox_events AS e
       SET status = 'processing', attempt_count = e.attempt_count + 1,
           locked_by = p_worker, locked_at = clock_timestamp(),
           claim_token = gen_random_uuid(), lease_expires_at = clock_timestamp() + p_lease
      FROM candidates AS c WHERE e.id = c.id RETURNING e.*;
END;
$$;

CREATE OR REPLACE FUNCTION bridgeai_core.ack_outbox_event(
    p_event_id UUID, p_worker TEXT, p_claim_token UUID
) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_core
AS $$
BEGIN
    UPDATE bridgeai_core.outbox_events
       SET status = 'published', published_at = clock_timestamp(),
           locked_by = NULL, locked_at = NULL, claim_token = NULL, lease_expires_at = NULL
     WHERE id = p_event_id AND status = 'processing' AND locked_by = p_worker
       AND claim_token = p_claim_token AND lease_expires_at > clock_timestamp()
       AND organization_id::text = current_setting('app.organization_id', true)
       AND project_id::text = current_setting('app.project_id', true);
    IF NOT FOUND THEN RAISE EXCEPTION 'outbox acknowledgement lease mismatch'; END IF;
END;
$$;

CREATE OR REPLACE FUNCTION bridgeai_core.fail_outbox_event(
    p_event_id UUID, p_worker TEXT, p_claim_token UUID,
    p_error_code TEXT, p_error_summary TEXT, p_retryable BOOLEAN
) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_core
AS $$
BEGIN
    UPDATE bridgeai_core.outbox_events
       SET status = CASE WHEN NOT p_retryable OR attempt_count >= max_attempts
                         THEN 'dead_letter' ELSE 'retry' END,
           available_at = clock_timestamp()
             + LEAST(INTERVAL '1 hour', INTERVAL '5 seconds' * power(2, attempt_count - 1)),
           locked_by = NULL, locked_at = NULL, claim_token = NULL, lease_expires_at = NULL,
           last_error_code = p_error_code, last_error_summary = left(p_error_summary, 1000),
           dead_lettered_at = CASE WHEN NOT p_retryable OR attempt_count >= max_attempts
                                  THEN clock_timestamp() END
     WHERE id = p_event_id AND status = 'processing' AND locked_by = p_worker
       AND claim_token = p_claim_token AND lease_expires_at > clock_timestamp()
       AND organization_id::text = current_setting('app.organization_id', true)
       AND project_id::text = current_setting('app.project_id', true);
    IF NOT FOUND THEN RAISE EXCEPTION 'outbox failure lease mismatch'; END IF;
END;
$$;

CREATE OR REPLACE FUNCTION bridgeai_core.reap_expired_outbox_events(
    p_organization_id UUID, p_project_id UUID, p_limit INTEGER
) RETURNS SETOF UUID
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_core
AS $$
BEGIN
    IF p_organization_id::text <> current_setting('app.organization_id', true)
       OR p_project_id::text <> current_setting('app.project_id', true) THEN
        RAISE EXCEPTION 'reaper scope differs from trusted context';
    END IF;
    RETURN QUERY
    WITH expired AS (
        SELECT id FROM bridgeai_core.outbox_events
        WHERE organization_id = p_organization_id AND project_id = p_project_id
          AND status = 'processing' AND lease_expires_at <= clock_timestamp()
        ORDER BY lease_expires_at, id FOR UPDATE SKIP LOCKED LIMIT p_limit
    )
    UPDATE bridgeai_core.outbox_events AS e
       SET status = CASE WHEN attempt_count >= max_attempts THEN 'dead_letter' ELSE 'retry' END,
           available_at = clock_timestamp(), locked_by = NULL, locked_at = NULL,
           claim_token = NULL, lease_expires_at = NULL,
           last_error_code = 'lease_expired', last_error_summary = 'worker lease expired',
           dead_lettered_at = CASE WHEN attempt_count >= max_attempts THEN clock_timestamp() END
      FROM expired AS x WHERE e.id = x.id RETURNING e.id;
END;
$$;

CREATE OR REPLACE FUNCTION bridgeai_core.replay_dead_letter_event(
    p_source_event_id UUID, p_new_idempotency_key TEXT
) RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_core, bridgeai_identity
AS $$
DECLARE v_source bridgeai_core.outbox_events%ROWTYPE; v_actor UUID; v_new_id UUID;
BEGIN
    IF current_setting('app.actor_type', true) IS DISTINCT FROM 'user' THEN
        RAISE EXCEPTION 'only a user may request dead-letter replay';
    END IF;
    v_actor := NULLIF(current_setting('app.actor_id', true), '')::uuid;
    SELECT * INTO STRICT v_source FROM bridgeai_core.outbox_events
     WHERE id = p_source_event_id FOR UPDATE;
    IF v_source.status <> 'dead_letter'
       OR v_source.organization_id::text <> current_setting('app.organization_id', true)
       OR v_source.project_id::text <> current_setting('app.project_id', true)
       OR NOT EXISTS (
           SELECT 1 FROM bridgeai_identity.users AS u
           JOIN bridgeai_identity.organization_memberships AS om
             ON om.organization_id = u.organization_id AND om.user_id = u.id
           JOIN bridgeai_core.project_memberships AS pm
             ON pm.organization_id = u.organization_id AND pm.user_id = u.id
            AND pm.principal_type = 'user'
           WHERE u.id = v_actor AND u.organization_id = v_source.organization_id
             AND u.status = 'active' AND om.status = 'active' AND pm.status = 'active'
             AND pm.project_id = v_source.project_id
             AND pm.role_code IN ('project_admin', 'outbox_replayer')
             AND om.valid_from <= clock_timestamp()
             AND (om.valid_to IS NULL OR om.valid_to > clock_timestamp())
             AND pm.valid_from <= clock_timestamp()
             AND (pm.valid_to IS NULL OR pm.valid_to > clock_timestamp())
       ) THEN
        RAISE EXCEPTION 'only an authorized dead-letter event may be replayed';
    END IF;
    INSERT INTO bridgeai_core.outbox_events (
        organization_id, project_id, aggregate_type, aggregate_id, aggregate_version,
        event_type, event_schema_version, payload, event_semantic_sha256,
        idempotency_key, max_attempts,
        replay_of_event_id, replay_requested_by, replay_requested_at
    ) VALUES (
        v_source.organization_id, v_source.project_id, v_source.aggregate_type,
        v_source.aggregate_id, v_source.aggregate_version, v_source.event_type,
        v_source.event_schema_version, v_source.payload,
        v_source.event_semantic_sha256, p_new_idempotency_key,
        v_source.max_attempts, v_source.id, v_actor, clock_timestamp()
    ) RETURNING id INTO v_new_id;
    RETURN v_new_id;
END;
$$;

REVOKE ALL ON FUNCTION bridgeai_core.enqueue_outbox_event(
    UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB, TEXT, INTEGER
) FROM PUBLIC;
REVOKE ALL ON FUNCTION bridgeai_core.claim_outbox_events(UUID, UUID, TEXT, INTEGER, INTERVAL)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION bridgeai_core.ack_outbox_event(UUID, TEXT, UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION bridgeai_core.fail_outbox_event(UUID, TEXT, UUID, TEXT, TEXT, BOOLEAN)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION bridgeai_core.reap_expired_outbox_events(UUID, UUID, INTEGER)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION bridgeai_core.replay_dead_letter_event(UUID, TEXT) FROM PUBLIC;

CREATE OR REPLACE FUNCTION bridgeai_core.request_artifact_version_deletion(
    p_artifact_version_id UUID, p_retention_execution_id UUID,
    p_reason TEXT, p_idempotency_key TEXT
) RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_core, bridgeai_audit, bridgeai_report,
                  bridgeai_inspection, bridgeai_knowledge, bridgeai_identity
AS $$
DECLARE
    v_artifact bridgeai_core.artifact_versions%ROWTYPE;
    v_retention bridgeai_audit.retention_executions%ROWTYPE;
    v_actor UUID;
    v_reference_count INTEGER;
    v_outbox_id UUID;
BEGIN
    IF current_setting('app.actor_type', true) IS DISTINCT FROM 'user'
       OR p_reason IS NULL OR btrim(p_reason) = '' THEN
        RAISE EXCEPTION 'deletion request requires a trusted user and reason';
    END IF;
    v_actor := NULLIF(current_setting('app.actor_id', true), '')::uuid;
    SELECT * INTO STRICT v_artifact FROM bridgeai_core.artifact_versions
     WHERE id = p_artifact_version_id FOR UPDATE;
    SELECT * INTO STRICT v_retention FROM bridgeai_audit.retention_executions
     WHERE id = p_retention_execution_id FOR UPDATE;
    IF v_artifact.organization_id::text <> current_setting('app.organization_id', true)
       OR v_artifact.project_id::text <> current_setting('app.project_id', true)
       OR v_retention.organization_id <> v_artifact.organization_id
       OR v_retention.project_id IS DISTINCT FROM v_artifact.project_id
       OR v_retention.target_type <> 'artifact_version'
       OR v_retention.target_id <> v_artifact.id::text
       OR v_retention.action <> 'delete_object'
       OR v_retention.status NOT IN ('pending', 'running')
       OR NOT v_retention.legal_hold_checked
       OR v_retention.shared_reference_count IS DISTINCT FROM 0
       OR v_retention.requested_by <> v_actor
       OR v_artifact.legal_hold
       OR (v_artifact.retention_until IS NOT NULL
           AND v_artifact.retention_until > clock_timestamp())
       OR v_artifact.status NOT IN ('archived', 'revoked') THEN
        RAISE EXCEPTION 'retention execution does not authorize this artifact deletion';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM bridgeai_identity.users AS u
        JOIN bridgeai_identity.organization_memberships AS om
          ON om.organization_id = u.organization_id AND om.user_id = u.id
        JOIN bridgeai_core.project_memberships AS pm
          ON pm.organization_id = u.organization_id AND pm.user_id = u.id
         AND pm.principal_type = 'user'
        WHERE u.id = v_actor AND u.organization_id = v_artifact.organization_id
          AND u.status = 'active' AND om.status = 'active' AND pm.status = 'active'
          AND pm.project_id = v_artifact.project_id
          AND pm.role_code IN ('project_admin', 'retention_operator')
          AND om.valid_from <= clock_timestamp()
          AND (om.valid_to IS NULL OR om.valid_to > clock_timestamp())
          AND pm.valid_from <= clock_timestamp()
          AND (pm.valid_to IS NULL OR pm.valid_to > clock_timestamp())
    ) THEN
        RAISE EXCEPTION 'actor is not authorized to request deletion';
    END IF;

    SELECT count(*) INTO v_reference_count FROM (
        SELECT 1 FROM bridgeai_inspection.dataset_artifacts
         WHERE artifact_version_id = v_artifact.id
        UNION ALL SELECT 1 FROM bridgeai_inspection.damage_evidence
         WHERE artifact_version_id = v_artifact.id
        UNION ALL SELECT 1 FROM bridgeai_knowledge.knowledge_sources
         WHERE source_artifact_version_id = v_artifact.id
        UNION ALL SELECT 1 FROM bridgeai_knowledge.document_versions
         WHERE source_artifact_version_id = v_artifact.id
        UNION ALL SELECT 1 FROM bridgeai_knowledge.citations
         WHERE source_artifact_version_id = v_artifact.id
        UNION ALL SELECT 1 FROM bridgeai_report.report_artifacts
         WHERE artifact_version_id = v_artifact.id
        UNION ALL SELECT 1 FROM bridgeai_audit.lineage_edges
         WHERE source_artifact_version_id = v_artifact.id
            OR target_artifact_version_id = v_artifact.id
        UNION ALL SELECT 1 FROM bridgeai_core.idempotency_requests
         WHERE result_artifact_version_id = v_artifact.id
    ) AS strong_references;
    IF v_reference_count <> 0 THEN
        RAISE EXCEPTION 'artifact version still has % strong references', v_reference_count;
    END IF;

    UPDATE bridgeai_core.artifact_versions
       SET status = 'deleting', deletion_requested_at = clock_timestamp(),
           updated_at = clock_timestamp(), updated_by = v_actor, version = version + 1
     WHERE id = v_artifact.id;
    UPDATE bridgeai_audit.retention_executions
       SET status = 'running', started_at = COALESCE(started_at, clock_timestamp()),
           version = version + 1 WHERE id = v_retention.id;
    v_outbox_id := bridgeai_core.enqueue_outbox_event(
        v_artifact.organization_id, v_artifact.project_id, 'artifact_version',
        v_artifact.id::text, v_artifact.revision_no::text, 'artifact.deletion_requested',
        '1', jsonb_build_object('artifact_id', v_artifact.artifact_id,
                                'artifact_version_id', v_artifact.id,
                                'retention_execution_id', v_retention.id,
                                'reason_code', left(p_reason, 200)),
        p_idempotency_key, 8
    );
    RETURN v_outbox_id;
END;
$$;

REVOKE ALL ON FUNCTION bridgeai_core.request_artifact_version_deletion(
    UUID, UUID, TEXT, TEXT
) FROM PUBLIC;

CREATE OR REPLACE FUNCTION bridgeai_core.has_controlled_retention_outbox_access(
    p_organization_id UUID, p_project_id UUID, p_aggregate_type TEXT,
    p_aggregate_id TEXT, p_event_type TEXT, p_event_schema_version TEXT,
    p_payload JSONB
) RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = pg_catalog, bridgeai_core, bridgeai_audit
AS $$
BEGIN
    RETURN (
    SELECT current_setting('app.actor_type', true) = 'user'
       AND bridgeai_core.has_organization_access(p_organization_id)
       AND p_project_id = NULLIF(current_setting('app.project_id', true), '')::uuid
       AND p_aggregate_type = 'artifact_version'
       AND p_event_type = 'artifact.deletion_requested'
       AND p_event_schema_version = '1'
       AND p_payload ->> 'artifact_version_id' = p_aggregate_id
       AND EXISTS (
           SELECT 1
           FROM bridgeai_audit.retention_executions AS re
           JOIN bridgeai_core.project_memberships AS pm
             ON pm.organization_id = re.organization_id
            AND pm.project_id = re.project_id
            AND pm.principal_type = 'user'
            AND pm.user_id = re.requested_by
           WHERE re.id = CASE
               WHEN p_payload ->> 'retention_execution_id' ~
                    '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
               THEN (p_payload ->> 'retention_execution_id')::uuid
               ELSE NULL
           END
             AND re.organization_id = p_organization_id
             AND re.project_id = p_project_id
             AND re.target_type = 'artifact_version'
             AND re.target_id = p_aggregate_id
             AND re.action = 'delete_object' AND re.status = 'running'
             AND re.requested_by = NULLIF(current_setting('app.actor_id', true), '')::uuid
             AND pm.role_code = 'retention_operator' AND pm.status = 'active'
             AND pm.valid_from <= statement_timestamp()
             AND (pm.valid_to IS NULL OR pm.valid_to > statement_timestamp())
       )
    );
END;
$$;

REVOKE ALL ON FUNCTION bridgeai_core.has_controlled_retention_outbox_access(
    UUID, UUID, TEXT, TEXT, TEXT, TEXT, JSONB
) FROM PUBLIC;
```

Outbox 幂等键同时冻结租户、聚合身份/版本、事件类型/模式版本、规范化 JSONB payload 和重试上限。同 key 同语义返回原 UUID；任一语义字段不同则明确冲突并回滚，包括两个并发事务竞争同 key 的情形。`SKIP LOCKED` 使并发 Worker 不会领取同一行；`attempt_count` 在 Claim 时递增，达到上限必然死信。重放函数只接受死信源行，完整复制聚合身份、事件类型/版本和 payload，只产生新 ID、新幂等键与服务器记录的重放人/时间。Lease Reaper 只把过期 `processing` 转为 `retry/dead_letter`，不执行业务补偿。核对任务按 `aggregate_type/id/version + event_type` 比较 PostgreSQL 权威状态、Outbox 终态和外部派生版本。

### 8.20.1 跨存储创建与激活

```text
1. 客户端向受控临时键写入 staged object
2. Artifact Worker 读回字节并校验 sha256/size/media_type；不匹配即隔离
3. PostgreSQL 事务：登记 verified Artifact version + 业务引用 + Outbox
4. 提交后 Worker 按 outbox_id 幂等执行对象激活/向量索引/缓存失效
5. PostgreSQL 短事务回写派生资源 ID、版本、哈希和 Outbox published
6. 核对通过后，只将权威记录切换为 active/ready
```

对象写成功而第 3 步失败时，临时键仍不可读，由 orphan 清理任务按哈希和宽限期删除；第 3 步成功而第 4/5 步失败时，保留权威记录与 Outbox 重试，不伪称索引已就绪。索引已写而回写失败时，Worker 用 outbox_id/派生版本查询并收敛，不再生成第二个 Point。

### 8.20.2 撤销、删除与墓碑

```text
1. PostgreSQL 事务：先 revoke/deleting，令新读取失败，写审计 + Outbox
2. Worker 删除 Qdrant Point/派生索引和 Redis 缓存
3. 核对法定保留、legal hold 和全部强/受控引用
4. 只在共享 Artifact 的合法引用计数为 0 时删除指定对象版本
5. PostgreSQL 保留无正文的 tombstone：对象 ID、原哈希、依据、执行人、时间和受影响引用
```

任意外部步骤失败都保持权威记录不可读，进入有界重试/死信并告警，不得因补偿失败自动恢复 `active`。数据库事务内禁止同步调用 Qdrant、MinIO、Redis 或模型；PostgreSQL 与这些系统是最终一致，不是分布式强一致事务。

## 8.21 RLS、数据库角色与权限隔离

数据库角色按职责分离，业务连接不使用表所有者、超级用户或 `BYPASSRLS` 角色。所有角色都是无登录组角色；具体 LOGIN 角色由部署层按环境授予，凭据不进入迁移文件。

| 角色 | 职责 | 明确边界 |
|---|---|---|
| `bridgeai_migration_owner` | 执行审核后的 DDL、持有 Schema/表 | `NOLOGIN`，不用于应用流量 |
| `bridgeai_app_rw` | 项目业务读写 | `NOBYPASSRLS`，不得 DDL，不得改审计/签名历史 |
| `bridgeai_readonly` | 受权项目查询/报表 | `NOBYPASSRLS`，不读安全证据原始字段 |
| `bridgeai_index_worker` | Claim Outbox，维护派生索引状态 | 无报告签发、用户或审计管理权 |
| `bridgeai_audit_writer` | 追加审计/访问/安全/血缘事件 | 只 `INSERT`，不 `UPDATE/DELETE` |
| `bridgeai_backup_restore` | 受控备份和恢复演练 | 无常驻 LOGIN，作业结束即撤销成员资格 |
| `bridgeai_break_glass` | 紧急运维 | 可 `BYPASSRLS` 但 `NOLOGIN`，双人授权、限时、全程审计 |

```sql
DO $$
DECLARE
    v_role TEXT;
BEGIN
    FOREACH v_role IN ARRAY ARRAY[
        'bridgeai_migration_owner', 'bridgeai_app_rw', 'bridgeai_readonly',
        'bridgeai_index_worker', 'bridgeai_audit_writer', 'bridgeai_backup_restore',
        'bridgeai_break_glass'
    ] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v_role) THEN
            EXECUTE format('CREATE ROLE %I', v_role);
        END IF;
    END LOOP;
END;
$$;

-- 每次迁移都纠正已存在角色，不把“仅首次创建”当作安全基线。
ALTER ROLE bridgeai_migration_owner NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE bridgeai_app_rw NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE bridgeai_readonly NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE bridgeai_index_worker NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE bridgeai_audit_writer NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE bridgeai_backup_restore NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION BYPASSRLS;
ALTER ROLE bridgeai_break_glass NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION BYPASSRLS;

ALTER TABLE bridgeai_report.reports OWNER TO bridgeai_migration_owner;
ALTER TABLE bridgeai_report.report_revisions OWNER TO bridgeai_migration_owner;
ALTER TABLE bridgeai_report.report_items OWNER TO bridgeai_migration_owner;
ALTER TABLE bridgeai_report.report_citations OWNER TO bridgeai_migration_owner;
ALTER TABLE bridgeai_report.report_artifacts OWNER TO bridgeai_migration_owner;
ALTER TABLE bridgeai_report.report_signatures OWNER TO bridgeai_migration_owner;
ALTER TABLE bridgeai_audit.audit_events OWNER TO bridgeai_migration_owner;
ALTER TABLE bridgeai_audit.audit_events_default OWNER TO bridgeai_migration_owner;
ALTER TABLE bridgeai_audit.data_access_events OWNER TO bridgeai_migration_owner;
ALTER TABLE bridgeai_audit.data_access_events_default OWNER TO bridgeai_migration_owner;
ALTER TABLE bridgeai_audit.security_events OWNER TO bridgeai_migration_owner;
ALTER TABLE bridgeai_audit.retention_executions OWNER TO bridgeai_migration_owner;
ALTER TABLE bridgeai_audit.lineage_edges OWNER TO bridgeai_migration_owner;
ALTER TABLE bridgeai_core.idempotency_requests OWNER TO bridgeai_migration_owner;
ALTER TABLE bridgeai_core.outbox_events OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_report.validate_report_signature()
    OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_report.validate_report_memory_item()
    OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_report.validate_report_citation()
    OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_core.register_idempotency_request(
    UUID, UUID, TEXT, TEXT, TEXT, TIMESTAMPTZ
) OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_report.compute_snapshot_manifest(UUID) OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_report.issue_report_revision(UUID) OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_report.withdraw_report_revision(UUID, TEXT) OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_report.assert_report_signature_state() OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_core.complete_idempotency_request(UUID, TEXT, TEXT, UUID, UUID)
    OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_core.fail_idempotency_request(UUID, TEXT, BOOLEAN)
    OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_core.outbox_event_semantic_sha256(
    UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB, INTEGER
) OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_core.enqueue_outbox_event(
    UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB, TEXT, INTEGER
) OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_core.claim_outbox_events(UUID, UUID, TEXT, INTEGER, INTERVAL)
    OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_core.ack_outbox_event(UUID, TEXT, UUID)
    OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_core.fail_outbox_event(UUID, TEXT, UUID, TEXT, TEXT, BOOLEAN)
    OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_core.reap_expired_outbox_events(UUID, UUID, INTEGER)
    OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_core.replay_dead_letter_event(UUID, TEXT)
    OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_core.request_artifact_version_deletion(UUID, UUID, TEXT, TEXT)
    OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_core.has_controlled_retention_outbox_access(
    UUID, UUID, TEXT, TEXT, TEXT, TEXT, JSONB
) OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_audit.event_details_are_safe(JSONB)
    OWNER TO bridgeai_migration_owner;

REVOKE ALL ON SCHEMA bridgeai_identity, bridgeai_core, bridgeai_asset,
    bridgeai_inspection, bridgeai_workflow, bridgeai_knowledge,
    bridgeai_memory, bridgeai_report, bridgeai_audit FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA bridgeai_report, bridgeai_audit FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA bridgeai_report, bridgeai_audit FROM PUBLIC;
REVOKE ALL ON FUNCTION bridgeai_core.register_idempotency_request(
    UUID, UUID, TEXT, TEXT, TEXT, TIMESTAMPTZ
), bridgeai_core.complete_idempotency_request(UUID, TEXT, TEXT, UUID, UUID),
   bridgeai_core.fail_idempotency_request(UUID, TEXT, BOOLEAN),
   bridgeai_core.outbox_event_semantic_sha256(
       UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB, INTEGER
   ),
   bridgeai_core.enqueue_outbox_event(
       UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB, TEXT, INTEGER
   ), bridgeai_core.claim_outbox_events(UUID, UUID, TEXT, INTEGER, INTERVAL),
   bridgeai_core.ack_outbox_event(UUID, TEXT, UUID),
   bridgeai_core.fail_outbox_event(UUID, TEXT, UUID, TEXT, TEXT, BOOLEAN),
   bridgeai_core.reap_expired_outbox_events(UUID, UUID, INTEGER),
   bridgeai_core.replay_dead_letter_event(UUID, TEXT),
   bridgeai_core.request_artifact_version_deletion(UUID, UUID, TEXT, TEXT)
FROM PUBLIC;

GRANT USAGE ON SCHEMA bridgeai_identity, bridgeai_core, bridgeai_inspection,
    bridgeai_workflow, bridgeai_knowledge, bridgeai_memory, bridgeai_report,
    bridgeai_audit TO bridgeai_migration_owner;
GRANT SELECT ON bridgeai_core.project_memberships,
    bridgeai_core.artifact_versions, bridgeai_identity.users,
    bridgeai_identity.service_principals,
    bridgeai_identity.organization_memberships, bridgeai_identity.organizations,
    bridgeai_inspection.dataset_artifacts, bridgeai_inspection.damage_evidence,
    bridgeai_knowledge.knowledge_sources, bridgeai_knowledge.document_versions,
    bridgeai_memory.memory_records,
    bridgeai_knowledge.citations, bridgeai_knowledge.publication_items
    TO bridgeai_migration_owner;
GRANT UPDATE (status, deletion_requested_at, updated_at, updated_by, version)
    ON bridgeai_core.artifact_versions TO bridgeai_migration_owner;
-- 在下文所有 RLS Policy 完成后才授予运行时权限。
```

认证网关在开始业务事务后使用 `set_config(..., true)`（等价于 `SET LOCAL`）写入组织、项目、actor 类型和 actor ID；值来自已验证会话/服务身份，绝不直接采信 API 请求字段。每次归还连接前必须 `ROLLBACK`，连接池 checkout 再执行 `RESET ALL`；缺少任一上下文时 Policy 默认拒绝。

```sql
BEGIN;
SELECT set_config('app.organization_id', $1, true);
SELECT set_config('app.project_id',      $2, true);
SELECT set_config('app.actor_type',      $3, true); -- user | service_principal
SELECT set_config('app.actor_id',        $4, true);
-- 业务 SQL
COMMIT;
```

```sql
CREATE OR REPLACE FUNCTION bridgeai_core.has_organization_access(
    p_organization_id UUID
) RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_core, bridgeai_identity
AS $$
    SELECT p_organization_id = NULLIF(current_setting('app.organization_id', true), '')::uuid
       AND EXISTS (
           SELECT 1 FROM bridgeai_identity.organizations AS o
           WHERE o.id = p_organization_id AND o.status = 'active'
       )
       AND (
           (current_setting('app.actor_type', true) = 'user' AND EXISTS (
               SELECT 1 FROM bridgeai_identity.users AS u
               JOIN bridgeai_identity.organization_memberships AS om
                 ON om.organization_id = u.organization_id AND om.user_id = u.id
               WHERE u.id = NULLIF(current_setting('app.actor_id', true), '')::uuid
                 AND u.organization_id = p_organization_id
                 AND u.status = 'active' AND om.status = 'active'
                 AND om.valid_from <= statement_timestamp()
                 AND (om.valid_to IS NULL OR om.valid_to > statement_timestamp())
           ))
           OR
           (current_setting('app.actor_type', true) = 'service_principal' AND EXISTS (
               SELECT 1 FROM bridgeai_identity.service_principals AS sp
               WHERE sp.id = NULLIF(current_setting('app.actor_id', true), '')::uuid
                 AND sp.organization_id = p_organization_id AND sp.status = 'active'
                 AND (sp.credential_expires_at IS NULL
                      OR sp.credential_expires_at > statement_timestamp())
           ))
       );
$$;

CREATE OR REPLACE FUNCTION bridgeai_core.has_project_access(
    p_organization_id UUID,
    p_project_id UUID,
    p_write BOOLEAN DEFAULT false
) RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_core, bridgeai_identity
AS $$
    SELECT bridgeai_core.has_organization_access(p_organization_id)
        AND p_project_id = NULLIF(current_setting('app.project_id', true), '')::uuid
        AND EXISTS (
            SELECT 1
            FROM bridgeai_core.project_memberships AS pm
            WHERE pm.organization_id = p_organization_id
              AND pm.project_id = p_project_id
              AND pm.status = 'active'
              AND pm.valid_from <= statement_timestamp()
              AND (pm.valid_to IS NULL OR pm.valid_to > statement_timestamp())
              AND (
                  (NULLIF(current_setting('app.actor_type', true), '') = 'user'
                   AND pm.principal_type = 'user'
                   AND pm.user_id = NULLIF(current_setting('app.actor_id', true), '')::uuid)
                  OR
                  (NULLIF(current_setting('app.actor_type', true), '') = 'service_principal'
                   AND pm.principal_type = 'service_principal'
                   AND pm.service_principal_id =
                       NULLIF(current_setting('app.actor_id', true), '')::uuid)
              )
              AND (NOT p_write OR pm.role_code IN (
                  'project_admin', 'inspector', 'reviewer', 'report_issuer', 'service_writer'
              ))
        );
$$;

ALTER FUNCTION bridgeai_core.has_project_access(UUID, UUID, BOOLEAN)
    OWNER TO bridgeai_migration_owner;
ALTER FUNCTION bridgeai_core.has_organization_access(UUID)
    OWNER TO bridgeai_migration_owner;
REVOKE ALL ON FUNCTION bridgeai_core.has_project_access(UUID, UUID, BOOLEAN) FROM PUBLIC;
REVOKE ALL ON FUNCTION bridgeai_core.has_organization_access(UUID) FROM PUBLIC;
ALTER TABLE bridgeai_core.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_core.projects FORCE ROW LEVEL SECURITY;
CREATE POLICY projects_org_isolation ON bridgeai_core.projects
    USING (
        organization_id = NULLIF(current_setting('app.organization_id', true), '')::uuid
        AND bridgeai_core.has_project_access(organization_id, id, false)
    )
    WITH CHECK (
        organization_id = NULLIF(current_setting('app.organization_id', true), '')::uuid
        AND bridgeai_core.has_project_access(organization_id, id, true)
    );

ALTER TABLE bridgeai_report.reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_report.reports FORCE ROW LEVEL SECURITY;
CREATE POLICY reports_project_isolation ON bridgeai_report.reports
    USING (bridgeai_core.has_project_access(organization_id, project_id, false))
    WITH CHECK (bridgeai_core.has_project_access(organization_id, project_id, true));

ALTER TABLE bridgeai_report.report_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_report.report_revisions FORCE ROW LEVEL SECURITY;
CREATE POLICY report_revisions_project_isolation ON bridgeai_report.report_revisions
    USING (bridgeai_core.has_project_access(organization_id, project_id, false))
    WITH CHECK (bridgeai_core.has_project_access(organization_id, project_id, true));

ALTER TABLE bridgeai_report.report_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_report.report_items FORCE ROW LEVEL SECURITY;
CREATE POLICY report_items_project_isolation ON bridgeai_report.report_items
    USING (bridgeai_core.has_project_access(organization_id, project_id, false))
    WITH CHECK (bridgeai_core.has_project_access(organization_id, project_id, true));

ALTER TABLE bridgeai_report.report_citations ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_report.report_citations FORCE ROW LEVEL SECURITY;
CREATE POLICY report_citations_project_isolation ON bridgeai_report.report_citations
    USING (bridgeai_core.has_project_access(organization_id, project_id, false))
    WITH CHECK (bridgeai_core.has_project_access(organization_id, project_id, true));

ALTER TABLE bridgeai_report.report_artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_report.report_artifacts FORCE ROW LEVEL SECURITY;
CREATE POLICY report_artifacts_project_isolation ON bridgeai_report.report_artifacts
    USING (bridgeai_core.has_project_access(organization_id, project_id, false))
    WITH CHECK (bridgeai_core.has_project_access(organization_id, project_id, true));

ALTER TABLE bridgeai_report.report_signatures ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_report.report_signatures FORCE ROW LEVEL SECURITY;
CREATE POLICY report_signatures_project_isolation ON bridgeai_report.report_signatures
    USING (bridgeai_core.has_project_access(organization_id, project_id, false))
    WITH CHECK (bridgeai_core.has_project_access(organization_id, project_id, true));

ALTER TABLE bridgeai_core.idempotency_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_core.idempotency_requests FORCE ROW LEVEL SECURITY;
CREATE POLICY idempotency_requests_project_isolation
    ON bridgeai_core.idempotency_requests
    USING (bridgeai_core.has_project_access(organization_id, project_id, false))
    WITH CHECK (bridgeai_core.has_project_access(organization_id, project_id, true));

ALTER TABLE bridgeai_core.outbox_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_core.outbox_events FORCE ROW LEVEL SECURITY;
CREATE POLICY outbox_events_project_worker ON bridgeai_core.outbox_events
    USING (
        bridgeai_core.has_project_access(organization_id, project_id, true)
        OR bridgeai_core.has_controlled_retention_outbox_access(
            organization_id, project_id, aggregate_type, aggregate_id,
            event_type, event_schema_version, payload
        )
    )
    WITH CHECK (
        bridgeai_core.has_project_access(organization_id, project_id, true)
        OR bridgeai_core.has_controlled_retention_outbox_access(
            organization_id, project_id, aggregate_type, aggregate_id,
            event_type, event_schema_version, payload
        )
    );

ALTER TABLE bridgeai_audit.audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_audit.audit_events FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_events_append_scope ON bridgeai_audit.audit_events
    USING (CASE WHEN project_id IS NULL
                THEN bridgeai_core.has_organization_access(organization_id)
                ELSE bridgeai_core.has_project_access(organization_id, project_id, false) END)
    WITH CHECK (CASE WHEN project_id IS NULL
                     THEN bridgeai_core.has_organization_access(organization_id)
                     ELSE bridgeai_core.has_project_access(organization_id, project_id, false) END);

ALTER TABLE bridgeai_audit.audit_events_default ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_audit.audit_events_default FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_events_default_scope ON bridgeai_audit.audit_events_default
    USING (CASE WHEN project_id IS NULL
                THEN bridgeai_core.has_organization_access(organization_id)
                ELSE bridgeai_core.has_project_access(organization_id, project_id, false) END)
    WITH CHECK (CASE WHEN project_id IS NULL
                     THEN bridgeai_core.has_organization_access(organization_id)
                     ELSE bridgeai_core.has_project_access(organization_id, project_id, false) END);

ALTER TABLE bridgeai_audit.data_access_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_audit.data_access_events FORCE ROW LEVEL SECURITY;
CREATE POLICY data_access_events_scope ON bridgeai_audit.data_access_events
    USING (CASE WHEN project_id IS NULL
                THEN bridgeai_core.has_organization_access(organization_id)
                ELSE bridgeai_core.has_project_access(organization_id, project_id, false) END)
    WITH CHECK (CASE WHEN project_id IS NULL
                     THEN bridgeai_core.has_organization_access(organization_id)
                     ELSE bridgeai_core.has_project_access(organization_id, project_id, false) END);

ALTER TABLE bridgeai_audit.data_access_events_default ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_audit.data_access_events_default FORCE ROW LEVEL SECURITY;
CREATE POLICY data_access_events_default_scope ON bridgeai_audit.data_access_events_default
    USING (CASE WHEN project_id IS NULL
                THEN bridgeai_core.has_organization_access(organization_id)
                ELSE bridgeai_core.has_project_access(organization_id, project_id, false) END)
    WITH CHECK (CASE WHEN project_id IS NULL
                     THEN bridgeai_core.has_organization_access(organization_id)
                     ELSE bridgeai_core.has_project_access(organization_id, project_id, false) END);

ALTER TABLE bridgeai_audit.security_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_audit.security_events FORCE ROW LEVEL SECURITY;
CREATE POLICY security_events_scope ON bridgeai_audit.security_events
    USING (CASE WHEN project_id IS NULL
                THEN bridgeai_core.has_organization_access(organization_id)
                ELSE bridgeai_core.has_project_access(organization_id, project_id, false) END)
    WITH CHECK (CASE WHEN project_id IS NULL
                     THEN bridgeai_core.has_organization_access(organization_id)
                     ELSE bridgeai_core.has_project_access(organization_id, project_id, false) END);

ALTER TABLE bridgeai_audit.retention_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_audit.retention_executions FORCE ROW LEVEL SECURITY;
CREATE POLICY retention_executions_scope ON bridgeai_audit.retention_executions
    USING (CASE WHEN project_id IS NULL
                THEN bridgeai_core.has_organization_access(organization_id)
                ELSE bridgeai_core.has_project_access(organization_id, project_id, false) END)
    WITH CHECK (CASE WHEN project_id IS NULL
                     THEN bridgeai_core.has_organization_access(organization_id)
                     ELSE bridgeai_core.has_project_access(organization_id, project_id, true)
                       OR (
                           -- 仅为受控 Artifact 删除的 retention 状态推进开精确通道；
                           -- retention_operator 不加入通用写角色白名单。
                           bridgeai_core.has_organization_access(organization_id)
                           AND project_id = NULLIF(
                               current_setting('app.project_id', true), ''
                           )::uuid
                           AND current_setting('app.actor_type', true) = 'user'
                           AND EXISTS (
                               SELECT 1 FROM bridgeai_core.project_memberships AS pm
                               WHERE pm.organization_id = retention_executions.organization_id
                                 AND pm.project_id = retention_executions.project_id
                                 AND pm.principal_type = 'user'
                                 AND pm.user_id = NULLIF(
                                     current_setting('app.actor_id', true), ''
                                 )::uuid
                                 AND pm.role_code = 'retention_operator'
                                 AND pm.status = 'active'
                                 AND pm.valid_from <= statement_timestamp()
                                 AND (pm.valid_to IS NULL
                                      OR pm.valid_to > statement_timestamp())
                           )
                       ) END);

ALTER TABLE bridgeai_audit.lineage_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_audit.lineage_edges FORCE ROW LEVEL SECURITY;
CREATE POLICY lineage_edges_scope ON bridgeai_audit.lineage_edges
    USING (bridgeai_core.has_project_access(organization_id, project_id, false))
    WITH CHECK (bridgeai_core.has_project_access(organization_id, project_id, true));

-- Policy 已全部存在；此后才授予表和受控函数权限。
GRANT USAGE ON SCHEMA bridgeai_identity, bridgeai_core, bridgeai_inspection,
    bridgeai_workflow, bridgeai_knowledge, bridgeai_memory, bridgeai_report
    TO bridgeai_app_rw, bridgeai_readonly;
GRANT USAGE ON SCHEMA bridgeai_core, bridgeai_report
    TO bridgeai_index_worker;
GRANT USAGE ON SCHEMA bridgeai_identity, bridgeai_core, bridgeai_audit
    TO bridgeai_audit_writer;
GRANT EXECUTE ON FUNCTION bridgeai_core.has_project_access(UUID, UUID, BOOLEAN),
    bridgeai_core.has_organization_access(UUID)
    TO bridgeai_app_rw, bridgeai_readonly, bridgeai_index_worker, bridgeai_audit_writer;

GRANT SELECT, INSERT ON bridgeai_report.reports TO bridgeai_app_rw;
GRANT UPDATE (report_type, title, updated_at, updated_by, version)
    ON bridgeai_report.reports TO bridgeai_app_rw;
GRANT SELECT, INSERT, UPDATE ON bridgeai_report.report_revisions,
    bridgeai_report.report_items, bridgeai_report.report_citations,
    bridgeai_report.report_artifacts TO bridgeai_app_rw;
GRANT SELECT ON bridgeai_report.report_signatures TO bridgeai_app_rw;
GRANT SELECT ON ALL TABLES IN SCHEMA bridgeai_report TO bridgeai_readonly;

REVOKE INSERT, UPDATE, DELETE ON bridgeai_report.report_signatures
    FROM bridgeai_app_rw, bridgeai_index_worker, bridgeai_audit_writer;
REVOKE UPDATE (status, current_revision_id, current_revision_no)
    ON bridgeai_report.reports FROM bridgeai_app_rw;
REVOKE UPDATE (
    status, legal_hold, retention_until, deletion_requested_at, deleted_at
) ON bridgeai_core.artifact_versions
    FROM bridgeai_app_rw, bridgeai_index_worker, bridgeai_audit_writer;
REVOKE ALL ON bridgeai_core.idempotency_requests, bridgeai_core.outbox_events
    FROM bridgeai_app_rw, bridgeai_index_worker, bridgeai_audit_writer;

GRANT INSERT (
    id, organization_id, project_id, actor_user_id, service_principal_id,
    action, object_schema, object_table, object_id, object_version, result,
    before_sha256, after_sha256, request_id, trace_id, occurred_at,
    policy_version, reason_code, details
) ON bridgeai_audit.audit_events TO bridgeai_audit_writer;
GRANT INSERT (
    id, organization_id, project_id, actor_user_id, service_principal_id,
    resource_type, resource_id, access_action, purpose_code, result,
    row_count, bytes_returned, request_id, trace_id, occurred_at,
    policy_version, details
) ON bridgeai_audit.data_access_events TO bridgeai_audit_writer;
GRANT INSERT (
    id, organization_id, project_id, audit_event_id, audit_server_recorded_at,
    actor_user_id, service_principal_id, event_type, severity, detection_source,
    resource_type, resource_id, disposition, request_id, trace_id, occurred_at,
    evidence_sha256, details
) ON bridgeai_audit.security_events TO bridgeai_audit_writer;
GRANT INSERT (
    id, organization_id, project_id, source_type, source_id, source_version,
    source_sha256, source_artifact_id, source_artifact_version_id,
    target_type, target_id, target_version, target_sha256,
    target_artifact_id, target_artifact_version_id, relation_type,
    transformation_code, transformation_version, workflow_run_id,
    workflow_task_id, occurred_at, created_by_service_id
) ON bridgeai_audit.lineage_edges TO bridgeai_audit_writer;

GRANT EXECUTE ON FUNCTION bridgeai_report.issue_report_revision(UUID),
    bridgeai_report.withdraw_report_revision(UUID, TEXT),
    bridgeai_core.register_idempotency_request(UUID, UUID, TEXT, TEXT, TEXT, TIMESTAMPTZ),
    bridgeai_core.complete_idempotency_request(UUID, TEXT, TEXT, UUID, UUID),
    bridgeai_core.fail_idempotency_request(UUID, TEXT, BOOLEAN),
    bridgeai_core.enqueue_outbox_event(
        UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB, TEXT, INTEGER
    ), bridgeai_core.replay_dead_letter_event(UUID, TEXT),
    bridgeai_core.request_artifact_version_deletion(UUID, UUID, TEXT, TEXT)
    TO bridgeai_app_rw;
GRANT EXECUTE ON FUNCTION
    bridgeai_core.claim_outbox_events(UUID, UUID, TEXT, INTEGER, INTERVAL),
    bridgeai_core.ack_outbox_event(UUID, TEXT, UUID),
    bridgeai_core.fail_outbox_event(UUID, TEXT, UUID, TEXT, TEXT, BOOLEAN),
    bridgeai_core.reap_expired_outbox_events(UUID, UUID, INTEGER)
    TO bridgeai_index_worker;
GRANT EXECUTE ON FUNCTION bridgeai_audit.event_details_are_safe(JSONB)
    TO bridgeai_audit_writer;
```

本节新增 13 个逻辑租户表（含两个分区父表），物理目录中为 15 个关系（另含两个 default partition）；全部在授权前 `ENABLE` + `FORCE ROW LEVEL SECURITY` 并有可执行 Policy。`retention_operator` 只在 `retention_executions` 的受控状态推进 Policy 中获得精确通道，不进入通用 `p_write` 白名单，也不获得底表权限。应以 `pg_class.relrowsecurity/relforcerowsecurity`、`pg_policy`、`pg_roles` 和 `information_schema.role_table_grants` 验收，不以 SQL 文本或逻辑/物理数量混报代替目录证据。

任何 `SECURITY DEFINER` 函数都必须由不登录所有者持有，固定只含 `pg_catalog` 和所需 Schema 的 `search_path`，所有对象使用 Schema 限定名，并在授予指定角色前先 `REVOKE ... FROM PUBLIC`。不得在函数中拼接请求提供的 SQL、表名或 `search_path`。

## 8.22 索引、查询与空间检索优化

### 8.22.1 索引选择矩阵

索引以已登记的查询形状为起点，不以“字段重要”为理由遍历建索引。主键和 `UNIQUE` 约束已有隐式 B-tree，不重复建等价索引；PostgreSQL 不自动为外键引用列建索引，只有父行删除／更新或子表联接的真实路径需要时才补齐。复合索引先放组织、项目等值边界，再放业务等值、范围和排序列。

| 查询路径 | 谓词／排序 | 决策 | 写放大控制 |
|---|---|---|---|
| 项目任务列表 | `organization_id, project_id, status` 等值，`updated_at DESC, id DESC` seek | 新增 `ix_workflow_tasks_scope_status_seek_v2` | 既有索引缺少同时间戳的 `id` tie-break；新索引通过观察窗后再决定是否替换旧索引 |
| 多期病害 | 项目／资产／稳定病害，按 `observed_at` | 复用 `ix_damage_observations_entity_time`、`ix_damage_measurements_trend` | 部分索引只收 confirmed 关联；current revision 由既有组合唯一索引点查 |
| 当前报告版本 | 项目、`report_code`，再按 current pointer 联接 | 复用 `uq_reports_project_code`、`uq_report_revisions_id_scope_report_revision` | 两步均是唯一点查，不再建等价 current 索引 |
| 待复核 | 项目、`pending/claimed`、priority/due time | 复用 `ix_workflow_reviews_pending` | 只有热集合入索引；领取仍由受控写入、锁和 lease 完成 |
| Outbox Claim | 租户／项目内 `pending/retry`、到期时间，按 available/created/id | 新增 `ix_outbox_events_claim_scope_v2` | 组织、项目必须作为前导列，避免每个 Worker 扫描其他租户的热集合 |
| 空间范围 | 组织／项目／资产 + `&&` + `ST_Intersects` | 复用 scope B-tree 与 `ix_spatial_locations_geom_4490` GiST | 标准列为 `geom_4490 geometry(Geometry,4490)`；不以 EPSG:4490 角度计算米制距离 |
| 名称模糊查找 | 项目内 `lower(assets.name) % lower(:query)` | 新增 `pg_trgm` GIN | 只覆盖有明确入口的资产名；构件别名先用精确 `alias_code`，不为全部 text 建 Trigram |
| 顺序追加事件 | 月分区内时间范围 | 大分区才启用 BRIN | 只用于与物理写入顺序高相关的 `occurred_at/server_recorded_at`；相关性下降或分区很小时不建 |
| JSONB 条件 | 版本化且高频的单一标量路径 | V1 allowlist 为空，拒绝通用 GIN | `status/event_type/aggregate_id` 已结构化；只有查询登记、JSON Schema、选择率和写成本均通过后才引入有限表达式索引 |

空间索引的唯一基线仍是 8.11 已定义的 `ON bridgeai_asset.spatial_locations USING GIST (geom_4490)`，本节不重复创建。正式环境必须在含 PostGIS 的 PostgreSQL 16+ 上对它和 Q6 执行验收；未安装 PostGIS 的环境只能报告静态校验结果。

外键父端的唯一索引不解决子端反向检索。报告按 Workflow run 回溯和复核按 node execution 回溯增加下列非等价子端索引：

```sql
-- 扩展由迁移所有者安装；生产 CONCURRENTLY DDL 按 8.24 拆为非事务迁移。
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_assets_name_trgm
    ON bridgeai_asset.assets USING GIN (lower(name) gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_workflow_reviews_node_execution_fk
    ON bridgeai_workflow.workflow_reviews
       (node_execution_id, organization_id, project_id, task_id, run_id)
    WHERE node_execution_id IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_report_revisions_workflow_run_fk
    ON bridgeai_report.report_revisions
       (workflow_run_id, organization_id, project_id, workflow_task_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_workflow_tasks_scope_status_seek_v2
    ON bridgeai_workflow.workflow_tasks
       (organization_id, project_id, status, updated_at DESC, id DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_outbox_events_claim_scope_v2
    ON bridgeai_core.outbox_events
       (organization_id, project_id, available_at, created_at, id)
    WHERE status IN ('pending', 'retry');
```

`ix_workflow_tasks_scope_status_seek_v2` 与 `ix_outbox_events_claim_scope_v2` 先以新名称并行上线；只有原样查询合同在完整观察窗持续命中新索引、写放大可接受且旧索引无其他登记消费者时，才在独立非事务 revision 中 `DROP INDEX CONCURRENTLY` 旧索引。不得以改名或同名 `IF NOT EXISTS` 跳过有效性检查。

fresh install 可在业务写入前直接于分区父表建 BRIN；PostgreSQL 会为已有及后续新建分区维护匹配子索引。在线父表不能使用 `CREATE INDEX CONCURRENTLY`：须先逐个子表并发建索引，再将子索引 `ATTACH PARTITION` 到父索引。

```sql
CREATE INDEX IF NOT EXISTS ix_workflow_events_occurred_brin
    ON bridgeai_workflow.workflow_events
    USING BRIN (occurred_at) WITH (pages_per_range = 32, autosummarize = on);
CREATE INDEX IF NOT EXISTS ix_audit_events_recorded_brin
    ON bridgeai_audit.audit_events
    USING BRIN (server_recorded_at) WITH (pages_per_range = 32, autosummarize = on);
CREATE INDEX IF NOT EXISTS ix_data_access_events_recorded_brin
    ON bridgeai_audit.data_access_events
    USING BRIN (server_recorded_at) WITH (pages_per_range = 32, autosummarize = on);
```

在线已有分区不能执行上面的父表 DDL，也不能对父表使用 `CONCURRENTLY`。以 `workflow_events` 已有 `2026_08` 和 DEFAULT 子表为例，完整在线链为：先建立仅含目录定义的父索引，再在事务外逐子表并发建同定义索引，最后短事务逐一 ATTACH；实际迁移必须从 `pg_partition_tree()` 枚举**全部**叶子，包括 DEFAULT，不能只执行示例中的两个子表。

```sql
-- 1. 短事务；ON ONLY 不扫描子表，父索引在所有叶子 ATTACH 前保持 invalid。
CREATE INDEX ix_workflow_events_occurred_brin_v2
    ON ONLY bridgeai_workflow.workflow_events
    USING BRIN (occurred_at) WITH (pages_per_range = 32, autosummarize = on);

-- 2. 每条都在独立 autocommit 连接执行，不得位于事务块。
CREATE INDEX CONCURRENTLY ix_workflow_events_2026_08_occurred_brin_v2
    ON bridgeai_workflow.workflow_events_2026_08
    USING BRIN (occurred_at) WITH (pages_per_range = 32, autosummarize = on);
CREATE INDEX CONCURRENTLY ix_workflow_events_default_occurred_brin_v2
    ON bridgeai_workflow.workflow_events_default
    USING BRIN (occurred_at) WITH (pages_per_range = 32, autosummarize = on);

-- 3. 短事务；对枚举出的每个叶子重复 ATTACH。
ALTER INDEX bridgeai_workflow.ix_workflow_events_occurred_brin_v2
    ATTACH PARTITION bridgeai_workflow.ix_workflow_events_2026_08_occurred_brin_v2;
ALTER INDEX bridgeai_workflow.ix_workflow_events_occurred_brin_v2
    ATTACH PARTITION bridgeai_workflow.ix_workflow_events_default_occurred_brin_v2;

-- 4. 只有全部叶子都已附着时父索引才应 valid；否则阻断发布。
SELECT indexrelid::regclass AS index_name, indisvalid, indisready
FROM pg_index
WHERE indexrelid = 'bridgeai_workflow.ix_workflow_events_occurred_brin_v2'::regclass;
```

`audit_events/server_recorded_at` 与 `data_access_events/server_recorded_at` 使用同一 `ON ONLY → child CONCURRENTLY → ALTER INDEX ... ATTACH PARTITION` 模板。新增月分区时必须先为其创建并附着匹配子索引，或在父索引已 valid 时由 `CREATE TABLE ... PARTITION OF` 自动生成；任何叶子缺失都会使父索引 invalid。

### 8.22.2 真实查询合同

应用必须显式传入组织／项目边界，不能依赖 RLS 为遗漏谓词“补滤”。

```sql
-- Q1：项目任务列表，使用稳定 seek cursor 而非深 OFFSET。
SELECT id, thread_id, task_type, status, current_node, progress,
       requested_at, updated_at, version
FROM bridgeai_workflow.workflow_tasks
WHERE organization_id = :organization_id
  AND project_id = :project_id
  AND status = :status
  AND (updated_at, id) < (:cursor_updated_at, :cursor_id)
ORDER BY updated_at DESC, id DESC
LIMIT :page_size;

-- Q2：多期病害的当前 confirmed 修订。
SELECT o.id AS observation_id, o.observed_at, o.evolution_state,
       r.id AS revision_id, r.revision_no, r.damage_type_code,
       r.severity_code, r.risk_level, r.confidence
FROM bridgeai_inspection.damage_observations AS o
JOIN bridgeai_inspection.damage_revisions AS r
  ON (r.id, r.organization_id, r.project_id, r.observation_id, r.revision_no)
   = (o.current_revision_id, o.organization_id, o.project_id, o.id,
      o.current_revision_no)
WHERE o.organization_id = :organization_id
  AND o.project_id = :project_id
  AND o.asset_id = :asset_id
  AND o.damage_entity_id = :damage_entity_id
  AND o.association_status = 'confirmed'
  AND o.status = 'confirmed'
  AND r.status = 'confirmed'
ORDER BY o.observed_at, o.id;

-- Q3：通过真实 current pointer 取当前报告修订。
SELECT p.id, p.report_code, p.status, r.id AS revision_id, r.revision_no,
       r.content_sha256, r.snapshot_manifest_sha256
FROM bridgeai_report.reports AS p
JOIN bridgeai_report.report_revisions AS r
  ON (r.id, r.organization_id, r.project_id, r.report_id, r.revision_no)
   = (p.current_revision_id, p.organization_id, p.project_id, p.id,
      p.current_revision_no)
WHERE p.organization_id = :organization_id
  AND p.project_id = :project_id
  AND p.report_code = :report_code;

-- Q4：待复核列表；状态改变另由带 lease 的受控写入完成。
SELECT id, task_id, run_id, node_execution_id, review_type,
       priority, title, due_at, created_at
FROM bridgeai_workflow.workflow_reviews
WHERE organization_id = :organization_id
  AND project_id = :project_id
  AND status IN ('pending', 'claimed')
ORDER BY CASE priority
             WHEN 'critical' THEN 4 WHEN 'high' THEN 3
             WHEN 'normal' THEN 2 WHEN 'low' THEN 1
         END DESC,
         due_at NULLS LAST, id
LIMIT :page_size;

-- Q5：Outbox 候选；实际 Worker 调用 8.20 claim_outbox_events()。
SELECT id
FROM bridgeai_core.outbox_events
WHERE organization_id = :organization_id
  AND project_id = :project_id
  AND status IN ('pending', 'retry')
  AND available_at <= clock_timestamp()
  AND attempt_count < max_attempts
ORDER BY available_at, created_at, id
FOR UPDATE SKIP LOCKED
LIMIT :claim_limit;

-- Q6：EPSG:4490 范围查询，先包围盒再精确拓扑。
WITH query_area AS (SELECT ST_GeomFromText(:query_wkt, 4490) AS geom)
SELECT sl.id, sl.asset_id, sl.component_id, sl.location_kind, sl.geom_4490
FROM bridgeai_asset.spatial_locations AS sl
CROSS JOIN query_area AS qa
WHERE sl.organization_id = :organization_id
  AND sl.project_id = :project_id
  AND sl.asset_id = :asset_id
  AND sl.geom_4490 && qa.geom
  AND ST_Intersects(sl.geom_4490, qa.geom);
```

Trigram 同样不得跨项目搜索：

```sql
SELECT id, asset_code, name, similarity(lower(name), lower(:query)) AS score
FROM bridgeai_asset.assets
WHERE organization_id = :organization_id
  AND project_id = :project_id
  AND lower(name) % lower(:query)
ORDER BY score DESC, id
LIMIT 20;
```

### 8.22.3 `EXPLAIN` 验收与索引生命周期

索引创建成功不等于查询达标。Q1—Q6 每条关键查询都必须留存 query ID/SQL hash、应用与 Schema 版本、参数类型和脱敏参数；总行数、租户行数、状态分布、月分区大小和倾斜；PostgreSQL 小版本、实例规格、规划参数、并发数，以及冷、热缓存各一轮。

验收保存 `EXPLAIN (ANALYZE, BUFFERS, WAL, SETTINGS, VERBOSE)` 全文，包括实际／估算行、loops、shared hit/read/dirtied、temp I/O 和 WAL。p50/p95/p99、吞吐、超时率和最大扫描量由容量测试按目标硬件批准；本章不伪造脱离环境的毫秒门限。

```sql
ANALYZE bridgeai_workflow.workflow_tasks;
EXPLAIN (ANALYZE, BUFFERS, WAL, SETTINGS, VERBOSE)
SELECT id, thread_id, task_type, status, current_node, progress,
       requested_at, updated_at, version
FROM bridgeai_workflow.workflow_tasks
WHERE organization_id = :organization_id
  AND project_id = :project_id
  AND status = :status
  AND (updated_at, id) < (:cursor_updated_at, :cursor_id)
ORDER BY updated_at DESC, id DESC
LIMIT :page_size;
```

Q1 必须另有至少 100,000 行共享同一 `updated_at` 的 tie-break fixture；验收计划应直接使用 `ix_workflow_tasks_scope_status_seek_v2`，不得出现为了 LIMIT 而扫描／排序整个同时间戳集合。Q5 使用至少 100,000 条其他租户到期事件与目标租户小热集，计划必须以 `ix_outbox_events_claim_scope_v2` 的组织／项目前导条件定位，`Rows Removed by Filter` 不得随其他租户积压线性增长。

验收须解释分区剪枝、计划节点和读块，不强制所有查询都是 Index Scan：小表或低选择率参数使用 Seq Scan 可以正确。当实际／估算行持续相差一个数量级时，先检查倾斜、`ANALYZE` 和扩展统计。覆盖索引的 `INCLUDE` 只放稳定、小型、高频返回列；JSONB、正文和高频更新列默认不放入。

每个新索引上线前后比较表／索引字节数、TPS、WAL、checkpoint 和 `pg_stat_user_indexes.idx_scan`。连续两个完整观察周期无读取且无约束用途的索引，经 query owner 确认后才下线。分区事件表同时观察 `n_dead_tup`、autovacuum/autoanalyze、BRIN 时间相关性和默认分区积压；高频 UPDATE 表与追加事件分区分别调参，不能用一组全局值覆盖所有表。

## 8.23 分区、归档、保留与删除传播

### 8.23.1 月分区边界

首期只分区高增长时间序列。`assets`、`projects`、`damage_entities`、`damage_observations`、`reports` 及其修订表不分区；强外键、current pointer 和不可变历史优先于时间裁剪。

| 表 | RANGE 键 | 当前形态与动作 |
|---|---|---|
| `workflow_events` | `occurred_at` | 8.15 已是父表和 `workflow_events_default`；只增量建月分区，不重建父表 |
| `audit_events` | `server_recorded_at` | 8.19 已是父表和 `audit_events_default`；不使用客户端 `occurred_at` 路由 |
| `data_access_events` | `server_recorded_at` | 同上 |
| `workflow_node_executions` | `created_at` | 当前非分区；必须走 8.23.4/8.24 的兼容影子迁移，不能一句 `ALTER TABLE` 原地修改 |

边界统一按 UTC 半开区间 `[from,to)`，分区名月份也按 UTC。新环境／维护窗口的 2026-08 示例：

```sql
CREATE TABLE bridgeai_workflow.workflow_events_2026_08
    PARTITION OF bridgeai_workflow.workflow_events
    FOR VALUES FROM ('2026-08-01 00:00:00+00') TO ('2026-09-01 00:00:00+00');
CREATE TABLE bridgeai_audit.audit_events_2026_08
    PARTITION OF bridgeai_audit.audit_events
    FOR VALUES FROM ('2026-08-01 00:00:00+00') TO ('2026-09-01 00:00:00+00');
CREATE TABLE bridgeai_audit.data_access_events_2026_08
    PARTITION OF bridgeai_audit.data_access_events
    FOR VALUES FROM ('2026-08-01 00:00:00+00') TO ('2026-09-01 00:00:00+00');
```

运维任务每天检查并至少预建“当月 + 下两月”。经父表访问使用父表 RLS；父表权限不会变成对子表的直接访问权限，因此默认不向应用角色 grant 子表。若特权运维必须直读子表，须对子表单独 `ENABLE/FORCE ROW LEVEL SECURITY`、建等价 Policy 并只 grant 该运维角色。新分区 owner、RLS、Policy、grant、行级触发器和索引继承均以系统目录验收。

### 8.23.2 默认分区、迟到数据与 ATTACH

DEFAULT 分区是防止路由故障丢数的短时护栏，不是归档区。下列查询每 5 分钟执行；任一计数非 0 立即告警：

```sql
SELECT 'workflow_events_default' AS partition_name,
       count(*) AS row_count, min(occurred_at) AS min_key, max(occurred_at) AS max_key
FROM bridgeai_workflow.workflow_events_default
UNION ALL
SELECT 'audit_events_default', count(*), min(server_recorded_at), max(server_recorded_at)
FROM bridgeai_audit.audit_events_default
UNION ALL
SELECT 'data_access_events_default', count(*), min(server_recorded_at), max(server_recorded_at)
FROM bridgeai_audit.data_access_events_default
UNION ALL
SELECT 'workflow_node_executions_partitioned_default', count(*), min(created_at), max(created_at)
FROM bridgeai_workflow.workflow_node_executions_partitioned_default;
```

shadow expand 完成后，发布门禁用下列目录查询确认当前 UTC 月至未来 62 天覆盖的每个月均为真实叶子分区，且 `actual_bound` 等于同一行计算出的 UTC 月半开 `expected_bound`；异常结果必须为 0 行。migration manifest 另保存去掉末尾 `WHERE` 的完整 `catalog` 结果，不能只凭关系名宣称完整。

```sql
WITH parents(schema_name, partition_prefix, parent_rel) AS (
    VALUES
      ('bridgeai_workflow', 'workflow_events',
       to_regclass('bridgeai_workflow.workflow_events')),
      ('bridgeai_workflow', 'workflow_node_executions_partitioned',
       to_regclass('bridgeai_workflow.workflow_node_executions_partitioned')),
      ('bridgeai_audit', 'audit_events',
       to_regclass('bridgeai_audit.audit_events')),
      ('bridgeai_audit', 'data_access_events',
       to_regclass('bridgeai_audit.data_access_events'))
), expected AS (
    SELECT p.*, month_start,
           to_regclass(format(
               '%I.%I_%s', p.schema_name, p.partition_prefix,
               to_char(month_start, 'YYYY_MM')
           )) AS expected_rel,
           format(
               'FOR VALUES FROM (%L) TO (%L)',
               month_start AT TIME ZONE 'UTC',
               (month_start + INTERVAL '1 month') AT TIME ZONE 'UTC'
           ) AS expected_bound
    FROM parents AS p
    CROSS JOIN LATERAL generate_series(
        date_trunc('month', clock_timestamp() AT TIME ZONE 'UTC'),
        date_trunc('month',
                   (clock_timestamp() + INTERVAL '62 days') AT TIME ZONE 'UTC'),
        INTERVAL '1 month'
    ) AS month_start
), catalog AS (
    SELECT e.*, pt.isleaf,
           CASE WHEN e.expected_rel IS NULL THEN NULL
                ELSE pg_get_expr(c.relpartbound, c.oid) END AS actual_bound
    FROM expected AS e
    LEFT JOIN LATERAL pg_partition_tree(e.parent_rel) AS pt
      ON pt.relid = e.expected_rel
    LEFT JOIN pg_class AS c ON c.oid = e.expected_rel
)
SELECT schema_name, partition_prefix, month_start, expected_rel,
       expected_bound, actual_bound
FROM catalog
WHERE parent_rel IS NULL OR expected_rel IS NULL OR isleaf IS DISTINCT FROM true
   OR actual_bound IS DISTINCT FROM expected_bound
ORDER BY schema_name, partition_prefix, month_start;
```

DEFAULT 有行时先区分“未预建”与合法迟到数据，禁止改写事件时间。DEFAULT 中有重叠行会阻止直接建分区。迟到月份先在事务外保存来源摘要，然后在同一事务内搬移、校验并 ATTACH；任何摘要不一致必须在 COMMIT 前抛错。以下是 `workflow_events` 的完整模板：

```sql
CREATE TABLE bridgeai_workflow.workflow_events_2026_07_late
    (LIKE bridgeai_workflow.workflow_events
     INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES
     INCLUDING STORAGE INCLUDING COMMENTS);
ALTER TABLE bridgeai_workflow.workflow_events_2026_07_late
    ADD CONSTRAINT ck_workflow_events_2026_07_late
    CHECK (occurred_at >= TIMESTAMPTZ '2026-07-01 00:00:00+00'
       AND occurred_at <  TIMESTAMPTZ '2026-08-01 00:00:00+00');

-- 与下面事务使用同一数据库连接；临时表记录锁表前的期望集合。
CREATE TEMP TABLE workflow_events_late_expected (
    row_count BIGINT NOT NULL,
    min_id BIGINT,
    max_id BIGINT,
    min_key TIMESTAMPTZ,
    max_key TIMESTAMPTZ,
    row_sha256 TEXT NOT NULL
) ON COMMIT PRESERVE ROWS;
INSERT INTO workflow_events_late_expected
SELECT count(*), min(id), max(id), min(occurred_at), max(occurred_at),
       encode(digest(COALESCE(string_agg(row_doc, E'\n' ORDER BY id, occurred_at), ''),
                     'sha256'), 'hex')
FROM (
    SELECT d.id, d.occurred_at, to_jsonb(d)::text AS row_doc
    FROM bridgeai_workflow.workflow_events_default AS d
    WHERE d.occurred_at >= TIMESTAMPTZ '2026-07-01 00:00:00+00'
      AND d.occurred_at <  TIMESTAMPTZ '2026-08-01 00:00:00+00'
) AS expected_rows;

BEGIN;
LOCK TABLE bridgeai_workflow.workflow_events_default IN ACCESS EXCLUSIVE MODE;
DO $empty_staging$
BEGIN
    IF EXISTS (SELECT 1 FROM bridgeai_workflow.workflow_events_2026_07_late) THEN
        RAISE EXCEPTION 'late staging must be empty before copy';
    END IF;
END
$empty_staging$;
ALTER TABLE bridgeai_workflow.workflow_events_default DISABLE TRIGGER USER;
INSERT INTO bridgeai_workflow.workflow_events_2026_07_late
SELECT * FROM bridgeai_workflow.workflow_events_default
WHERE occurred_at >= TIMESTAMPTZ '2026-07-01 00:00:00+00'
  AND occurred_at <  TIMESTAMPTZ '2026-08-01 00:00:00+00';
DELETE FROM bridgeai_workflow.workflow_events_default
WHERE occurred_at >= TIMESTAMPTZ '2026-07-01 00:00:00+00'
  AND occurred_at <  TIMESTAMPTZ '2026-08-01 00:00:00+00';
ALTER TABLE bridgeai_workflow.workflow_events_default ENABLE TRIGGER USER;

-- 必须在 ATTACH/COMMIT 前验证；RAISE 会回滚 DELETE、触发器状态和全部 DDL。
DO $verify_late_copy$
DECLARE
    e_count BIGINT; e_min_id BIGINT; e_max_id BIGINT;
    e_min_key TIMESTAMPTZ; e_max_key TIMESTAMPTZ; e_hash TEXT;
    a_count BIGINT; a_min_id BIGINT; a_max_id BIGINT;
    a_min_key TIMESTAMPTZ; a_max_key TIMESTAMPTZ; a_hash TEXT;
    remaining BIGINT;
BEGIN
    SELECT row_count, min_id, max_id, min_key, max_key, row_sha256
      INTO STRICT e_count, e_min_id, e_max_id, e_min_key, e_max_key, e_hash
      FROM workflow_events_late_expected;
    SELECT count(*), min(id), max(id), min(occurred_at), max(occurred_at),
           encode(digest(COALESCE(string_agg(row_doc, E'\n' ORDER BY id, occurred_at), ''),
                         'sha256'), 'hex')
      INTO a_count, a_min_id, a_max_id, a_min_key, a_max_key, a_hash
      FROM (
          SELECT s.id, s.occurred_at, to_jsonb(s)::text AS row_doc
          FROM bridgeai_workflow.workflow_events_2026_07_late AS s
      ) AS actual_rows;
    SELECT count(*) INTO remaining
      FROM bridgeai_workflow.workflow_events_default
     WHERE occurred_at >= TIMESTAMPTZ '2026-07-01 00:00:00+00'
       AND occurred_at <  TIMESTAMPTZ '2026-08-01 00:00:00+00';
    IF remaining <> 0 OR
       ROW(a_count, a_min_id, a_max_id, a_min_key, a_max_key, a_hash)
       IS DISTINCT FROM
       ROW(e_count, e_min_id, e_max_id, e_min_key, e_max_key, e_hash) THEN
        RAISE EXCEPTION 'late copy verification failed: expected %, actual %, remaining %',
            e_count, a_count, remaining;
    END IF;
END
$verify_late_copy$;

ALTER TABLE bridgeai_workflow.workflow_events
    ATTACH PARTITION bridgeai_workflow.workflow_events_2026_07_late
    FOR VALUES FROM ('2026-07-01 00:00:00+00') TO ('2026-08-01 00:00:00+00');
COMMIT;

-- 提交后独立复核路由与摘要；此处失败触发发布中止和前滚修复，不冒充可回滚。
SELECT tableoid::regclass AS routed_partition, count(*) AS row_count,
       min(id) AS min_id, max(id) AS max_id,
       min(occurred_at) AS min_key, max(occurred_at) AS max_key
FROM bridgeai_workflow.workflow_events
WHERE occurred_at >= TIMESTAMPTZ '2026-07-01 00:00:00+00'
  AND occurred_at <  TIMESTAMPTZ '2026-08-01 00:00:00+00'
GROUP BY tableoid;
DROP TABLE workflow_events_late_expected;
```

该流程仅由迁移所有者执行，期间暂停目标父表写入或由上游缓冲。`DISABLE TRIGGER USER` 仅用于移动已经提交且追加不可变的 DEFAULT 行，不是业务删除通道。审计／访问事件使用同一事务内摘要门禁并将路由键换成 `server_recorded_at`；UUID 事件 ID 不依赖 `min/max(id)`，改为 `count + min/max(server_recorded_at) + 全行稳定 SHA-256`。节点执行 DEFAULT 的迟到行以 `created_at` 为键，且 registry/shadow 双向 anti-join 必须同时为 0 后才可 ATTACH。

### 8.23.3 父子索引和在线限制

分区父索引不存数据，真实存储在子索引。`CREATE TABLE ... PARTITION OF` 会为现有父索引建立匹配子索引。大存量独立表先加已验证的边界 CHECK，再于事务外逐子表 `CREATE INDEX CONCURRENTLY`，最后在短事务中 ATTACH 表和索引。PostgreSQL 17 不支持对分区父表 `CREATE INDEX CONCURRENTLY`。

```sql
SELECT parent.relname AS parent_index, child.relname AS child_index,
       i.indisvalid, i.indisready
FROM pg_inherits AS inh
JOIN pg_class AS parent ON parent.oid = inh.inhparent
JOIN pg_class AS child ON child.oid = inh.inhrelid
JOIN pg_index AS i ON i.indexrelid = child.oid
WHERE parent.relkind = 'I'
  AND parent.relnamespace IN (
      'bridgeai_workflow'::regnamespace, 'bridgeai_audit'::regnamespace
  )
ORDER BY parent.relname, child.relname;
```

任何 `indisvalid=false` 或 `indisready=false` 均阻断发布。失败的 concurrent index 先诊断，再 `DROP INDEX CONCURRENTLY` 后重试；同名 `IF NOT EXISTS` 不能证明其有效。

### 8.23.4 `workflow_node_executions` 兼容分区

该表当前以 `id` 为主键，且 run/node/attempt、idempotency 跨全表唯一；`workflow_reviews` 还以五列组合外键引用它。PostgreSQL 要求分区表的 PK/UNIQUE 包含分区键，简单加入 `created_at` 会把全局唯一错误地弱化为同时间唯一。

兼容方案使用不分区键登记表保持全局唯一，月分区表保存大体量执行内容：

```sql
CREATE TABLE bridgeai_workflow.workflow_node_execution_keys (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL,
    project_id UUID NOT NULL,
    task_id UUID NOT NULL,
    run_id UUID NOT NULL,
    node_name TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    idempotency_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_workflow_node_execution_keys_scope
        UNIQUE (id, organization_id, project_id, task_id, run_id, created_at),
    CONSTRAINT uq_workflow_node_execution_keys_attempt
        UNIQUE (organization_id, project_id, run_id, node_name, attempt),
    CONSTRAINT uq_workflow_node_execution_keys_idempotency
        UNIQUE (organization_id, project_id, idempotency_key),
    CONSTRAINT fk_workflow_node_execution_keys_run FOREIGN KEY (
        run_id, organization_id, project_id, task_id
    ) REFERENCES bridgeai_workflow.workflow_runs
      (id, organization_id, project_id, task_id) ON DELETE RESTRICT
);

-- 正式迁移显式列出 8.15 的全部列、CHECK 和 task/run FK，并在末尾声明：
CREATE TABLE bridgeai_workflow.workflow_node_executions_partitioned (
    LIKE bridgeai_workflow.workflow_node_executions
    INCLUDING DEFAULTS INCLUDING GENERATED INCLUDING STORAGE INCLUDING COMMENTS,
    PRIMARY KEY (id, created_at),
    UNIQUE (id, organization_id, project_id, task_id, run_id, created_at),
    FOREIGN KEY (id, organization_id, project_id, task_id, run_id, created_at)
        REFERENCES bridgeai_workflow.workflow_node_execution_keys
          (id, organization_id, project_id, task_id, run_id, created_at)
        ON DELETE RESTRICT
) PARTITION BY RANGE (created_at);

CREATE TABLE bridgeai_workflow.workflow_node_executions_partitioned_default
    PARTITION OF bridgeai_workflow.workflow_node_executions_partitioned DEFAULT;
CREATE TABLE bridgeai_workflow.workflow_node_executions_partitioned_2026_08
    PARTITION OF bridgeai_workflow.workflow_node_executions_partitioned
    FOR VALUES FROM ('2026-08-01 00:00:00+00') TO ('2026-09-01 00:00:00+00');

CREATE INDEX ix_workflow_node_executions_partitioned_run_status
    ON bridgeai_workflow.workflow_node_executions_partitioned
       (organization_id, project_id, run_id, status, node_name, created_at);
```

`LIKE` 不复制外键，原 PK/UNIQUE 也不能原样放入分区表；正式 Alembic 必须显式重建 task/run 外键、全部 CHECK 和不可变控制。DEFAULT 与月分区在 shadow 创建后、开始双写前建立；日常预建、DEFAULT 告警、迟到迁移和普通 DETACH 均把该父表作为第四个受管父表。switch 时父表改为正式名，子表可在独立低风险 revision 中同步改名，不能因名称切换重写行。

registry、shadow 父表、DEFAULT 和月分区都是租户表。下列 DDL 在任何运行时授权前完成；直接 INSERT/UPDATE/DELETE 始终从应用、索引 Worker 和 PUBLIC 撤销，应用只通过同事务受控函数创建 node，普通查询仅访问父表。后续月分区复用相同 owner/RLS/Policy，默认不获得直接 grant。

```sql
ALTER TABLE bridgeai_workflow.workflow_node_execution_keys
    OWNER TO bridgeai_migration_owner;
ALTER TABLE bridgeai_workflow.workflow_node_executions_partitioned
    OWNER TO bridgeai_migration_owner;
ALTER TABLE bridgeai_workflow.workflow_node_executions_partitioned_default
    OWNER TO bridgeai_migration_owner;
ALTER TABLE bridgeai_workflow.workflow_node_executions_partitioned_2026_08
    OWNER TO bridgeai_migration_owner;

ALTER TABLE bridgeai_workflow.workflow_node_execution_keys
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_workflow.workflow_node_execution_keys
    FORCE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_workflow.workflow_node_executions_partitioned
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_workflow.workflow_node_executions_partitioned
    FORCE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_workflow.workflow_node_executions_partitioned_default
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_workflow.workflow_node_executions_partitioned_default
    FORCE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_workflow.workflow_node_executions_partitioned_2026_08
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridgeai_workflow.workflow_node_executions_partitioned_2026_08
    FORCE ROW LEVEL SECURITY;

CREATE POLICY pl_workflow_node_execution_keys_scope
ON bridgeai_workflow.workflow_node_execution_keys
USING (
    organization_id = NULLIF(current_setting('app.organization_id', true), '')::uuid
    AND project_id = NULLIF(current_setting('app.project_id', true), '')::uuid
) WITH CHECK (
    organization_id = NULLIF(current_setting('app.organization_id', true), '')::uuid
    AND project_id = NULLIF(current_setting('app.project_id', true), '')::uuid
);
CREATE POLICY pl_workflow_node_executions_partitioned_scope
ON bridgeai_workflow.workflow_node_executions_partitioned
USING (
    organization_id = NULLIF(current_setting('app.organization_id', true), '')::uuid
    AND project_id = NULLIF(current_setting('app.project_id', true), '')::uuid
) WITH CHECK (
    organization_id = NULLIF(current_setting('app.organization_id', true), '')::uuid
    AND project_id = NULLIF(current_setting('app.project_id', true), '')::uuid
);
CREATE POLICY pl_workflow_node_executions_partitioned_default_scope
ON bridgeai_workflow.workflow_node_executions_partitioned_default
USING (
    organization_id = NULLIF(current_setting('app.organization_id', true), '')::uuid
    AND project_id = NULLIF(current_setting('app.project_id', true), '')::uuid
) WITH CHECK (
    organization_id = NULLIF(current_setting('app.organization_id', true), '')::uuid
    AND project_id = NULLIF(current_setting('app.project_id', true), '')::uuid
);
CREATE POLICY pl_workflow_node_executions_partitioned_2026_08_scope
ON bridgeai_workflow.workflow_node_executions_partitioned_2026_08
USING (
    organization_id = NULLIF(current_setting('app.organization_id', true), '')::uuid
    AND project_id = NULLIF(current_setting('app.project_id', true), '')::uuid
) WITH CHECK (
    organization_id = NULLIF(current_setting('app.organization_id', true), '')::uuid
    AND project_id = NULLIF(current_setting('app.project_id', true), '')::uuid
);

REVOKE ALL ON bridgeai_workflow.workflow_node_execution_keys,
    bridgeai_workflow.workflow_node_executions_partitioned,
    bridgeai_workflow.workflow_node_executions_partitioned_default,
    bridgeai_workflow.workflow_node_executions_partitioned_2026_08
    FROM PUBLIC;
REVOKE INSERT, UPDATE, DELETE ON bridgeai_workflow.workflow_node_execution_keys,
    bridgeai_workflow.workflow_node_executions_partitioned,
    bridgeai_workflow.workflow_node_executions_partitioned_default,
    bridgeai_workflow.workflow_node_executions_partitioned_2026_08
    FROM bridgeai_app_rw, bridgeai_index_worker;
GRANT SELECT ON bridgeai_workflow.workflow_node_execution_keys,
    bridgeai_workflow.workflow_node_executions_partitioned
    TO bridgeai_app_rw, bridgeai_readonly;
```

受控入口接受 shadow 的完整复合行，先登记全局键、锁定并比较已有语义，再写分区父表；任一步失败都回滚同一 PostgreSQL 事务。相同稳定 `id` 和相同 key 语义的重试可补齐此前由迁移所有者留下的 registry-only 行；不同 attempt/idempotency 或同 `id` 不同语义由唯一约束／显式比较拒绝。

```sql
CREATE OR REPLACE FUNCTION bridgeai_workflow.insert_node_execution_v2(
    p_execution bridgeai_workflow.workflow_node_executions_partitioned
) RETURNS TABLE (execution_id UUID, execution_created_at TIMESTAMPTZ)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, bridgeai_workflow
AS $$
DECLARE
    existing_key bridgeai_workflow.workflow_node_execution_keys%ROWTYPE;
BEGIN
    IF p_execution.organization_id IS DISTINCT FROM
       NULLIF(current_setting('app.organization_id', true), '')::uuid
       OR p_execution.project_id IS DISTINCT FROM
       NULLIF(current_setting('app.project_id', true), '')::uuid THEN
        RAISE EXCEPTION 'node execution scope differs from trusted context';
    END IF;

    INSERT INTO bridgeai_workflow.workflow_node_execution_keys (
        id, organization_id, project_id, task_id, run_id, node_name,
        attempt, idempotency_key, created_at
    ) VALUES (
        p_execution.id, p_execution.organization_id, p_execution.project_id,
        p_execution.task_id, p_execution.run_id, p_execution.node_name,
        p_execution.attempt, p_execution.idempotency_key, p_execution.created_at
    ) ON CONFLICT (id) DO NOTHING;

    SELECT * INTO STRICT existing_key
    FROM bridgeai_workflow.workflow_node_execution_keys
    WHERE id = p_execution.id
    FOR UPDATE;
    IF ROW(existing_key.organization_id, existing_key.project_id,
           existing_key.task_id, existing_key.run_id, existing_key.node_name,
           existing_key.attempt, existing_key.idempotency_key, existing_key.created_at)
       IS DISTINCT FROM
       ROW(p_execution.organization_id, p_execution.project_id,
           p_execution.task_id, p_execution.run_id, p_execution.node_name,
           p_execution.attempt, p_execution.idempotency_key, p_execution.created_at) THEN
        RAISE EXCEPTION 'node execution id reused with different key semantics';
    END IF;

    INSERT INTO bridgeai_workflow.workflow_node_executions_partitioned
    SELECT (p_execution).*
    ON CONFLICT (id, created_at) DO NOTHING;
    IF NOT FOUND AND NOT EXISTS (
        SELECT 1
        FROM bridgeai_workflow.workflow_node_executions_partitioned AS n
        WHERE (n.id, n.organization_id, n.project_id, n.task_id, n.run_id, n.created_at)
            = (p_execution.id, p_execution.organization_id, p_execution.project_id,
               p_execution.task_id, p_execution.run_id, p_execution.created_at)
    ) THEN
        RAISE EXCEPTION 'existing node execution differs from registry semantics';
    END IF;
    RETURN QUERY SELECT p_execution.id, p_execution.created_at;
END
$$;

ALTER FUNCTION bridgeai_workflow.insert_node_execution_v2(
    bridgeai_workflow.workflow_node_executions_partitioned
) OWNER TO bridgeai_migration_owner;
REVOKE ALL ON FUNCTION bridgeai_workflow.insert_node_execution_v2(
    bridgeai_workflow.workflow_node_executions_partitioned
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION bridgeai_workflow.insert_node_execution_v2(
    bridgeai_workflow.workflow_node_executions_partitioned
) TO bridgeai_app_rw;
```

双写、verify 和 contract 都必须保存下列结果，两个 anti-join 与键不一致查询均为 0；失败注入还须证明在 shadow INSERT 被 CHECK/FK 拒绝后 registry 行也随事务回滚。

```sql
SELECT k.id, k.created_at
FROM bridgeai_workflow.workflow_node_execution_keys AS k
LEFT JOIN bridgeai_workflow.workflow_node_executions_partitioned AS n
  ON (n.id, n.organization_id, n.project_id, n.task_id, n.run_id, n.created_at)
   = (k.id, k.organization_id, k.project_id, k.task_id, k.run_id, k.created_at)
WHERE n.id IS NULL;

SELECT n.id, n.created_at
FROM bridgeai_workflow.workflow_node_executions_partitioned AS n
LEFT JOIN bridgeai_workflow.workflow_node_execution_keys AS k
  ON (k.id, k.organization_id, k.project_id, k.task_id, k.run_id, k.created_at)
   = (n.id, n.organization_id, n.project_id, n.task_id, n.run_id, n.created_at)
WHERE k.id IS NULL
   OR ROW(k.node_name, k.attempt, k.idempotency_key)
      IS DISTINCT FROM ROW(n.node_name, n.attempt, n.idempotency_key);
```

`workflow_reviews` 在 expand 期新增可空 `node_execution_created_at`，从旧 node 行回填；验证后建立包含该时间的六列外键。`node_execution_id` 为空时新列也为空，非空时两者均非空。旧五列 FK 仅在六列 FK `VALIDATE` 成功、所有实例切换后删除。

### 8.23.5 归档与保留门禁

生命周期使用既有表的真实状态，不强行为每表添加同一状态集：`active` 可读可引用；`archived` 退出热查询但仍保留引用和恢复；`revoked` 立即拒绝新读取／引用；`deleting` 表示已授权且传播中；`deleted` 表示传播已核对；Memory 的 `tombstoned` 只保留 ID、scope、版本／哈希、删除依据和时间，不保留正文。

本章的四个父表都保留 DEFAULT 分区，PostgreSQL 17 因此会拒绝 `DETACH PARTITION ... CONCURRENTLY`。到龄分区须在写入暂停／上游缓冲的维护窗口中，使用短事务执行普通 `ALTER TABLE ... DETACH PARTITION`；node 分区在 DETACH 前还必须使 registry/shadow 双向 anti-join 为 0，并确认 `workflow_reviews` 六列 FK 无引用。不得为追求 concurrent detach 临时移除 DEFAULT 护栏。脱离后转只读归档，记录行数、范围、哈希、备份对象版本和恢复演练。物理 drop 前必须有精确 `retention_executions`，并同时满足：

1. `legal_hold_checked = true` 且无 legal hold；
2. `shared_reference_count = 0`，无强 FK、签发报告、Context、血缘或调查仍需数据；
3. 无 `pending/running/blocked/failed` 的保留或删除传播任务；
4. 归档备份已验证可恢复，法定审计保留期已满；
5. 两人审批、变更窗口和 break-glass 记录齐全。

审计事件不因业务对象删除而级联删除，按自身法定策略归档。门禁不满足时保持 detached/read-only 或继续在线，禁止自动 drop。

### 8.23.6 删除传播与失败重试

删除不是跨 PostgreSQL、Qdrant、Redis、MinIO 的分布式事务。顺序固定为：

```text
1 authorize：校验 actor、scope、retention、legal hold 和强引用
2 deny-read：同一 PostgreSQL 事务将 active -> revoked/deleting；Memory 创建
  bridgeai_memory.deletion_jobs，Artifact/其他领域对象创建相应领域 job 或
  bridgeai_audit.retention_executions；两者都写审计事件和 Outbox
3 cache：按对象版本／命名空间使 Redis 对象、查询和 Context 缓存失效
4 vector：只删除精确 collection/index_version/source UUID 的 point；
  bridgeai_memory_* 与 bridgeai_knowledge_* 永不交叉
5 object：仅当无共享引用、无 legal hold 且 retention_until 已到，
  删除 MinIO 精确 bucket/object_key/version_id 并回读确认
6 derived：撤销可重建的未签发产物；已签发报告、citation、lineage 和
  context_manifest_items 保留版本／哈希并显示“来源已删除”，不静默换源
7 tombstone：受控脱敏正文并保留最小墓碑；逐项成功后先 complete job，
  再将权威记录置 deleted
```

任何外部步骤失败时，PostgreSQL tombstone／拒读状态、删除依据、已完成步骤和 `last_error` 保留；Outbox 进入 retry/dead-letter。人工重放使用新幂等键且保持原语义。禁止为重试先删权威证据、审计或 Outbox，也禁止在数据库事务中同步调用外部存储。

## 8.24 数据迁移、兼容与发布流程

### 8.24.1 Expand-contract 主流程

所有 Alembic 发布固定采用 **expand → backfill → verify → switch → contract**，默认前滚而不是把新写入硬降级回旧形状。每阶段是独立 revision，记录兼容代码范围、前后置条件、锁预算和中止方案。

| 阶段 | 动作 | 退出门禁 |
|---|---|---|
| expand | 新增 nullable 列／新表、宽松 CHECK、兼容写入、`NOT VALID` 约束 | 老应用仍可读写；新对象 owner/RLS/Policy/grant 已验收；无长表锁 |
| backfill | 稳定游标分批回填、双写、异常隔离 | 可幂等重放；孤儿／越界／未知状态为 0；复制延迟、WAL、autovacuum 可控 |
| verify | `VALIDATE CONSTRAINT`、双读、行数／哈希／范围和查询计划核对 | 硬失配为 0；并发新写已纳入；失效索引为 0 |
| switch | 版本化 repository/feature flag 先切读、后切权威写 | 全实例运行兼容版；旧读仍可恢复；观察窗无硬失配 |
| contract | `NOT NULL`、最终 CHECK、删除旧列／触发器／表、收回 grant | 旧实例／Worker 为 0；完整业务周期与恢复演练通过 |

全程保持：租户键不跨域；confirmed 修订、已签发报告、审计事件和墓碑不原地改写；`task_id/run_id/thread_id` 不混同；已存幂等键语义不变；未终态 Outbox、legal hold、未到期 retention 和强引用不丢失。

### 8.24.2 Expand、稳定游标 Backfill 与并发写

新列先 nullable，不在一次高锁风险变更中同时新增、全表回填和 `SET NOT NULL`。以第五章旧 `workflow_tasks` 为例：

```sql
ALTER TABLE bridgeai_workflow.workflow_tasks
    ADD COLUMN IF NOT EXISTS organization_id UUID,
    ADD COLUMN IF NOT EXISTS idempotency_key TEXT,
    ADD COLUMN IF NOT EXISTS requested_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS updated_by UUID,
    ADD COLUMN IF NOT EXISTS version BIGINT;
```

回填 Worker 以 `(created_at,id)` 为稳定 cursor，每批独立短事务，只填 NULL。UUID 只打破同时间并列，不假设时间单调性。每个组织／项目 shard 只允许一个持有 advisory lease 的顺序 Worker 和一个独立 cursor；该 Worker**不得**使用 `SKIP LOCKED`，遇到较早业务锁时等待或整批超时重试，不能越过被锁行后推进高水位。需要并行时只在互不重叠的 shard 间并行。

```sql
WITH batch AS (
    SELECT t.id, p.organization_id
    FROM bridgeai_workflow.workflow_tasks AS t
    JOIN bridgeai_core.projects AS p ON p.id = t.project_id
    WHERE (t.created_at, t.id) > (:cursor_created_at, :cursor_id)
      AND (
          t.organization_id IS NULL OR t.idempotency_key IS NULL
          OR t.requested_at IS NULL OR t.updated_by IS NULL OR t.version IS NULL
    )
    ORDER BY t.created_at, t.id
    FOR UPDATE OF t
    LIMIT :batch_size
)
UPDATE bridgeai_workflow.workflow_tasks AS t
SET organization_id = COALESCE(t.organization_id, b.organization_id),
    idempotency_key = COALESCE(t.idempotency_key, 'legacy:task:' || t.id::text),
    requested_at = COALESCE(t.requested_at, t.created_at),
    updated_by = COALESCE(t.updated_by, t.created_by),
    version = COALESCE(t.version, 1)
FROM batch AS b
WHERE t.id = b.id
RETURNING t.created_at, t.id;
```

运行器仅在提交后保存最大 cursor；失败从上一已提交 cursor 重放。因为同一 shard 不跳锁，已提交 cursor 之前不存在因锁被越过的 NULL 行。expand 后新应用双写新旧形状，旧应用仍可写旧列。回填以 `COALESCE(target, derived)` 和行锁／version 避免覆盖并发新值。若必须使用兼容触发器，它须单向、可测试、有明确移除版本，且不能调用外部存储。

高水位扫描完成不等于 backfill 完成。停掉旧写入口并等待在途事务结束后，必须重复运行下列**无 cursor** 扫尾批次直至连续两轮返回 0 行；随后 NULL 统计仍须为 0，才可进入约束收紧。该扫尾也覆盖人工修复、超时重试或历史异常造成的低位遗漏。

```sql
WITH residual AS (
    SELECT t.id, p.organization_id
    FROM bridgeai_workflow.workflow_tasks AS t
    JOIN bridgeai_core.projects AS p ON p.id = t.project_id
    WHERE t.organization_id IS NULL OR t.idempotency_key IS NULL
       OR t.requested_at IS NULL OR t.updated_by IS NULL OR t.version IS NULL
    ORDER BY t.created_at, t.id
    FOR UPDATE OF t
    LIMIT :batch_size
)
UPDATE bridgeai_workflow.workflow_tasks AS t
SET organization_id = COALESCE(t.organization_id, r.organization_id),
    idempotency_key = COALESCE(t.idempotency_key, 'legacy:task:' || t.id::text),
    requested_at = COALESCE(t.requested_at, t.created_at),
    updated_by = COALESCE(t.updated_by, t.created_by),
    version = COALESCE(t.version, 1)
FROM residual AS r
WHERE t.id = r.id
RETURNING t.id;
```

### 8.24.3 约束、索引与事务边界

大表 FK/CHECK 先 `NOT VALID`：从创建起保护新写，历史数据回填和孤儿检查后再验证。

```sql
ALTER TABLE bridgeai_workflow.workflow_runs
    ADD CONSTRAINT fk_workflow_runs_task_scope_v2
    FOREIGN KEY (task_id, organization_id, project_id)
    REFERENCES bridgeai_workflow.workflow_tasks (id, organization_id, project_id)
    ON DELETE RESTRICT NOT VALID;

ALTER TABLE bridgeai_workflow.workflow_runs
    VALIDATE CONSTRAINT fk_workflow_runs_task_scope_v2;
```

验证失败时保留 `NOT VALID` 约束，隔离并修正历史异常后重试，不删除保护新写的约束。非空收紧先建并验证 `CHECK (column IS NOT NULL) NOT VALID`，再 `SET NOT NULL`，最后删过渡 CHECK。

`CREATE INDEX CONCURRENTLY`／`DROP INDEX CONCURRENTLY` 使用 Alembic autocommit block 或独立非事务 revision，与表变更、回填和验证分开：

```sql
-- 独立连接执行，前后不得有 BEGIN/COMMIT。
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_assets_name_trgm
    ON bridgeai_asset.assets USING GIN (lower(name) gin_trgm_ops);
```

执行后检查 `pg_index.indisvalid/indisready`。超时或取消可能留下失效索引；同名 `IF NOT EXISTS` 不证明有效，重试前须 `DROP INDEX CONCURRENTLY` 失效对象。分区父索引遵守 8.23.3 的逐子表并发创建和 ATTACH 边界。

### 8.24.4 Verify、Switch 与观察窗

verify 同时覆盖：

1. 目录：列、PK/UNIQUE/FK/CHECK、触发器、索引有效性、owner、RLS `ENABLE+FORCE`、Policy 和 grant 与 manifest 一致；
2. 数据：新旧路径比较 `count(*)`、`min/max(key)`、每租户／项目／月行数及不可变列聚合哈希；NULL、孤儿、越界为 0；
3. 并发：双写期持续执行创建／claim／复核，验证幂等冲突、锁等待、`SKIP LOCKED` 和重试；
4. 派生：所有非终态 Outbox 仍可 claim，Qdrant point/collection/index version、MinIO object version、Redis namespace 可与 PostgreSQL 聚合版本对账；
5. 性能：保存 8.22.3 的代表性 `EXPLAIN (ANALYZE, BUFFERS)`，确认分区剪枝及可接受的 WAL／写入影响。

switch 先切读后切写。读切换可按组织／项目回退，shadow-read 差异只存 hash 和定位键。读稳定后新写路径成为权威，旧路径在观察窗只作兼容核对。观察窗至少覆盖一个月分区边界和完整 Workflow 执行—复核—报告签发周期；风险记录可以要求更长，迁移人员不得临时缩短。

### 8.24.5 第五章 Workflow 逐表升级

已部署环境不得以空表替换旧表。严格顺序如下，每步先通过 8.15.2 的逐表验证：

| 顺序 | 表 | 升级与门禁 |
|---|---|---|
| 1 | `workflow_tasks` | 从 project 回填 organization；`bridge_id → asset_id`、`input_batch_id → acquisition_dataset_id`；移除 thread 全局唯一；补幂等、请求时间、版本、审计列；未知状态阻断 |
| 2 | `workflow_runs` | 从 task 回填 scope；历史 thread 仅此次复制，之后不自动同步；建 task/run/thread 组合被引用键 |
| 3 | `workflow_events` | `created_at → occurred_at`，补 recorded/scope/producer key；核对 task/run 后按月完整复制到影子分区表；count/min/max/hash 一致才短事务改名；DEFAULT 为 0 |
| 4 | `workflow_node_executions` | 先补 scope/audit/version 并核对 run；再建 8.23.4 registry、DEFAULT、月分区和 shadow 父表；通过受控函数双写，逐批把同一旧行在一个事务中写入 registry+shadow；双向 anti-join、键一致和 id/attempt/idempotency 全局唯一全部为 0 异常后才切换 |
| 5 | `workflow_reviews` | 最后补 scope/run/node；expand 新增 `node_execution_created_at`，回填后建六列 `NOT VALID` FK 并 `VALIDATE CONSTRAINT`；保持终态决策和幂等语义 |

每表异常清零、约束验证后才 `ENABLE/FORCE ROW LEVEL SECURITY`。owner 是不登录迁移角色，应用角色无 `BYPASSRLS`；Policy 先于 grant，切换后撤销旧表直访权限。分区子表和 registry 也在清单内。LangGraph Checkpointer 仍只由官方版本管理，不改名、不加业务 FK。

节点执行分区的关键增量为：

```sql
ALTER TABLE bridgeai_workflow.workflow_reviews
    ADD COLUMN IF NOT EXISTS node_execution_created_at TIMESTAMPTZ;

UPDATE bridgeai_workflow.workflow_reviews AS v
SET node_execution_created_at = n.created_at
FROM bridgeai_workflow.workflow_node_executions AS n
WHERE v.node_execution_id = n.id
  AND v.organization_id = n.organization_id
  AND v.project_id = n.project_id
  AND v.task_id = n.task_id
  AND v.run_id = n.run_id
  AND v.node_execution_created_at IS NULL;

ALTER TABLE bridgeai_workflow.workflow_reviews
    ADD CONSTRAINT ck_workflow_reviews_node_execution_time_pair_v2
    CHECK (
        (node_execution_id IS NULL AND node_execution_created_at IS NULL)
        OR
        (node_execution_id IS NOT NULL AND node_execution_created_at IS NOT NULL)
    ) NOT VALID;
ALTER TABLE bridgeai_workflow.workflow_reviews
    VALIDATE CONSTRAINT ck_workflow_reviews_node_execution_time_pair_v2;

ALTER TABLE bridgeai_workflow.workflow_reviews
    ADD CONSTRAINT fk_workflow_reviews_node_execution_v2
    FOREIGN KEY (
        node_execution_id, organization_id, project_id, task_id, run_id,
        node_execution_created_at
    ) REFERENCES bridgeai_workflow.workflow_node_executions_partitioned
      (id, organization_id, project_id, task_id, run_id, created_at)
    ON DELETE RESTRICT NOT VALID;
ALTER TABLE bridgeai_workflow.workflow_reviews
    VALIDATE CONSTRAINT fk_workflow_reviews_node_execution_v2;

-- 仅在 pair CHECK、六列 FK 均已 VALIDATE，所有实例已切换且观察窗通过后，
-- 于 contract revision 删除旧五列 FK；在此之前两条 FK 并存。
ALTER TABLE bridgeai_workflow.workflow_reviews
    DROP CONSTRAINT fk_workflow_reviews_node_execution_scope;
```

六列 FK 使用 PostgreSQL 默认 `MATCH SIMPLE`，所以 pair CHECK 不是文档性断言，而是防止 `node_execution_id` 非空、时间键为空时跳过 FK 的必要数据库约束。负向验收必须分别拒绝“任意 node + NULL 时间键”和“真实 node + 错误非空时间键”；`VALIDATE CONSTRAINT` 后从 `pg_constraint` 同时确认 pair CHECK 与六列 FK 的 `convalidated=true`，再允许旧 FK contract。

### 8.24.6 Contract、快照、失败与重试门禁

contract 不与 switch 同日执行。删除列／表、重编码 ID／分区键或改变哈希语义前，必须创建且真实恢复验证快照，记录 LSN、Schema revision、行数／哈希、MinIO version ID 与 Qdrant collection/index version。

- expand/backfill 失败：停 Worker，保留新列／影子表和 cursor，修复映射后幂等继续。
- verify 失败：不切流，保留保护新写的约束，隔离历史异常后重验。
- switch 后失败：兼容窗内 feature flag 切回旧读，双写不停；修复后再切。
- contract 后失败：发布 forward-fix 重建兼容视图／列，或从验证快照恢复到新表；不盲目 downgrade 丢弃新写。

最终 contract 硬门禁为：旧实例／Worker 为 0；双读硬失配为 0；所有高水位回填均完成无 cursor 扫尾且 NULL 为 0；registry/shadow 双向 anti-join 与键不一致为 0；pair CHECK 和六列 FK 均已验证；所有其他 FK/CHECK 已验证；无失效索引；四个 DEFAULT 均为 0 且未来 62 天分区已预建并核对边界；无未发布 Outbox 遗漏；legal hold、retention、删除 job 通过；RLS/Policy/grant 目录验收通过；Q1/Q5 原样查询计划和恢复演练通过。任一失败都保留兼容形态，不进入破坏性收缩。

## 8.25 备份、恢复与灾难演练

### 8.25.1 恢复目标、计时口径与失败语义

本节的灾难恢复范围覆盖 PostgreSQL 17 权威数据库、LangGraph 官方
Checkpointer 表、MinIO/S3 Artifact 不可变对象版本，以及由 PostgreSQL 权威状态
派生的 Qdrant 索引和 Redis 缓存。任何演练在开始前都必须指定灾难场景、故障时刻
`T_failure`、恢复点、隔离环境、数据集规模和负责人；生产实例不得作为试恢复目标，
也不得在演练中删除生产 WAL、对象版本或集合。

第一阶段服务目标为 **RPO 不超过 15 分钟、RTO 不超过 4 小时**：

- PostgreSQL 数据损失窗口为 `T_failure - T_last_recoverable_commit`；
  `T_last_recoverable_commit` 必须由实际回放后的事务、恢复 LSN 与业务时间戳共同证明。
- Artifact 数据损失窗口为 `T_failure - T_last_recoverable_object_version`；该对象版本必须
  同时存在于对象存储备份和同一恢复边界导出的 Artifact Manifest 中，并通过 SHA-256
  和字节数校验。
- 端到端 RPO 取 PostgreSQL 与所有受保护 Artifact 中的**最大**数据损失窗口，不取组件
  平均值。Qdrant 和 Redis 是派生层，不单独放宽权威数据 RPO。
- RTO 从事件被宣告且写入入口被隔离的 `T_declared` 开始，到 8.25.5 全部门禁通过、
  恢复负责人签署 `T_service_accepted` 为止，即
  `RTO = T_service_accepted - T_declared`。数据库进程启动、端口可连、对象服务返回 200
  或 Qdrant 集合创建成功都不是 RTO 结束。

`archive_timeout`、基础备份周期、对象复制周期和监控采样周期只是配置输入，不能单独
证明 RPO；组件启动日志、无断言的脚本退出码、截图或手工口头确认也不能证明 RTO。
任一权威组件超过 15 分钟、任一强门禁在 4 小时内未通过，或计时证据不完整，本次
演练状态都必须为 `FAILED`，不能以“部分通过”抵消。

### 8.25.2 备份分层与恢复契约

| 数据层 | 备份合同 | 恢复用途 | 完整性证据 | 失败处理 |
|---|---|---|---|---|
| PostgreSQL 物理层 | 周期性全量 `pg_basebackup`，持续归档其后 WAL；基准备份和 WAL 在独立故障域加密保存 | 整库、跨 Schema、Checkpoint 和审计的一致 PITR；主灾备路径 | `pg_verifybackup`、backup manifest、起止 LSN、WAL 连续性、数据校验和状态、实际目标时刻恢复 | 缺任一 WAL 段、manifest 校验失败或时间线不明即阻断，不跳过坏段启动 |
| PostgreSQL 逻辑层 | 按发布／合同变更创建 `pg_dump --format=custom`；另将全局角色和成员关系以受控、加密、最小权限方式导出 | 新空库兼容验证、选择性取证和物理恢复后的交叉核对；不替代 PITR | `pg_restore --list`、新空库恢复退出码、行数／哈希／约束／RLS 目录核对 | 不用逻辑备份宣称达到 15 分钟 RPO；角色文件可能含敏感 verifier，禁止写普通日志或仓库 |
| MinIO/S3 Artifact | bucket versioning 开启；保留精确 `bucket/object_key/version_id`，复制或离线备份对象版本；每个数据库恢复边界导出 Artifact Manifest | 恢复原始影像、模型、报告、知识原件及其他不可变字节 | 对象版本可读、`size_bytes` 一致、流式 SHA-256 一致、legal hold/retention 元数据核对、抽样与全量清单统计 | 禁止回退到同 key 的 latest 对象；对象缺失或哈希不一致时对应引用保持拒读并告警 |
| Qdrant | 保存 collection 配置、向量维数／距离、payload index、别名与 `index_version`；Point 可从权威记录重建 | 派生索引重建，不作为业务事实备份 | active/published 权威 ID 与 Point 双向差集、payload scope/version 抽样、别名切换记录 | 不完整集合不得挂生产别名；缺失时按第六、七章规则降级或拒绝，不扩大 SQL 扫描 |
| Redis | 不保存唯一权威数据，不要求内容级备份 | 从 PostgreSQL 和当前派生版本重建缓存 | 命名空间版本、ACL 版本和失效事件核对 | 丢失时冷启动；不得用旧 ACL 缓存恢复放行 |

物理备份作业使用受限备份角色和密钥管理系统注入的连接信息。以下是 PostgreSQL 17
命令形态，不包含凭据；实际目录、DSN、保留、带宽和归档工具必须来自版本化 Runbook，
并在非生产演练环境验证：

```bash
pg_basebackup \
  --dbname="$BRIDGEAI_BACKUP_DSN" \
  --pgdata="$BRIDGEAI_BASEBACKUP_DIR" \
  --format=plain \
  --wal-method=stream \
  --manifest-checksums=SHA256 \
  --progress

pg_verifybackup "$BRIDGEAI_BASEBACKUP_DIR"

pg_dump \
  --dbname="$BRIDGEAI_SOURCE_DSN" \
  --format=custom \
  --no-owner \
  --no-acl \
  --file="$BRIDGEAI_LOGICAL_DUMP"

pg_dumpall \
  --dbname="$BRIDGEAI_SOURCE_DSN" \
  --globals-only \
  --no-role-passwords \
  --file="$BRIDGEAI_GLOBALS_SQL"

pg_restore --list "$BRIDGEAI_LOGICAL_DUMP"
pg_restore \
  --dbname="$BRIDGEAI_EMPTY_RESTORE_DSN" \
  --exit-on-error \
  --no-owner \
  --no-acl \
  "$BRIDGEAI_LOGICAL_DUMP"
```

`pg_basebackup` 默认使用 spread checkpoint；除非容量测试证明 WAL/IO 峰值可承受、变更已
审批且处于维护窗口，不得以 `--checkpoint=fast` 覆盖默认值。fast checkpoint 不是 RPO/RTO
达标证据，也不得为缩短备份表面耗时牺牲在线工作负载。

逻辑恢复目标必须是新建空库；`pg_dumpall --globals-only --no-role-passwords` 只保存角色
属性和成员关系，不保存 verifier，恢复时由密钥管理流程重新配置凭据。对象 owner、角色
成员关系、RLS 和函数授权随后按迁移 manifest 恢复并以目录查询验收，而不是因为使用了
`--no-owner/--no-acl` 就省略。物理
PITR 从一份已通过 `pg_verifybackup` 的基准备份开始，恢复实例配置 `restore_command`，
创建 `recovery.signal`，并设置明确的 `recovery_target_time` 或经批准的
`recovery_target_lsn`；`recovery_target_action = 'pause'` 使负责人先核对目标点，再决定
promote。归档命令、恢复命令、时间线历史文件和介质路径依部署实现，只有在隔离环境
实际取回每个所需 WAL 段并到达目标点后才记录 `VERIFIED`。不得把本文示例替换成未经
执行的生产参数，也不得使用 `recovery_target = 'immediate'` 冒充指定时刻 PITR。

每次备份同时保存以下可追踪信息：集群 system identifier、PostgreSQL/扩展版本、
数据校验和状态、Alembic heads、配置摘要、基准备份起止时间／LSN／时间线、WAL 归档
连续区间、所有非系统 Schema、对象 owner、角色属性／成员关系、RLS/Policy/grant
manifest、已验证约束、有效索引、分区边界、行数和不可变列摘要。密钥、口令、访问令牌
和敏感正文不得进入证据包。

### 8.25.3 Artifact Manifest 与跨存储一致恢复点

Artifact Manifest 不是对象 key 列表，而是受控写屏障关闭后的不可变引用集合。不得用
`pg_current_wal_lsn()` 冒充 MVCC 快照或跨存储边界。备份控制器先关闭所有权威写入口、
等待在途写事务排空，并记录 `write_barrier_closed_at` 与唯一
`recovery_point_name`；随后由受控备份角色调用 `pg_create_restore_point`，将返回的
`restore_point_lsn` 与该名称写入恢复点记录。只有在该写屏障仍关闭时，才在
`REPEATABLE READ, READ ONLY` 事务导出 Manifest；查询按冻结时间／版本边界过滤，不接收
屏障后的 Artifact 版本。示例字段合同如下：

```sql
SELECT
    a.organization_id,
    a.project_id,
    a.id AS artifact_id,
    a.artifact_code,
    a.artifact_kind,
    a.status AS artifact_status,
    av.id AS artifact_version_id,
    av.revision_no,
    av.provider,
    av.bucket,
    av.object_key,
    av.version_id AS object_version_id,
    av.sha256,
    av.size_bytes,
    av.media_type,
    av.status AS artifact_version_status,
    av.sensitivity_level,
    av.verified_at,
    av.activated_at,
    av.retention_until,
    av.legal_hold,
    av.created_at,
    av.updated_at
FROM bridgeai_core.artifacts AS a
JOIN bridgeai_core.artifact_versions AS av
  ON (av.artifact_id, av.organization_id, av.project_id)
   = (a.id, a.organization_id, a.project_id)
WHERE av.status <> 'deleted'
  AND av.created_at <= :write_barrier_closed_at
  AND av.updated_at <= :write_barrier_closed_at
ORDER BY a.organization_id, a.project_id, a.id, av.revision_no;
```

在同一写屏障中先创建命名恢复点，再打开只读快照：

```sql
-- 此调用只在隔离演练或批准的备份控制器中执行；名称在控制平面全局唯一。
SELECT pg_create_restore_point(:recovery_point_name) AS restore_point_lsn;

BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
-- 导出以上带 :write_barrier_closed_at 的 Manifest 查询，并记录 snapshot_started_at。
COMMIT;
```

Manifest 使用确定性 CSV 或 JSON Lines 编码，记录行数、总字节数、文件 SHA-256、生成器
版本、`recovery_point_name`、`restore_point_lsn`、`write_barrier_closed_at`、快照时间和签名人；
文件本身写入版本化、加密、不可覆盖的备份位置。对象复制任务逐项读取精确
`object_version_id`，流式计算哈希而不把大对象整体装入内存。`sha256`/`size_bytes` 为空的
staged 行只可作为待收敛异常登记，不能计入已保护对象；active/archived/revoked/deleting
对象缺版本、缺哈希或 legal hold/retention 元数据不一致均阻断备份完成。

PostgreSQL 与对象清单必须形成命名恢复点：写屏障关闭并排空事务 → 创建
`recovery_point_name/restore_point_lsn` → 导出冻结边界 Manifest → 等待 Manifest 所列对象版本
全部进入备份故障域 → 写入完成标记。完成标记至少包含 PostgreSQL backup ID、WAL 连续上界、
`recovery_point_name`、`restore_point_lsn`、Manifest SHA-256、对象版本全量校验状态和
`completed_at`。没有该完成标记的组合只能作为候选恢复材料，不能宣称达到 RPO。

### 8.25.4 隔离恢复顺序与逐步门禁

恢复全程默认 deny-by-default：入口、Worker、定时任务、Outbox 发布、对象删除、索引
别名切换和报告签发均保持关闭。每步必须保存执行者、起止时间、命令／查询版本、原始
机器可读结果和裁决；`expected` 不满足时停止后续放流，但可继续只读取证。

| 顺序 | 恢复动作与负责人 | 验证查询／证据 | 期望 | 不满足时的阻断 |
|---:|---|---|---|---|
| 0 | 事件指挥选择 `T_target`、backup ID、时间线和 Artifact Manifest | 比较 `T_failure`、LSN/WAL 覆盖区间、Manifest 快照时间与 SHA-256 | 同一命名恢复点，计算的最坏数据损失 ≤ 15 分钟 | 时间线分叉不明、WAL 缺段或清单未完成则不得恢复 |
| 1 | 数据库负责人在隔离网络恢复物理基线并回放 WAL 到目标点 | PostgreSQL recovery 日志、`pg_is_in_recovery()`、`pg_last_wal_replay_lsn()`、目标事务抽样 | 精确到批准目标且先 pause；promote 后时间线被记录 | 到达错误目标、自动越过目标或需跳过坏 WAL 均失败 |
| 2 | 平台负责人核对扩展和空间基线 | `SELECT extname,extversion FROM pg_extension ORDER BY 1;`；`SELECT PostGIS_Full_Version();`；检查 `spatial_ref_sys` 中本项目 SRID | `pgcrypto`、`pg_trgm`、`btree_gist`、PostGIS 及 SRID 与 manifest 一致 | 扩展/SRID 缺失或版本未经兼容验证时不运行空间迁移与查询 |
| 3 | 数据库迁移负责人核对 Schema revision | Alembic `current`/`heads`；`pg_namespace`、`pg_class` 和 migration manifest 差集 | 恢复库只处于一个已批准 revision；不存在意外 ahead/behind | 不在恢复库盲目补跑未知 migration；先裁决 forward-fix 或重选恢复点 |
| 4 | 安全与数据库负责人恢复／验证角色、owner、RLS 与函数授权 | `pg_roles`、`pg_auth_members`、`pg_class.relrowsecurity/relforcerowsecurity`、`pg_policies`、`information_schema.routine_privileges` | migration owner 不登录；应用无 `BYPASSRLS`；租户表 `ENABLE+FORCE`；SECURITY DEFINER 固定 `search_path` 且 PUBLIC 无 EXECUTE | 任一 owner/Policy/grant 漂移即保持所有应用连接关闭 |
| 5 | 数据负责人验证强约束、索引和分区 | `pg_constraint.convalidated`、`pg_index.indisvalid/indisready`、`pg_partition_tree`、DEFAULT 行数、未来 62 天边界 | 所有目标 FK/CHECK 已验证；索引有效；DEFAULT 为 0；分区覆盖合同成立 | 约束未验证、无效索引或分区洞阻断写入 |
| 6 | 安全负责人执行双租户正负向 RLS 验收 | 分别设置受信任组织／项目上下文读取自身行，再以另一项目上下文查询和写入同一 ID | 同租户授权成功；跨组织／项目查询返回 0、写入被拒绝；审计可定位 | 只做正向查询或用 owner/superuser 测试均无效 |
| 7 | 对象负责人逐项恢复 Artifact | 按 Manifest 精确读取 bucket/key/object_version_id，核对 SHA-256、size、status、retention、legal hold；业务 FK anti-join | 所有强引用版本存在且字节一致；删除中／冻结对象状态不倒退 | 禁止以 latest 版本替代；缺失对象的上层记录保持不可读 |
| 8 | 领域负责人核对病害、报告与签发证据 | 当前 `damage_revision_id` 指针、revision 链和量测；报告版本、citation、lineage、signature 与 Artifact 版本 anti-join | confirmed 修订不被改写；签发报告所有证据版本和签名引用闭合 | 缺任何证据时报告签发／下载保持关闭，不换用“最新”来源 |
| 9 | Workflow 负责人核对业务表与官方 Checkpoint | 按 `thread_id/task_id/run_id` 检查任务、运行、复核、最后稳定节点、checkpoint 时间；执行原幂等键 dry-run | 非终态业务状态与 checkpoint 一致；Interrupt 前副作用可证明幂等 | 不直接改官方表；无法恢复关键上下文的任务进入人工复核 |
| 10 | Knowledge/Memory 负责人先加载 ACL、撤销、删除日志和墓碑，再重建派生索引 | active/published 权威集合与 Qdrant Point 双向差集；collection/index version、payload scope/ACL；Context Manifest 引用 | 已撤回／删除内容不复活；RAG 与 Memory 集合隔离；差集为 0 后才切别名 | Qdrant 不可用可按第六、七章降级；不得恢复旧集合绕过 ACL |
| 11 | 集成负责人恢复 Outbox 与审计链 | 非终态 Outbox claim/lease、dead-letter、语义哈希；业务版本与事件差集；审计序列、血缘和删除 job | 未发布事件不丢失不重复；相同 key 不同语义仍拒绝；审计与墓碑连续 | 不手改 Outbox 为 published；差异先用受控重放／前滚修复 |
| 12 | 事件指挥运行读写冒烟、关键 Workflow 与容量检查后签署开放 | 8.25.5 与 8.26.6 证据矩阵；监控无 P0/P1；恢复报告双人签署 | 全部门禁通过，记录 `T_service_accepted`，RTO ≤ 4 小时 | 任一强门禁失败则保持隔离，记录 `FAILED` 或明确 `GAP` |

逻辑恢复时角色必须在对象恢复前由受控流程创建；表和函数恢复后仍按上表第 4 步重新
赋 owner/grant。物理恢复包含全局目录，但不因此省略角色属性和 RLS 复核。删除日志、
ACL、legal hold、retention、墓碑和审计必须先于普通业务读开放，防止旧备份让已撤销
内容重新可见。

### 8.25.5 季度灾难演练与证据包

至少**每季度一次**在隔离网络做端到端恢复；重大 PostgreSQL/扩展升级、备份拓扑、
MinIO 版本策略、Schema 合同或加密密钥流程改变后追加演练。四个连续季度轮换覆盖：
整库丢失 PITR、误操作指定时刻恢复、单一 Artifact 版本丢失、Qdrant 全集合丢失并从
PostgreSQL 重建；每次都包含 Workflow Checkpoint 恢复、跨租户负向测试、Outbox 重放
和至少一个签发报告证据链。

演练步骤为：预登记场景与成功标准 → 记录故障点和最后已提交探针 → 隔离恢复 → 按
8.25.4 执行 → 在目标点后写入 canary 以确认回放停止 → 对 Manifest 对象全量元数据
核对并按风险分层抽样字节哈希 → 重建派生层 → 执行关键 Workflow → 计算端到端
RPO/RTO → 双人复核 → 记录缺陷、负责人和截止时间。演练不得使用生产凭据复制到普通
日志，测试数据必须脱敏，临时恢复环境在证据固化和批准后按受控流程清理。

证据包至少包含：场景和范围；参与人和审批；硬件／网络／数据规模；备份 ID；system
identifier；时间线与 LSN；目标时间；`pg_verifybackup` 输出；所需和已取回 WAL 清单；
PITR pause/promote 时刻；Alembic/扩展/角色/RLS/约束/索引/分区目录结果；Manifest 与
对象校验摘要；租户正负向结果；Workflow/Checkpoint 对账；RAG/Memory 重建差集；
Outbox/审计对账；故障注入记录；所有步骤起止时间；实际 RPO/RTO；失败原始输出；最终
`VERIFIED`/`FAILED`/`GAP` 状态和签署。只保留成功截图、删去失败日志或补写未执行结果
均视为证据无效。

## 8.26 性能、容量、可观测性与测试

### 8.26.1 性能 SLO 与可复现实验合同

数据库侧第一阶段硬目标如下；它们是第六、七章端到端目标的子预算，不能替代 RAG、
Memory、模型或对象传输的整体 SLO：

| 查询类别 | 数据库 p95 目标 | 代表合同 |
|---|---:|---|
| 主键读取与幂等重复写入 | p95 ≤ 100 ms | 在完整组织／项目 RLS 上下文中按业务唯一键读取 Artifact、任务、报告或当前版本；同 key 重复调用受控幂等入口 |
| 项目任务、病害与报告列表 | p95 ≤ 300 ms | 按 scope、状态和时间范围分页，含真实 JOIN、稳定排序和 keyset cursor |
| 单资产多期病害与典型空间查询 | p95 ≤ 500 ms | 8.22.2 的 Q2/Q6 原样绑定；包含 PostGIS 谓词、时间过滤、必要聚合与分区剪枝 |

任何性能结论必须附完整实验合同：Git SHA、Alembic revision、PostgreSQL/扩展版本、
Schema 与统计信息时间、硬件型号／CPU／内存／磁盘、OS、PostgreSQL 配置 diff、连接池
大小、客户端位置、数据行数／字节数／组织和项目分布、空间选择率、分区数量、索引清单、
真实或等分布脱敏数据生成版本、并发和到达率、持续时间、预热次数、冷热缓存状态、超时、
错误率，以及 P50/P95/P99。至少报告冷缓存与热缓存、1/5/20 个并发会话；本地 Memory
基线还须保留第七章的 20 并发预热场景。缓存命中结果与未命中结果分开，不得混为一个
P95。

延迟从客户端发出请求到完整结果被消费计时，包含连接池排队、事务、`SET LOCAL` 受信
任上下文、RLS、数据库执行和结果传输；大 Artifact 字节传输另列对象存储 SLO，不能从
数据库查询时延中隐藏。每个场景至少有足以稳定分位数的样本，预热、正式测量和故障
注入结果分开保存。零错误且 P95 达标才通过；超时请求仍计入分位和错误率。

代表性 Q1 只读计划使用真实绑定值和应用角色采集：

```sql
BEGIN READ ONLY;
SET LOCAL ROLE bridgeai_app_rw;
SELECT set_config('app.organization_id', :organization_id, true);
SELECT set_config('app.project_id', :project_id, true);

EXPLAIN (ANALYZE, BUFFERS, WAL, SETTINGS, FORMAT JSON)
-- 此处粘贴 8.22.2 Q1 的原样 SQL，并绑定同一验收参数；不得改写为简化查询。
ROLLBACK;
```

Q5 含 `FOR UPDATE SKIP LOCKED`，`EXPLAIN ANALYZE` 会执行并锁定候选行，不能放入
`BEGIN READ ONLY`，也不能在生产 Worker 流量中临时运行。仅在隔离、非生产数据库以受控
测试角色运行下列可回滚事务；锁只保留到 `ROLLBACK`：

```sql
BEGIN READ WRITE;
SET LOCAL ROLE bridgeai_migration_owner;
SELECT set_config('app.organization_id', :organization_id, true);
SELECT set_config('app.project_id', :project_id, true);

EXPLAIN (ANALYZE, BUFFERS, WAL, SETTINGS, FORMAT JSON)
-- 此处粘贴 8.22.2 Q5 的原样 SQL，并绑定同一验收参数；不得改写为简化查询。
ROLLBACK;
```

上例不是 `SELECT 1` 的替代品。证据必须保存 Q1/Q5 真实查询的实际／估算行数、loop、
shared/local/temp block、sort spill、WAL、planning/execution time、分区剪枝和索引条件。
生产环境只在审批的低风险窗口使用 `ANALYZE`；不得为“好看”的计划关闭 RLS、强制 planner
GUC、移除真实 JOIN 或只选最有利参数。

### 8.26.2 容量模型、预测与扩缩容门槛

容量基线按天快照，至少保存 90 天；新系统在历史不足时使用压测和导入计划形成有来源
的先验，并明确置信区间。每种资源都分配 owner、软阈值、硬阈值、采购／扩容 lead time
和降级策略：

| 资源 | 基线与增长公式 | 软／硬门槛 | 提前期与动作 |
|---|---|---|---|
| 表与 TOAST | `daily_growth = (total_bytes[D]-total_bytes[D-7])/7`；按 schema/table/partition、活跃和归档分别统计 | 预测可用空间 < 90 天或磁盘 ≥ 75% 告警；< 30 天或 ≥ 85% 严重 | 平台 owner，提前 90 天扩盘／归档；硬门槛冻结批量导入，保留关键在线写入 |
| 索引 | `index_ratio = index_bytes/table_bytes`，跟踪每日增长、重复／未使用索引和 bloat 证据 | 单索引逼近介质／维护窗限制、无效索引 > 0 为严重；增长偏离表增长 2 倍持续 7 天告警 | DBA 评审 8.22.3 生命周期；只能在工作负载证据和回归后删改 |
| WAL 与归档 | `wal_rate = delta(pg_stat_wal.wal_bytes)/seconds`；容量按 P95 写入速率 × 峰值因子 × 最长故障／保留窗 | 最近成功归档距今 > 5 分钟告警、> 10 分钟严重；归档失败增加立即严重 | DBA/存储 owner 先恢复归档连续性并限流批量写；15 分钟前升级灾备事件 |
| 月分区 | 每父表记录当月、DEFAULT、未来覆盖和迟到率 | DEFAULT 任一行立即严重；未来覆盖 < 62 天告警；单月预测超过维护窗能力告警 | DBA 预建／拆分粒度；保留 DEFAULT 护栏，不临时移除 |
| Outbox/审计 | 行数、最老可 claim 年龄、dead-letter、每日事件字节 | 正常 oldest pending > 30 秒告警，> 5 分钟严重；dead-letter 新增立即告警 | 集成 owner 扩 Worker／熔断派生写；不直接改 published |
| MinIO/S3 | 按 bucket、版本状态、media type 统计对象数／逻辑字节／实际占用，计入非当前版本和复制开销 | 预测余量 < 90/30 天；Manifest 引用版本缺失或校验失败立即严重 | 对象 owner 扩容或按 8.23 门禁归档；不得覆盖版本或越过 legal hold |
| Qdrant | collection/index version 的 Point 数、向量维数、payload、segment 和磁盘／内存；按发布量预测 | 资源 ≥ 75% 告警、≥ 85% 严重；Point 与权威集合差异 > 0 阻断别名 | Knowledge/Memory owner 建新版本集合、限流重建；禁止混用两类集合 |
| 连接与内存 | 活跃／等待连接、池排队、事务年龄、temp bytes、work_mem 乘并发上界 | 池占用 ≥ 80% 持续 10 分钟告警，≥ 90% 或等待 > 30 秒严重；idle in transaction > 60 秒严重 | 应用 owner 限并发、排查长事务；不靠无限增大 max_connections |

预测使用 `effective_daily_growth = max(P50_recent, planned_import_rate) × peak_factor`；
`days_to_exhaust = usable_free_bytes / effective_daily_growth`。`peak_factor`、压缩率、版本
保留倍数、复制副本数、Autovacuum 空间和恢复临时空间必须显式记录，不能默认等于 1。
年度采购按 P95 峰值与 lead time 规划，短期降级优先暂停批量 OCR/Embedding/索引重建和
非关键分析，不暂停审计、Outbox、删除拒读或正式业务结果持久化。

PostgreSQL 容量快照的可执行基线为：

```sql
SELECT n.nspname AS schema_name, c.relname,
       pg_total_relation_size(c.oid) AS total_bytes,
       pg_relation_size(c.oid) AS heap_bytes,
       pg_indexes_size(c.oid) AS index_bytes,
       COALESCE(s.n_live_tup, 0) AS estimated_live_rows,
       COALESCE(s.n_dead_tup, 0) AS estimated_dead_rows,
       s.last_analyze, s.last_autovacuum
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
LEFT JOIN pg_stat_user_tables AS s ON s.relid = c.oid
WHERE n.nspname LIKE 'bridgeai\_%' ESCAPE '\'
  AND c.relkind IN ('r', 'p', 'm')
ORDER BY total_bytes DESC;

SELECT wal_bytes, wal_records, wal_fpi, stats_reset
FROM pg_stat_wal;

SELECT archived_count, last_archived_wal, last_archived_time,
       failed_count, last_failed_wal, last_failed_time, stats_reset
FROM pg_stat_archiver;
```

### 8.26.3 数据库指标、告警与可定位性

每条告警定义都必须包含来源、公式、维度、阈值、窗口、严重级别、Runbook 和 owner。
推荐基线如下，生产阈值须以压测和至少 30 天趋势校准，但不能放宽安全与恢复硬门禁：

| 信号 | 来源／公式与低基数维度 | 告警合同 | Runbook 首动作 |
|---|---|---|---|
| 查询延迟／错误 | 应用 OpenTelemetry；按 `operation,route,result,db_role` 统计 histogram 和 error rate | 任一数据库类别 P95 连续 10 分钟超 8.26.1 目标为 P1；错误率 > 1% 持续 5 分钟为 P1 | 对照 trace 查池等待与 query fingerprint，再查计划漂移／锁／IO；禁止记录绑定的敏感正文 |
| 连接池饱和 | 池 metrics：`checked_out/max_size` 与 wait histogram；维度 `service,pool` | ≥ 80% 10 分钟 P2；≥ 90% 或等待 P95 > 1 秒 5 分钟 P1 | 限流批任务，定位长事务和泄漏，不先加连接数 |
| 锁等待／长事务 | `pg_stat_activity`、`pg_locks`；等待年龄和 `xact_start` | 阻塞关键写 > 30 秒或事务 > 5 分钟 P1；idle in transaction > 60 秒 P1 | 保存阻塞图、联系 owner；终止会话需事件审批 |
| 缓存／IO | `pg_stat_database` 的 blks_hit/read、temp_bytes；OS 磁盘时延 | cache hit ratio 异常下降或 temp_bytes 速率较基线翻倍 15 分钟 P2；磁盘延迟越 SLO P1 | 对照工作负载和 plan，检查 spill、顺扫、统计信息与磁盘 |
| 表健康 | `pg_stat_user_tables` 的 dead/live、last_autovacuum/analyze；`pg_stat_progress_vacuum` | `dead/live > 10%` 且 dead > 100000 持续 30 分钟 P2；关键表 24 小时未 analyze 且变化大为 P2 | 查长事务和 autovacuum 配置，先验证再手动 VACUUM/ANALYZE |
| 复制／归档／备份 | `pg_stat_replication` LSN 差、`pg_stat_archiver`、备份作业和季度恢复证据 | 归档 5/10 分钟阈值见 8.26.2；最近成功物理备份超过计划窗口 P1；季度恢复逾期 P1 | 先保护 WAL 连续性和介质容量；不能以 archive_timeout 关闭告警 |
| 端到端恢复点年龄与生成延迟 | 备份控制平面仅对 PostgreSQL backup、`recovery_point_name/restore_point_lsn`、Manifest digest 和全部对象版本校验均为 verified 的完成标记取值；`latest_completed_recovery_point_age_seconds = extract(epoch from (clock_timestamp() - max(write_barrier_closed_at)))`，`recovery_point_completion_latency_seconds = extract(epoch from (completed_at - write_barrier_closed_at))`；维度仅 `environment,backup_policy` | RPO 告警只看数据边界年龄：>10 分钟 P2，>15 分钟 P1；缺完成标记或任一组成状态非 verified 立即 P1。生成延迟单独按备份策略预算告警，不得用 `completed_at` 刷新或清零 RPO 年龄 | 灾备/DB/对象存储 owner 首先读取最近 fully verified 标记的 `write_barrier_closed_at`，以它而非 `completed_at` 判定 RPO；随后保护 WAL 连续性，检查写屏障、Manifest 与对象复制并重新生成完整恢复点。不得把候选材料、单独 PostgreSQL 备份或对象同步标为可恢复 |
| 分区／约束／索引 | 目录巡检、DEFAULT 行数、未来边界、`convalidated`、`indisvalid/indisready` | DEFAULT > 0、约束意外未验证、失效索引均 P1 | 停相关发布／归档，按 8.23/8.24 前滚修复 |
| Outbox／删除 | `outbox_events`、`deletion_jobs`、`retention_executions` 的状态年龄和 semantic digest | oldest 30 秒 P2／5 分钟 P1；dead-letter 或删除状态倒退 P1 | 保持 revoked/deny-read，检查 lease、worker 和外部依赖，受控重放 |
| Artifact | Manifest 对账、对象 HEAD/GET、哈希抽样 | 强引用版本缺失、SHA-256 不一致、legal hold/retention 漂移均 P0/P1 | 阻断对象及上层证据读取，保全版本和审计，不以 latest 替代 |
| 租户隔离 | 应用拒绝计数、安全审计和持续合成越权探针 | 合成探针任何一次越权成功为 P0；异常拒绝率激增 P1 | 立即隔离入口，保存 Policy/role/trace 证据并启动安全响应 |

数据库即时诊断只读查询示例：

```sql
SELECT pid, usename, application_name, backend_type, state, wait_event_type,
       wait_event, clock_timestamp() - xact_start AS transaction_age,
       clock_timestamp() - query_start AS query_age,
       query_id
FROM pg_stat_activity
WHERE datname = current_database()
ORDER BY query_age DESC NULLS LAST;

SELECT datname, numbackends, xact_commit, xact_rollback,
       blks_read, blks_hit, temp_files, temp_bytes, deadlocks, stats_reset
FROM pg_stat_database
WHERE datname = current_database();

SELECT schemaname, relname, seq_scan, idx_scan, n_live_tup, n_dead_tup,
       last_autovacuum, last_autoanalyze
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC;
```

指标标签禁止使用 `organization_id`、`project_id`、`user_id`、Artifact ID、自然语言 query、
`request_id` 或完整 `query_id` 等高基数／敏感值。精确定位键进入受控 trace、结构化日志或
审计，并受脱敏、访问控制和保留策略保护；metrics 只使用操作类别、服务、结果、区域、
数据库角色等低基数维度。日志不得包含访问令牌、数据库凭据、完整 SQL 参数、Artifact
正文、完整 Prompt 或未脱敏个人信息。

### 8.26.4 降级、运行手册与变更回归

性能或容量压力不得破坏一致性和权限边界。允许的顺序是：限制批量入库／回填／索引
重建 → 降低非关键统计频率 → 对 Qdrant/Reranker/摘要按第六、七章明确标记降级 → 对
仍超载的租户实施公平限流。禁止关闭 RLS、跳过引用校验、恢复 revoked 内容、丢弃审计
或 Outbox、把签发报告降级为无证据结果、无限增加连接数，或用全库模糊 SQL 替代不可用
向量检索。

每个 P0/P1/P2 告警 Runbook 至少说明：影响与安全边界、owner/升级路径、只读诊断、
停止条件、可逆缓解、需审批的破坏性动作、恢复查询、数据一致性复核和复盘证据。高风险
动作如终止后端、promote、分区 DETACH、对象删除、别名切换和受控 Outbox 重放必须有
精确目标、双人审批和审计；Runbook 不保存凭据。

以下变化必须重跑受影响的功能、性能和恢复合同：PostgreSQL/扩展升级；Schema migration；
RLS/Policy/owner/grant；索引与统计；分区／retention；Artifact 版本策略；Outbox；
Checkpoint 版本；Qdrant collection/payload/别名；ACL、Embedding、检索和 Context Policy。
计划回归以相同数据和参数比较，新计划若 P95 退化超过 20%、buffer/temp/WAL 明显增加、
分区剪枝消失、估算偏差超过 10 倍或出现跨 scope 行，均阻断发布，除非评审记录新的基线
和容量影响；安全负向失败没有豁免。

### 8.26.5 测试与恢复验收矩阵

| 层级／场景 | 正向断言 | 负向／并发／故障注入 | 必须保存的证据 | 验收 |
|---|---|---|---|---|
| DDL 与迁移 | PostgreSQL 17 空库从零迁移、旧版本 expand-backfill-verify-switch-contract；所有 Schema/表/索引/触发器存在 | 未知状态、孤儿、重复、NULL、失效索引、低位漏扫、并发旧写使发布阻断 | revision、目录 diff、行数/min/max/hash、`convalidated`、`indisvalid/indisready`、锁时长 | 所有强门禁满足且重跑幂等 |
| RLS 与角色 | 每个角色在授权组织／项目完成允许操作；SECURITY DEFINER 经受控入口生效 | 未设置上下文、跨组织、跨项目、伪造 actor、PUBLIC EXECUTE、owner/app BYPASSRLS 均拒绝 | 角色、owner、Policy/grant catalog 与正负向 SQL 原始结果 | 越权成功数为 0 |
| 约束与状态机 | 合法 Artifact、病害修订、报告签发、Memory、发布和删除流转成功 | 越界组合 FK、原地改写 immutable、跳状态、legal hold/retention 绕过、共享引用删除均拒绝 | 事务结果、错误码、回滚后 anti-join | 失败事务不留半状态 |
| 幂等／并发／Outbox | 同 key 同 request/semantic digest 返回同结果；不同 key 独立；claim/ack 正常 | 同 key 不同 hash/payload/max_attempts 冲突；并发 claim 不重复；lease 过期、Worker 崩溃、dead-letter、受控重放 | 稳定 key、semantic digest、并发时间线、锁／lease、业务与 Outbox 差集 | 无重复副作用，无已提交业务变更缺事件 |
| 分区与保留 | 月边界、迟到行迁移、registry/shadow、归档读取和恢复正常 | DEFAULT 行、边界时区、ATTACH 摘要不符、被 review 引用、legal hold、pending deletion 时 DETACH/drop 阻断 | `tableoid`、边界、摘要、双向 anti-join、审批和恢复对象版本 | DEFAULT 为 0；门禁失败不物理删除 |
| 物理备份与 PITR | 基准备份验证并回放到选定事务；角色/RLS/约束/Checkpoint 完整 | 删除一段演练 WAL、错误时间线、目标点之后 canary、归档中断 | backup/WAL manifest、replay LSN、目标事务、失败日志、实测 RPO/RTO | 全链 ≤15 分钟/≤4 小时，否则 FAILED |
| 逻辑恢复 | custom dump 恢复到新空 PostgreSQL 17 库并做目录/数据对账 | 非空目标、缺角色／扩展、错误 revision、约束/RLS/grant 漂移阻断 | dump digest、restore list/exit、catalog diff、行数/hash | 仅作补充证据，不冒充 PITR |
| Artifact/MinIO | Manifest 中每个强引用 object_version_id 可读且 hash/size 一致 | latest 与 version 不同、缺版本、篡改字节、legal hold/retention 漂移、对象服务中断 | Manifest digest、inventory、HEAD/GET 和 SHA-256 汇总 | 差异为 0；否则相关上层拒读 |
| PostGIS | 目标 SRID、空间约束、Q2/Q6、GiST 和空间结果在真实扩展运行 | 错 SRID、越界坐标、空 geometry、错误 bbox 被拒绝；计划退化阻断 | PostGIS 版本、SRID、结果集、`EXPLAIN (ANALYZE, BUFFERS)` | 没有 PostGIS 实例不得标 PASS |
| Qdrant/RAG/Memory | 从 active/published 权威集重建隔离集合并通过双向差集和 ACL | 集合全丢失、部分写、旧别名、跨集合／跨项目 payload、revoked point 被拒绝 | collection config/index version、Point 差集、别名、降级日志 | 差集和越权为 0 后才切别名 |
| Workflow/Checkpoint | 原 thread 从最后稳定节点恢复，复核结果、报告和 context manifest 对账 | Checkpoint 后进程终止、Interrupt 重入、Artifact 缺失、权限／来源变化进入复核 | task/run/thread/checkpoint 时间线、幂等副作用、人工决策 | 不静默跳节点、不重复副作用 |
| 性能与容量 | 8.26.1 三类 P95、第五至七章代表链和容量快照达标 | 冷缓存、20 并发、池饱和、锁、磁盘／WAL 压力、索引重建竞争和超时 | 完整实验合同、原始 histogram、EXPLAIN JSON、资源曲线、错误率 | 条件不完整或只测热缓存不得通过 |
| 可观测性 | 每个阈值触发对应告警、trace 和 Runbook，恢复后自动关闭 | 高基数爆炸、敏感正文／凭据写日志、采集器断开、告警风暴 | 指标定义、合成触发、通知／升级时间、脱敏检查 | 无敏感泄漏；关键告警可行动 |

SQLite、Mock、静态 SQL 解析和单元测试可以提供快速反馈，但**不能**作为 PostgreSQL 17
的 RLS、锁、分区、约束、SECURITY DEFINER、`SKIP LOCKED`、PITR 或查询计划验收。
未提供真实 PostGIS、MinIO/S3、Qdrant、WAL 归档或多会话并发环境时，对应状态必须为
`GAP`，列出缺少的环境、待执行命令／场景、owner 和关闭条件，不能写成 `PASS`。

### 8.26.6 证据判定与发布门禁

每条测试结果只允许：`VERIFIED`（在声明环境实际运行且断言成立）、`FAILED`（实际运行
且断言失败）或 `GAP`（环境／数据／权限不足而未运行）。文档中的 SQL、示例输出、预期值、
他人历史截图、工具不存在时的跳过和“命令返回 0 但没有业务断言”都不是 VERIFIED。
自动化报告必须保留命令版本、环境 fingerprint、起止时间、stdout/stderr、退出码、断言、
失败样本和 Artifact digest；人工核验保存 reviewer、依据、时间和签名。

发布前最低证据集为：目标 PostgreSQL 17 迁移和目录验收；多角色双租户 RLS 正负向；
全部强 FK/CHECK/唯一／不可变状态机；幂等冲突和并发 Outbox；四类分区 DEFAULT/未来边界；
Q1/Q5 查询计划及 Q2/Q6 真实 PostGIS／多期病害计划；三类数据库 P95 与 20 并发基线；Artifact 精确版本哈希；
Workflow/Checkpoint 恢复；Qdrant RAG/Memory 双向差集；以及最近一个季度 RPO≤15 分钟、
RTO≤4 小时的隔离恢复。任何 P0 安全失败、数据差异、不可恢复强引用、无效索引、
DEFAULT 积压或过期演练都阻断发布；性能未达标可通过明确的容量修复后重测，不能仅靠
风险接受跳过数据安全和恢复门禁。

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
