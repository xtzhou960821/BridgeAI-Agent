# BridgeAI-Agent Chapter 7 Memory and Project Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 编制并验证第七章《Memory 与项目上下文设计》V1.0，形成可指导桥梁与道路巡检 AI Agent 第一阶段研发和验收的完整工程设计。

**Architecture:** 采用分层、可治理的 Memory 架构，将任务记忆、项目记忆、用户与组织偏好、运行经验记忆分开管理。PostgreSQL 保存权威记忆记录、权限、版本和审计，MinIO 保存大型上下文 Artifact，独立语义索引用于可重建召回；LangGraph Checkpoint 仅负责运行恢复，Context Builder 负责权限过滤、排序、压缩和受控注入。

**Tech Stack:** Markdown、PostgreSQL、LangGraph Checkpointer/Store、Qdrant 或等价语义索引、MinIO、Pydantic 数据契约、BridgeAI Tool SDK、LangGraph Workflow、官方技术资料。

## Global Constraints

- 创建 docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md，并仅在最终任务中同步 README.md 的实际文档清单。
- 不修改前六章正文；如发现跨章矛盾，在第七章中通过职责边界和引用说明解决。
- 聚焦桥梁与道路巡检 AI Agent，不引入智慧工地文档线或 temp/ 中另一套第七章结构。
- 保持 LangGraph Checkpoint、Workflow State、Memory、RAG 和业务事实五类能力边界清晰。
- PostgreSQL 是记忆内容、来源、版本、权限、状态和审计的权威数据源；MinIO 保存大型 Artifact；语义索引必须可重建且不得作为权威事实源。
- LangGraph Store 只作为框架适配接口，业务语义、权限和生命周期不得绑定其内部实现。
- 自动提取内容默认进入候选状态；高风险项目事实必须绑定权威业务记录或人工确认。
- 正式评定、病害等级、处治决策、设备控制和报告签发不得由 Memory 直接触发。
- 权限过滤必须先于语义召回；跨项目默认隔离；删除、撤销和失效必须传播到缓存、索引和派生摘要。
- 核验 2026-07-29 当日仍可能变化的软件能力，仅引用官方技术资料。
- 本章不编写完整数据库 DDL、完整服务代码、MCP Server 实现或通用 Prompt 库。

---

### Task 1: 建立官方资料基线与完整章节骨架

**Files:**
- Create: docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md
- Read: docs/superpowers/specs/2026-07-29-chapter-7-memory-design.md
- Read: docs/md/BridgeAI-Agent-第一章-项目背景与建设目标-V1.0.md
- Read: docs/md/BridgeAI-Agent-第三章-Agent总体设计-V1.0.md
- Read: docs/md/BridgeAI-Agent-第五章-Workflow与任务编排系统设计-V1.0.md
- Read: docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md

**Interfaces:**
- Consumes: 已批准的第七章设计、前六章术语、Memory Manager 边界、Workflow 持久化边界和 RAG 证据边界。
- Produces: 含文档信息、7.1-7.27、参考资料和修订记录的完整 Markdown 骨架。

- [ ] **Step 1: 复核跨章术语和责任边界**

Run:

~~~bash
rg -n -i "Memory|记忆|Checkpoint|Workflow State|RAG|项目上下文|Context Builder|PostgreSQL|Qdrant|MinIO|人工复核" docs/md/BridgeAI-Agent-{第一章-项目背景与建设目标,第三章-Agent总体设计,第五章-Workflow与任务编排系统设计,第六章-RAG行业知识库设计}-V1.0.md
~~~

Expected: 输出能够确认 Checkpoint 用于线程恢复、Memory 用于跨步骤和跨任务上下文、RAG 用于可引用外部知识、业务表用于权威工程事实。

- [ ] **Step 2: 核验 LangGraph Memory 与 Persistence 官方资料**

仅使用以下官方资料确认当前能力：

