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

`damage_observations.current_revision_id/current_revision_no` 是唯一的默认当前指针，两列必须同时为空或同时非空。为解决观测与修订的闭环外键，先创建两张表，再以 `ALTER TABLE` 添加同观测、组织、项目的可延迟组合外键。新观测允许在首个修订落库前保持空指针，但 `pending_review` 和 `confirmed` 观测必须已指向同状态修订。指针切换更新观测的 `updated_at/updated_by/version`，并由 8.19 记录审计事件。

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
BEFORE INSERT OR UPDATE ON bridgeai_inspection.damage_observations
FOR EACH ROW
EXECUTE FUNCTION bridgeai_inspection.validate_damage_observation();

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

## 8.16 RAG 知识库数据模型

## 8.17 Memory 与 Context 数据模型

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