- LangGraph Persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph Memory: https://docs.langchain.com/oss/python/langgraph/add-memory
- LangChain Memory Overview: https://docs.langchain.com/oss/python/concepts/memory
- LangGraph PostgresStore Reference: https://reference.langchain.com/python/langgraph.store.postgres/base/PostgresStore

Expected: 正文可以准确说明 Checkpointer 按 thread 保存状态快照，Store 支持跨 thread 命名空间，PostgresStore 可持久化 Store 数据并可选启用语义索引；这些框架能力通过适配层使用，不直接充当 BridgeAI 业务权限模型。

- [ ] **Step 3: 核验存储、权限和安全官方资料**

仅使用以下官方资料：

- PostgreSQL Row Security Policies: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- Qdrant Payload: https://qdrant.tech/documentation/concepts/payload/
- Qdrant Filtering: https://qdrant.tech/documentation/search/filtering/
- MinIO Object Versioning: https://docs.min.io/aistor/administration/objects-and-versioning/versioning/
- OWASP LLM Prompt Injection Prevention: https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html
- OWASP AI Agent Security: https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html

Expected: 正文只陈述官方资料支持的能力，并把 RLS、Payload Filter、对象版本和提示注入防护作为纵深防御，不把任一机制描述为单独的完整安全边界。

- [ ] **Step 4: 创建正式章节骨架**

使用 apply_patch 创建目标文件，包含总标题、章节标题、V1.0 文档信息表、7.1 至 7.27、参考资料和修订记录。章节名称与批准的设计说明完全一致。

- [ ] **Step 5: 校验骨架完整性**

Run:

~~~bash
rg -n '^#{1,3} ' docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md
~~~

Expected: 7.1 至 7.27 各出现一次且顺序正确，末尾依次为参考资料和修订记录。

- [ ] **Step 6: 提交章节骨架**

Run:

~~~bash
git add -- docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md
git commit -m "docs: scaffold chapter 7 memory design"
~~~

Expected: 提交只包含新建的第七章文件。

---

### Task 2: 编写定位、场景、原则、分类、架构与统一对象

**Files:**
- Modify: docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md

**Interfaces:**
- Consumes: 第一至第六章的 Agent、Workflow、Tool、RAG 和业务数据边界。
- Produces: 7.1-7.7，以及后续章节统一使用的 MemoryScope、MemoryType、MemoryStatus、SourceRef 和 MemoryRecord 概念契约。

- [ ] **Step 1: 编写 7.1-7.2 本章目标和职责边界**

用责任矩阵区分 Checkpointer、Workflow State、Memory、RAG、业务数据、Context Builder、Agent、Tool 和人工复核。明确任务记忆不是完整 Checkpoint，项目记忆不是业务主数据，运行经验不是工程证据。

- [ ] **Step 2: 编写 7.3 典型巡检应用场景**

覆盖多期巡检复用、中断恢复和交接、人工修订复用、报告偏好继承、运行失败模式提示以及归档和删除传播。每个场景说明触发事件、所需记忆、权威来源、自动化程度和人工复核点。

- [ ] **Step 3: 编写 7.4 设计原则**

定义 source before memory、candidate by default、permission before recall、structured fact first、scope isolation、immutable revision、budgeted context、explicit forgetting、local first、auditable by default 和 graceful degradation。

- [ ] **Step 4: 编写 7.5 记忆分类、作用域与风险分级**

定义四类记忆、task/project/user/organization/system 五类作用域、low/medium/high/critical 四级风险和偏好继承规则。说明规范和案例归入 RAG，模型经验、错误模式和标注经验归入运行经验记忆。

- [ ] **Step 5: 编写 7.6 总体架构**

包含写入、存储、召回、上下文组装、反馈和遗忘架构图；分别说明写路径、读路径、反馈路径、控制面、数据面及各存储分工。

- [ ] **Step 6: 编写 7.7 统一记忆对象与数据契约**

提供 MemoryScope、SourceRef、MemoryRecord、MemoryStatus 和 MemoryRiskLevel 的 Pydantic 示例。MemoryRecord 字段与批准设计中的统一记忆对象保持一致。

- [ ] **Step 7: 校验边界和契约**

Run:

~~~bash
rg -n "class MemoryScope|class SourceRef|class MemoryRecord|MemoryStatus|MemoryRiskLevel|Checkpoint|Workflow State|RAG|业务事实|人工复核" docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md
~~~

Expected: 五个契约名称均存在，且每种邻接能力的边界至少有一处明确说明。

- [ ] **Step 8: 提交总体架构与统一对象**

Run:

~~~bash
git add -- docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md
git commit -m "docs: define chapter 7 memory architecture"
~~~

Expected: 提交包含完整的 7.1-7.7，不含空节或占位文本。

---

### Task 3: 编写来源、候选处理、发布版本与存储索引

**Files:**
- Modify: docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md

**Interfaces:**
- Consumes: Task 2 的 MemoryRecord、SourceRef、作用域和风险分级。
- Produces: 7.8-7.11、MemoryProposalInput、候选状态机、幂等键、索引一致性和存储职责。

- [ ] **Step 1: 编写 7.8 记忆来源与写入触发**

定义用户明确操作、Workflow 事件、ToolResult、Artifact、人工复核、报告签发、项目归档、业务事实变化和系统评测等来源。提供触发矩阵，标明自动候选、规则确认、人工确认和禁止写入四种处理方式。

- [ ] **Step 2: 编写 7.9 候选提取与处理流水线**

定义流程：

~~~text
captured → classified → deduplicated → risk_assessed → source_bound
         → validating → review_pending → active
                         ├→ rejected
                         ├→ conflicted
                         └→ quarantined
~~~

说明内容哈希、来源事件 ID、提取器版本和作用域组成幂等键。提供 MemoryProposalInput 契约，并要求模型输出只能创建 candidate，不能绕过 Policy Engine 写 active。

- [ ] **Step 3: 编写 7.10 校验、确认、发布与版本管理**

定义格式、来源、权限、作用域、敏感级别、重复和冲突校验；定义不同风险记忆的确认门；解释 active、superseded、expired、revoked、quarantined、tombstoned 和 deleted。修订生成新 memory_id 和 supersedes_id，不原地覆盖。

- [ ] **Step 4: 编写 7.11 存储、索引与职责分工**

提供 PostgreSQL、MinIO、语义索引、LangGraph Store、Checkpointer、Redis 和 Workflow State 的责任矩阵。明确 PostgreSQL 先提交、Outbox 异步更新索引；Memory 与 RAG 使用独立集合和生命周期；权限字段召回前过滤；删除先停止召回再清理派生物；完整 DDL 留给第八章。

- [ ] **Step 5: 校验写入和生命周期闭环**

Run:

~~~bash
rg -n "class MemoryProposalInput|candidate|review_pending|active|superseded|expired|revoked|quarantined|tombstoned|deleted|幂等|Outbox|索引重建" docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md
~~~

Expected: 候选、确认、冲突、替代、失效、撤销、隔离和删除均有确定性处理路径。

- [ ] **Step 6: 提交记忆写入与存储设计**

Run:

~~~bash
git add -- docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md
git commit -m "docs: define chapter 7 memory lifecycle"
~~~

Expected: 提交完整覆盖 7.8-7.11。

---

### Task 4: 编写检索、Context Builder、压缩和分层记忆

**Files:**
- Modify: docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md

**Interfaces:**
- Consumes: Task 2 的 MemoryRecord 和 Task 3 的状态、存储及索引规则。
- Produces: 7.12-7.17、MemorySearchInput、MemorySearchResult、ContextManifest 和 ContextPack 契约。

- [ ] **Step 1: 编写 7.12 检索、过滤、排序与去重**

定义权限和状态过滤先于语义召回；组合精确、结构化、时间和语义检索；使用相关度、新鲜度、来源可信度、确认状态、作用域距离和风险惩罚排序；折叠同源版本和重复摘要；冲突记忆并列返回。提供 MemorySearchInput 和 MemorySearchResult。

- [ ] **Step 2: 编写 7.13 Context Builder 与 Token 预算**

固定保留系统规则、安全边界、任务目标和权限上下文；节点状态和 Tool 契约按需保留；各类记忆使用可配置预算；至少预留 15% 给当前 Tool 输出、异常和响应空间。提供 ContextManifest 和 ContextPack，并记录来源、排序、裁剪、压缩、Token 和哈希。

- [ ] **Step 3: 编写 7.14 上下文压缩与摘要**

区分规则裁剪、滑动窗口、分层摘要、结构化事实保留、增量摘要和人工确认摘要。摘要必须保留否定关系、数值、单位、时间、资产与构件标识、风险、人工修订和来源；高风险摘要进入项目记忆前执行字段比对或人工复核。

- [ ] **Step 4: 编写 7.15 项目上下文设计**

定义 Project Context Profile，包括项目标识、资产范围、构件映射、术语、报告规则、复核流程、历史任务摘要、有效记忆引用和归档状态。桥梁、构件、病害事实仍从业务数据读取。

- [ ] **Step 5: 编写 7.16 任务记忆设计**

定义目标变化、阶段摘要、已完成步骤、ToolResult 引用、人工复核、未决事项和降级原因。说明与 Checkpoint 的恢复关系，以及同一任务跨 thread 的汇总规则。

- [ ] **Step 6: 编写 7.17 用户与组织偏好设计**

定义偏好来源、继承顺序、显式确认、撤销、有效期和安全策略不可覆盖规则。举例说明报告格式、单位制、命名和通知选项，不保存密码、令牌或非必要个人信息。

- [ ] **Step 7: 校验读链路和上下文契约**

Run:

~~~bash
rg -n "class MemorySearchInput|class MemorySearchResult|class ContextManifest|class ContextPack|权限过滤|Token|否定关系|数值|单位|Checkpoint|Project Context Profile" docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md
~~~

Expected: 四个契约存在，权限先于召回、预算裁剪、摘要保真和任务/项目边界均有明确规则。

- [ ] **Step 8: 提交检索与上下文组装设计**

Run:

~~~bash
git add -- docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md
git commit -m "docs: define chapter 7 context assembly"
~~~

Expected: 提交完整覆盖 7.12-7.17。

---

### Task 5: 编写反馈、遗忘、服务协议、系统集成与运行治理

**Files:**
- Modify: docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md

**Interfaces:**
- Consumes: Task 3 的生命周期和 Task 4 的召回及 ContextPack。
- Produces: 7.18-7.24、MemoryFeedbackInput、MemoryCorrectionInput、MemoryForgetInput、MemoryOperationResult、错误码和降级矩阵。

- [ ] **Step 1: 编写 7.18 反馈、冲突、更正与负向记忆**

定义 accepted、ignored、corrected、rejected 和 reported 五类反馈。冲突不得自动覆盖，权威业务事实和最新人工确认优先；人工否定内容形成负向记录和回归样例。提供 MemoryFeedbackInput 和 MemoryCorrectionInput。

- [ ] **Step 2: 编写 7.19 生命周期、保留与遗忘机制**

定义创建、确认、使用、复核、替代、失效、撤销、归档、墓碑和删除。项目结束后停止默认召回并进入保留评估；删除传播覆盖 PostgreSQL 内容、MinIO Artifact、语义索引、缓存和派生摘要；清理未完成时保持不可召回；删除失败进入补偿和告警。

- [ ] **Step 3: 编写 7.20 Memory Service/Tool 协议**

定义 memory.propose、memory.confirm、memory.search、memory.feedback、memory.correct、memory.revoke、memory.forget 和 context.build。提供 MemoryForgetInput 和 MemoryOperationResult。Agent 写操作经过 Policy Engine；context.build、高风险确认、跨项目发布和删除传播不能由模型自由调用。

错误码至少包括 MEM-400-SCOPE_INVALID、MEM-403-DENIED、MEM-404-NOT_FOUND、MEM-409-CONFLICT、MEM-412-SOURCE_REQUIRED、MEM-422-VALIDATION_FAILED、MEM-423-QUARANTINED、MEM-429-RATE_LIMITED、MEM-503-STORE_UNAVAILABLE 和 MEM-504-TIMEOUT。

- [ ] **Step 4: 编写 7.21 与 Agent、Workflow 和 RAG 集成**

包含调用时序：

~~~text
Workflow Node → Context Builder → Memory Service → PostgreSQL／Semantic Index
              → ContextPack → Agent → Tool／RAG → Review → Memory Candidate
~~~

说明 Checkpoint 恢复不自动生成长期记忆；Workflow State 只保存 memory_id、摘要和 context_manifest_id；RAG 证据必须按当前权限和版本重新读取；业务事实修订触发相关记忆重新校验；报告签发和人工复核是高价值候选触发点。

- [ ] **Step 5: 编写 7.22 权限、隐私与记忆污染防护**

覆盖组织、项目、用户、角色、敏感级别、RLS 纵深防御、Qdrant Payload Filter、对象签名访问、缓存隔离、日志脱敏、提示注入、持久化攻击和跨项目泄漏。权限异常默认拒绝，外部文本和模型输出均按不可信内容处理。

- [ ] **Step 6: 编写 7.23 缓存、性能、降级与资源控制**

安全缓存键至少包含 organization_id、project_id、user_id、role_set_hash、ACL 版本、query_hash、memory_version 和 retrieval_config_version。

定义降级顺序：

1. 语义索引失败时使用 PostgreSQL 结构化检索；
2. 摘要失败时返回原始引用且不写入不完整记忆；
3. Memory 不可用时仅使用 Workflow State、业务数据和 RAG；
4. 权限判断失败时拒绝召回；
5. 写入失败不阻断专业 Tool 结果落库，但创建补偿任务。

- [ ] **Step 7: 编写 7.24 可观测性、审计与异常恢复**

关联 trace_id、task_id、thread_id、run_id、memory_id、context_manifest_id 和 tool_execution_id。列出写入、召回、压缩、冲突、越权、删除和补偿指标，以及污染、越权、删除失败、索引滞后和摘要失真的告警。

- [ ] **Step 8: 校验服务和治理闭环**

Run:

~~~bash
rg -n "class MemoryFeedbackInput|class MemoryCorrectionInput|class MemoryForgetInput|class MemoryOperationResult|MEM-403-DENIED|MEM-409-CONFLICT|MEM-503-STORE_UNAVAILABLE|memory.propose|memory.search|memory.forget|context.build|context_manifest_id" docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md
~~~

Expected: 四个契约、八个操作、关键错误码和跨系统关联 ID 均存在。

- [ ] **Step 9: 提交服务协议与运行治理**

Run:

~~~bash
git add -- docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md
git commit -m "docs: define chapter 7 memory governance"
~~~

Expected: 提交完整覆盖 7.18-7.24。

---

### Task 6: 完成评测、实施范围、ADR、参考资料和仓库索引

**Files:**
- Modify: docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md
- Modify: README.md

**Interfaces:**
- Consumes: 7.1-7.24 的全部边界、契约、流程和运行规则。
- Produces: 7.25-7.27、参考资料、修订记录、实际文档索引和最终可交付 V1.0。

- [ ] **Step 1: 编写 7.25 评测与测试体系**

固定首期指标：

- 越权召回为 0；
- 无来源高风险事实进入 active 为 0；
- 已撤销、删除或过期记忆再次召回为 0；
- 上下文项目事实来源可解析比例为 100%；
- 关键事实、否定关系、数值、单位和时间的摘要保真率不低于 98%；
- 已确认目标记忆 Recall@10 不低于 90%；
- 自动覆盖权威事实为 0，冲突标记召回率为 100%；
- 20 个并发会话下，不含模型生成的检索和组装 P95 不高于 1.5 秒；
- 关键操作审计覆盖率为 100%。

覆盖单元、契约、集成、权限负向、提示注入、故障注入、删除传播、摘要回归和真实项目验收。

- [ ] **Step 2: 编写 7.26 第一阶段实施范围与架构决策**

定义契约与权威存储、写入治理、检索与 Context Builder、系统集成与降级、真实项目验收五个里程碑。

记录：

- ADR-007-001：Memory 与 LangGraph Checkpoint 分离；
- ADR-007-002：PostgreSQL 为权威存储，语义索引为派生物；
- ADR-007-003：自动提取默认创建候选记忆；
- ADR-007-004：权限过滤先于语义召回；
- ADR-007-005：高风险项目事实绑定权威来源或人工确认；
- ADR-007-006：每次组装生成 Context Manifest；
- ADR-007-007：撤销和删除先停止召回，再清理派生物。

每条 ADR 写明背景、决策、理由、代价和约束。

- [ ] **Step 3: 编写 7.27 本章结论、参考资料和修订记录**

总结 Memory 的成功标准并衔接第八章。参考资料只使用 Task 1 核验的官方页面，注明 2026-07-29 核验日期。修订记录写明 V1.0 正式发布及覆盖范围。

- [ ] **Step 4: 更新 README 实际文档索引**

使用 rg --files docs/md 获取真实文件名，修正 README 中失效的 docs-01、docs/docx 和智慧工地主线描述。主文档列表准确列出第一至第七章，并说明 temp/ 是历史参考和非当前正式目录。

- [ ] **Step 5: 检查章节编号和 Markdown 结构**

Run:

~~~bash
rg -n '^## 7\.[0-9]+ ' docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md
fences=$(rg -c '^```' docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md)
test $((fences % 2)) -eq 0
git diff --check
~~~

Expected: 7.1 至 7.27 各出现一次且顺序正确，代码围栏为偶数，差异检查无错误。

- [ ] **Step 6: 检查占位、范围和关键契约**

Run:

~~~bash
rg -n "TBD|TODO|FIXME|待补充|待确认|后续确定|智慧工地|BridgeAI-Site" docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md || true
rg -n "MemoryRecord|MemoryProposalInput|MemorySearchInput|MemorySearchResult|ContextManifest|ContextPack|MemoryFeedbackInput|MemoryCorrectionInput|MemoryForgetInput|MemoryOperationResult" docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md
~~~

Expected: 第一条命令没有命中；第二条命令中的十个契约名称均至少出现一次。

- [ ] **Step 7: 检查跨章一致性和 README 路径**

Run:

~~~bash
rg -n "Checkpoint|Workflow State|RAG|业务事实|人工复核|PostgreSQL|Qdrant|MinIO" docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md
rg --files docs/md | sort
git status --short
~~~

Expected: 第七章保持批准的五类能力边界；README 列出的第一至第七章均存在；工作区只包含计划内变更。

- [ ] **Step 8: 最终提交**

Run:

~~~bash
git add -- docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md README.md
git commit -m "docs: complete chapter 7 memory and project context design"
~~~

Expected: 最终提交补齐 7.25-7.27、参考资料、修订记录和 README 索引；分支工作区干净。

---

## Final Verification

Run:

~~~bash
git status --short --branch
git log --oneline --decorate -8
git diff main...HEAD --check
rg -n '^## 7\.[0-9]+ ' docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md
rg -n "TBD|TODO|FIXME|待补充|待确认|后续确定|智慧工地|BridgeAI-Site" docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md || true
~~~

Expected:

- 工作区无未提交变更；
- 第七章相关提交连续且可审阅；
- main...HEAD 差异无空白错误；
- 7.1 至 7.27 完整有序；
- 正文无占位文本或智慧工地范围漂移。
