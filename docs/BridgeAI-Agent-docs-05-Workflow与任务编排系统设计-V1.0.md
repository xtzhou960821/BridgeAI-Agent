# BridgeAI-Agent Architecture White Paper

# 第五章 Workflow 与任务编排系统设计
## Workflow & Orchestration Architecture

| 项目 | 内容 |
|---|---|
| 文档名称 | BridgeAI-Agent Architecture White Paper |
| 章节 | 第五章 Workflow 与任务编排系统设计 |
| 版本 | V1.0 |
| 文档状态 | 正式版 |
| 默认开发环境 | Mac Studio / Apple M3 Ultra / 512GB 统一内存 |
| 数据库 | PostgreSQL（本地部署） |
| Agent 编排框架 | LangGraph |
| 视觉推理 | YOLO26 / 本地边缘推理 |
| 本地大模型 | Apple MLX 优先 |
| 编制日期 | 2026-07-15 |

---

## 5.1 本章目的

本章定义 BridgeAI-Agent 的 Workflow 与任务编排系统，重点解决以下工程问题：

1. 将 Agent 的智能判断与确定性业务流程分离；
2. 让桥梁巡检任务在中断、失败或人工复核后继续执行；
3. 将 LangGraph 状态持久化到本地 PostgreSQL；
4. 统一管理 Tool 调用、任务状态、事件日志和成果文件；
5. 支持无人机、视觉识别、规范检索、处置建议和报告生成的完整闭环；
6. 防止 Agent 自由发挥导致流程不可控；
7. 为道路、隧道、智慧工地和多 Agent 协同预留演进空间。

本章不是 LangGraph 的通用教程，而是面向 BridgeAI-Agent 真实业务的可实施架构。

---

## 5.2 Workflow 与 Orchestration

### 5.2.1 Workflow

Workflow 强调预定义的业务步骤、状态转换、审批关口和异常分支。

```text
创建任务
  ↓
检查影像
  ↓
图像预处理
  ↓
病害识别
  ↓
统计分析
  ↓
规范检索
  ↓
人工复核
  ↓
生成报告
```

Workflow 适合处理顺序明确、必须执行、需要重试、需要审批和必须审计的流程。

### 5.2.2 Orchestration

Orchestration 强调根据任务上下文动态选择执行策略。Agent 可以决定：

- 是否需要预处理；
- 使用哪个 YOLO 模型版本；
- 是否进入低置信度复核；
- 是否查询特定规范；
- 是否执行历史病害对比；
- 报告应包含哪些章节；
- Tool 失败时采用何种降级方案。

### 5.2.3 BridgeAI-Agent 的组合模式

BridgeAI-Agent 不采用完全固定流程，也不采用完全自由 Agent，而采用：

> 固定业务骨架 + 有边界的 Agent 决策 + 标准 Tool 执行。

```text
Workflow 决定必须经过哪些关口
Agent 决定在关口内如何处理
Tool 负责实际执行
PostgreSQL 负责状态和证据持久化
人工负责关键结论确认
```

---

## 5.3 为什么必须有 Workflow

如果只使用一个能够调用 Tool 的大模型循环，系统可能：

- 重复调用同一 Tool；
- 跳过人工复核；
- 使用错误模型版本；
- 在数据不完整时生成报告；
- 任务失败后从头开始；
- 无法判断执行进度；
- 现场中断后丢失上下文；
- 难以形成审计记录；
- 无法可靠支持长时间任务；
- 无法向客户解释处理过程。

桥梁巡检要求结果可复核、过程可追溯、错误可恢复。Workflow 提供可靠性，Agent 提供灵活性。

---

## 5.4 总体架构

```text
┌────────────────────────────────────────────────────┐
│ 用户与业务入口                                     │
│ Web / 桌面端 / 遥控器数据 / 无人机任务 / API       │
└──────────────────────┬─────────────────────────────┘
                       ▼
┌────────────────────────────────────────────────────┐
│ Task Application Service                           │
│ 创建任务 / 权限校验 / 输入登记 / 返回任务状态      │
└──────────────────────┬─────────────────────────────┘
                       ▼
┌────────────────────────────────────────────────────┐
│ BridgeAI Workflow Orchestrator                      │
│ LangGraph StateGraph                                │
│ 状态路由 / Agent决策 / Tool调用 / Interrupt         │
│ Retry / Recovery / Human-in-the-loop                │
└───────────────┬────────────────┬───────────────────┘
                ▼                ▼
┌──────────────────────┐  ┌──────────────────────────┐
│ Tool Executor        │  │ PostgreSQL               │
│ YOLO/GIS/RAG/Report  │  │ Checkpoint/Task/Event    │
└──────────┬───────────┘  └──────────────────────────┘
           ▼
┌────────────────────────────────────────────────────┐
│ MLX / YOLO26 / 对象存储 / 文件系统 / Redis（可选） │
└────────────────────────────────────────────────────┘
```

---

## 5.5 职责边界

| 组件 | 负责 | 不负责 |
|---|---|---|
| API Service | 创建任务、查询状态、提交复核 | 不直接运行模型 |
| Workflow | 节点顺序、状态、恢复和分支 | 不实现检测算法 |
| Agent | 理解任务、选择策略、解释结果 | 不直接写数据库或渲染 PDF |
| Tool Executor | 统一调用、校验、超时和记录 | 不改变业务流程 |
| PostgreSQL | 任务、事件、Checkpoint、复核 | 不存储大体积原始影像 |
| Object Storage | 影像、模型、报告、中间文件 | 不保存任务逻辑 |
| Human Review | 复核关键结论 | 不人工串联全部步骤 |

---

## 5.6 主 Workflow

第一阶段定义：

```text
BridgeInspectionWorkflow
```

标准节点：

1. `initialize_task`
2. `validate_inputs`
3. `load_project_context`
4. `plan_execution`
5. `preprocess_images`
6. `run_damage_detection`
7. `validate_detection_results`
8. `calculate_damage_statistics`
9. `map_damage_location`
10. `retrieve_engineering_standards`
11. `generate_repair_advice`
12. `create_review_items`
13. `wait_for_human_review`
14. `apply_review_results`
15. `compose_report_data`
16. `generate_word_report`
17. `generate_pdf_report`
18. `archive_results`
19. `complete_task`

可选节点：

- `compare_historical_damage`
- `measure_crack_width`
- `measure_damage_area`
- `generate_gis_layer`
- `export_training_samples`

---

## 5.7 Workflow State

```python
from typing import Any, Literal, TypedDict

TaskStatus = Literal[
    "created", "validating", "planning", "running",
    "waiting_review", "resuming", "reporting",
    "completed", "failed", "cancelled",
]

class BridgeInspectionState(TypedDict, total=False):
    task_id: str
    thread_id: str
    project_id: str
    bridge_id: str
    user_id: str

    status: TaskStatus
    current_node: str
    previous_node: str | None
    progress: float

    input_batch_id: str
    input_files: list[str]
    input_metadata: dict[str, Any]

    plan_id: str
    plan_steps: list[dict[str, Any]]
    selected_model_version: str

    tool_execution_ids: list[str]
    detection_result_id: str | None
    statistics_result_id: str | None
    knowledge_result_ids: list[str]
    report_artifact_ids: list[str]

    review_required: bool
    review_item_ids: list[str]
    review_status: str | None
    reviewer_feedback: dict[str, Any] | None

    retry_count: int
    max_retry_count: int
    error_code: str | None
    error_message: str | None
    recovery_node: str | None

    final_summary: dict[str, Any] | None
```

### State 设计原则

1. 字段必须可以 JSON 序列化；
2. 大文件只保存路径或 Artifact ID；
3. 模型对象、数据库连接、文件句柄不得进入 State；
4. 关键检索字段同步写入业务任务表；
5. State 用于执行恢复，业务表用于查询统计；
6. 节点只返回状态增量；
7. 原始 Tool 结果独立保存；
8. State 必须有版本号。

---

## 5.8 状态生命周期

```text
CREATED
  ↓
VALIDATING
  ├── 输入缺失 ──> WAITING_INPUT
  └── 输入有效
          ↓
       PLANNING
          ↓
        RUNNING
          ├── 临时失败 ──> RETRYING ──> RUNNING
          ├── 需复核 ────> WAITING_REVIEW
          ├── 不可恢复 ──> FAILED
          └── 完成识别
                    ↓
                REPORTING
                    ↓
                COMPLETED
```

终态为 `completed`、`failed`、`cancelled`。进入终态后，不得静默覆盖历史结果。

---

## 5.9 LangGraph 图结构

```python
from langgraph.graph import END, START, StateGraph


def build_bridge_inspection_graph():
    builder = StateGraph(BridgeInspectionState)

    builder.add_node("initialize_task", initialize_task)
    builder.add_node("validate_inputs", validate_inputs)
    builder.add_node("load_project_context", load_project_context)
    builder.add_node("plan_execution", plan_execution)
    builder.add_node("preprocess_images", preprocess_images)
    builder.add_node("run_damage_detection", run_damage_detection)
    builder.add_node(
        "validate_detection_results",
        validate_detection_results,
    )
    builder.add_node(
        "calculate_damage_statistics",
        calculate_damage_statistics,
    )
    builder.add_node(
        "retrieve_engineering_standards",
        retrieve_engineering_standards,
    )
    builder.add_node("generate_repair_advice", generate_repair_advice)
    builder.add_node("human_review", human_review)
    builder.add_node("apply_review_results", apply_review_results)
    builder.add_node("generate_report", generate_report)
    builder.add_node("archive_results", archive_results)
    builder.add_node("mark_failed", mark_failed)

    builder.add_edge(START, "initialize_task")
    builder.add_edge("initialize_task", "validate_inputs")
    builder.add_edge("load_project_context", "plan_execution")
    builder.add_edge("plan_execution", "preprocess_images")
    builder.add_edge("preprocess_images", "run_damage_detection")
    builder.add_edge(
        "run_damage_detection",
        "validate_detection_results",
    )
    builder.add_edge(
        "calculate_damage_statistics",
        "retrieve_engineering_standards",
    )
    builder.add_edge(
        "retrieve_engineering_standards",
        "generate_repair_advice",
    )
    builder.add_edge("human_review", "apply_review_results")
    builder.add_edge("apply_review_results", "generate_report")
    builder.add_edge("generate_report", "archive_results")
    builder.add_edge("archive_results", END)
    builder.add_edge("mark_failed", END)

    builder.add_conditional_edges(
        "validate_inputs",
        route_after_validation,
        {"valid": "load_project_context", "invalid": "mark_failed"},
    )

    builder.add_conditional_edges(
        "validate_detection_results",
        route_after_detection_validation,
        {
            "review": "human_review",
            "continue": "calculate_damage_statistics",
            "failed": "mark_failed",
        },
    )

    return builder
```

每个节点只做一件事。节点过大会导致无法在中间形成 Checkpoint、失败后整体重跑、难以测试和复核。

---

## 5.10 PostgreSQL Checkpoint

LangGraph Checkpointer 保存线程在图执行过程中的状态快照，用于暂停恢复、人工复核、故障恢复和历史状态查看。

### 安装

```bash
pip install -U \
  langgraph \
  langgraph-checkpoint-postgres \
  "psycopg[binary,pool]"
```

### 同步示例

```python
from langgraph.checkpoint.postgres import PostgresSaver

DB_URI = (
    "postgresql://bridgeai:password@localhost:5432/"
    "bridgeai_agent?sslmode=disable"
)

builder = build_bridge_inspection_graph()

with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    # 首次初始化或迁移时调用
    checkpointer.setup()

    graph = builder.compile(checkpointer=checkpointer)

    config = {
        "configurable": {
            "thread_id": "task-20260715-0001",
        }
    }

    graph.invoke(
        {
            "task_id": "task-20260715-0001",
            "thread_id": "task-20260715-0001",
            "project_id": "project-001",
            "status": "created",
        },
        config=config,
    )
```

FastAPI 后端建议使用 `AsyncPostgresSaver`，并通过应用 lifespan 统一管理连接生命周期。`setup()` 不应在每次业务请求中执行。

### Checkpoint 与业务表边界

官方 Checkpointer 表只服务 LangGraph 内部状态。BridgeAI 自有业务表负责项目查询、进度展示、Tool 记录、人工审核、报告版本和权限。不得直接修改框架内部表结构。

长期项目记忆、历史病害和领域知识不应混入单个 `thread_id` 的 Checkpoint，应保存于项目表、知识库或 Store。生产环境还应设置 Checkpoint 保留期限、归档或清理策略，并对敏感 State 采用最小化存储、访问控制和加密保护；原始影像、模型文件和完整报告继续存储在对象存储或受控文件系统。

---

## 5.11 PostgreSQL Schema

建议：

```text
bridgeai_core       项目、桥梁、用户
bridgeai_workflow   任务、运行、事件、复核
bridgeai_tool       Tool及执行记录
bridgeai_model      模型和数据集
bridgeai_report     报告和版本
bridgeai_knowledge  规范和知识
public              LangGraph Checkpointer（第一阶段）
```

BridgeAI 自有业务表放在独立 Schema。大体积影像、模型和报告文件不直接存入 PostgreSQL。

---

## 5.12 核心数据库表

### workflow_tasks

```sql
CREATE TABLE bridgeai_workflow.workflow_tasks (
    id UUID PRIMARY KEY,
    thread_id VARCHAR(128) NOT NULL UNIQUE,
    project_id UUID NOT NULL,
    bridge_id UUID,
    task_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    current_node VARCHAR(128),
    progress NUMERIC(5, 2) NOT NULL DEFAULT 0,
    state_version INTEGER NOT NULL DEFAULT 1,
    selected_model_version VARCHAR(128),
    input_batch_id UUID,
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error_code VARCHAR(128),
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB
);

CREATE INDEX idx_workflow_tasks_project
ON bridgeai_workflow.workflow_tasks(project_id);

CREATE INDEX idx_workflow_tasks_status
ON bridgeai_workflow.workflow_tasks(status);
```

### workflow_runs

```sql
CREATE TABLE bridgeai_workflow.workflow_runs (
    id UUID PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES
        bridgeai_workflow.workflow_tasks(id),
    run_number INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL,
    start_node VARCHAR(128),
    end_node VARCHAR(128),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    duration_ms BIGINT,
    trigger_type VARCHAR(32) NOT NULL,
    triggered_by UUID,
    config JSONB NOT NULL DEFAULT '{}'::JSONB,
    UNIQUE(task_id, run_number)
);
```

### workflow_events

```sql
CREATE TABLE bridgeai_workflow.workflow_events (
    id BIGSERIAL PRIMARY KEY,
    task_id UUID NOT NULL,
    run_id UUID,
    trace_id VARCHAR(128) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    node_name VARCHAR(128),
    event_level VARCHAR(16) NOT NULL DEFAULT 'INFO',
    payload JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_workflow_events_task_time
ON bridgeai_workflow.workflow_events(task_id, created_at);
```

### workflow_reviews

```sql
CREATE TABLE bridgeai_workflow.workflow_reviews (
    id UUID PRIMARY KEY,
    task_id UUID NOT NULL,
    review_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    priority VARCHAR(16) NOT NULL DEFAULT 'normal',
    title VARCHAR(255) NOT NULL,
    description TEXT,
    input_data JSONB NOT NULL,
    suggested_result JSONB,
    final_result JSONB,
    reviewer_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    due_at TIMESTAMPTZ
);
```

### workflow_node_executions

```sql
CREATE TABLE bridgeai_workflow.workflow_node_executions (
    id UUID PRIMARY KEY,
    task_id UUID NOT NULL,
    run_id UUID NOT NULL,
    node_name VARCHAR(128) NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(32) NOT NULL,
    input_summary JSONB NOT NULL DEFAULT '{}'::JSONB,
    output_summary JSONB NOT NULL DEFAULT '{}'::JSONB,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    duration_ms BIGINT,
    error_code VARCHAR(128),
    error_message TEXT,
    idempotency_key VARCHAR(255) NOT NULL,
    UNIQUE(idempotency_key)
);
```

---

## 5.13 ID 语义

| ID | 含义 |
|---|---|
| task_id | 一项业务任务 |
| thread_id | LangGraph 持久化线程 |
| run_id | 某次实际执行 |

第一阶段可令 `thread_id = task_id`，但数据库中仍分别保存，以支持后续子流程和多线程。

---

## 5.14 节点规范

每个节点必须：

1. 只读取本节点需要的 State；
2. 通过 Service 或 Tool Executor 执行业务；
3. 只返回状态增量；
4. 不保存不可序列化对象；
5. 写事件日志；
6. 设置明确超时；
7. 支持幂等；
8. 捕获已知异常；
9. 未知异常交给统一错误节点处理；
10. 对结果进行 Schema 校验。

### 示例

```python
async def run_damage_detection(
    state: BridgeInspectionState,
) -> dict:
    execution = await tool_executor.execute(
        tool_name="yolo_damage_detection",
        context={
            "task_id": state["task_id"],
            "project_id": state["project_id"],
        },
        payload={
            "image_paths": state["input_files"],
            "model_version": state["selected_model_version"],
            "confidence_threshold": 0.35,
        },
    )

    if execution.status == "failed":
        raise WorkflowToolError(
            tool_name="yolo_damage_detection",
            error_code=execution.error_code,
            message=execution.error_message,
        )

    return {
        "previous_node": state.get("current_node"),
        "current_node": "run_damage_detection",
        "status": "running",
        "progress": 35.0,
        "detection_result_id": execution.data["result_id"],
        "tool_execution_ids": (
            state.get("tool_execution_ids", [])
            + [execution.execution_id]
        ),
    }
```

---

## 5.15 条件路由

Agent 不应使用任意自然语言控制节点。路由必须返回有限枚举。

```python
from typing import Literal


def route_after_detection_validation(
    state: BridgeInspectionState,
) -> Literal["review", "continue", "failed"]:
    if state.get("error_code"):
        return "failed"
    if state.get("review_required", False):
        return "review"
    return "continue"
```

复杂判断可由 Agent 生成结构化决策，再由 Policy Engine 校验。

---

## 5.16 Human-in-the-loop

必须支持人工复核的场景：

- 重大病害；
- 低置信度结果；
- 多模型冲突；
- 病害类别超出训练范围；
- 病害等级；
- 规范适用性；
- 处治建议；
- 正式报告签发；
- 无人机自主任务异常后的继续执行。

### Interrupt 节点

```python
from langgraph.types import interrupt


async def human_review(
    state: BridgeInspectionState,
) -> dict:
    decision = interrupt({
        "task_id": state["task_id"],
        "review_item_ids": state["review_item_ids"],
        "message": "请复核低置信度或关键病害结果",
        "allowed_actions": ["approve", "edit", "reject"],
    })

    return {
        "review_status": decision["action"],
        "reviewer_feedback": decision,
        "status": "resuming",
    }
```

### 恢复执行

```python
from langgraph.types import Command

config = {"configurable": {"thread_id": task_id}}

await graph.ainvoke(
    Command(resume={
        "action": "approve",
        "reviewer_id": "user-001",
        "comment": "已确认识别结果",
    }),
    config=config,
)
```

复核结果必须写业务表，恢复时必须使用原 `thread_id`，所有修改必须记录前后值。

`interrupt()` 恢复时会从所在节点的开头重新执行。因此，Interrupt 之前不得执行不可幂等的写库、发消息、生成正式文件或外部控制操作；应将副作用放在 Interrupt 之后、拆分为独立节点，或使用幂等键与已完成结果校验保护。

---

## 5.17 任务恢复

可恢复场景包括：

- FastAPI 重启；
- Mac Studio 重启；
- PostgreSQL 短暂断连；
- 本地模型服务重启；
- Tool 超时；
- 人工复核等待数小时或数天；
- 报告生成失败；
- 用户主动暂停。

恢复流程：

```text
读取 workflow_tasks
  ↓
确认任务不是终态
  ↓
通过 thread_id 加载 LangGraph State
  ↓
核对业务表与 Checkpoint
  ↓
判断最后稳定节点
  ↓
检查节点幂等结果
  ↓
恢复或重新执行当前节点
```

稳定恢复点建议设置在输入校验、图像预处理、病害识别、统计、人工复核、报告数据组装、Word 完成和 PDF 完成之后。

---

## 5.18 幂等设计

```python
import hashlib
import json


def build_idempotency_key(
    task_id: str,
    node_name: str,
    input_data: dict,
    version: str,
) -> str:
    normalized = json.dumps(
        input_data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()
    return f"{task_id}:{node_name}:{version}:{digest}"
```

应用：

- 同一模型和图像不重复推理；
- 相同审核结果不重复提交；
- 相同数据不重复生成正式报告；
- 任务恢复复用已成功 Tool 结果；
- Artifact 通过校验和判断是否存在。
- Interrupt 前的所有副作用均应具备幂等保护；必要时拆分为独立节点或受控 Task。

---

## 5.19 Retry 与补偿

### 可自动重试

- 临时数据库连接失败；
- 模型服务预热；
- 临时文件锁；
- 可恢复超时；
- 短暂进程间通信失败。

### 不自动重试

- 输入错误；
- 文件永久缺失；
- 模型版本不存在；
- 权限不足；
- 业务规则不满足；
- 无人机安全策略触发；
- 人工明确拒绝。

### 补偿示例

| 原操作 | 补偿 |
|---|---|
| 创建报告草稿 | 标记废弃，不物理删除 |
| 写入病害结果 | 创建新版本并关联旧版本 |
| 生成 Artifact | 标记 orphan，后台清理 |
| 创建复核项 | 取消并记录原因 |
| 发布正式报告 | 创建修订版，不覆盖原版 |

---

## 5.20 事件与可观测性

事件类型：

```text
TASK_CREATED
TASK_STARTED
NODE_STARTED
NODE_COMPLETED
NODE_FAILED
TOOL_STARTED
TOOL_COMPLETED
TOOL_FAILED
REVIEW_CREATED
REVIEW_COMPLETED
TASK_PAUSED
TASK_RESUMED
REPORT_GENERATED
TASK_COMPLETED
TASK_FAILED
```

关键指标：

- 任务成功率；
- 节点平均耗时；
- Tool 失败率；
- 重试次数；
- 人工复核比例；
- 恢复次数；
- 报告生成时长；
- 单任务图像量；
- 推理时长；
- 统一内存峰值；
- PostgreSQL 查询和 Checkpoint 写入时长。

---

## 5.21 物理世界 Workflow

BridgeAI-Agent 的部分任务发生在真实物理环境中。无人机任务与普通后台任务不同：

- 飞行状态实时变化；
- GPS、视觉定位和链路质量可能变化；
- 错误具有安全风险；
- 人工接管优先级最高；
- LLM 输出不能直接成为底层飞控指令；
- 任务暂停和飞行悬停不是同一概念；
- 现场状态必须由飞控和安全模块判定。

分层：

```text
BridgeAI-Agent Workflow
  ↓ 任务级编排
Mission Manager
  ↓ 航线级管理
Flight Safety Controller
  ↓ 安全规则与控制权
DJI Flight Controller
  ↓ 实时控制
无人机
```

Agent 只能提交高层任务，例如执行桥底短航线、暂停、请求人工接管、重新采集指定区域。Agent 不直接输出电机转速、姿态闭环参数或未经安全验证的实时控制量。

---

## 5.22 GPS 拒止场景预留

当前真实研发状态：

- YOLO26 已部署到妙算3；
- 已实现无人机边飞边识别；
- 遥控器实时画面可显示病害框；
- 正在验证无 GPS 时妙算3接管飞控；
- 当前短航线尚未成功执行；
- 现阶段采用双目视觉定位；
- 激光定位或 SLAM 作为后续增强。

本章只定义该任务在 Agent Workflow 中的位置，不在此决定具体飞控算法。

```text
MISSION_CREATED
  ↓
PRE_FLIGHT_CHECK
  ↓
TAKEOFF
  ↓
GPS_AVAILABLE?
  ├── 是 ──> GPS_MISSION
  └── 否 ──> VISION_POSITIONING_CHECK
                    ├── 有效 ──> REQUEST_CONTROL_HANDOVER
                    │                 ↓
                    │          SHORT_ROUTE_EXECUTION
                    └── 无效 ──> HOLD_AND_REQUEST_HUMAN
```

建议分别记录：

- `manual_control`
- `sdk_control_requested`
- `sdk_control_active`
- `positioning_valid`
- `mission_executing`
- `holding`
- `human_takeover_required`
- `aborted`

关键原则：

1. SDK 已接管不代表航线已执行；
2. 控制权、定位有效性、任务状态分别记录；
3. 无 GPS 时先验证视觉定位质量；
4. 短航线在受控条件下验证；
5. 异常优先悬停或人工接管；
6. 飞控安全逻辑不交给大语言模型；
7. Agent 只管理任务状态和证据。

---

## 5.23 FastAPI 接口

```http
POST /api/v1/workflow/tasks
GET  /api/v1/workflow/tasks/{task_id}
POST /api/v1/workflow/tasks/{task_id}/pause
POST /api/v1/workflow/tasks/{task_id}/resume
POST /api/v1/workflow/reviews/{review_id}/decision
POST /api/v1/workflow/tasks/{task_id}/cancel
```

### 应用生命周期

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


@asynccontextmanager
async def lifespan(app: FastAPI):
    cm = AsyncPostgresSaver.from_conn_string(DB_URI)
    checkpointer = await cm.__aenter__()
    await checkpointer.setup()

    builder = build_bridge_inspection_graph()
    app.state.workflow_graph = builder.compile(
        checkpointer=checkpointer
    )

    yield

    await cm.__aexit__(None, None, None)


app = FastAPI(lifespan=lifespan)
```

正式环境中应将数据库密码放入环境变量，设置连接池、超时和健康检查。

---

## 5.24 并发与资源控制

M3 Ultra 和 512GB 统一内存非常强，但仍需受控调度：

- 重型视觉推理节点受控并发；
- 报告生成与轻量数据库操作可并行；
- 同一模型由 Model Gateway 统一加载；
- 训练任务与在线巡检任务分离；
- YOLO、MLX LLM、Embedding 分别限流；
- 避免多个进程重复加载大模型；
- 大批量影像采用分片、受控并行和汇总节点。

```text
10000 张图片
  ↓
划分 100 个批次
  ↓
每批 100 张
  ↓
受控并行推理
  ↓
批次结果持久化
  ↓
最终汇总
```

---

## 5.25 版本与迁移

任务创建时固定：

- Workflow 版本；
- Tool 版本；
- 模型版本；
- Prompt 版本；
- 报告模板版本；
- 知识库版本。

正在运行的任务不得因代码升级自动切换到新 Workflow。

```python
def migrate_state_v1_to_v2(state_v1: dict) -> dict:
    return {
        **state_v1,
        "state_version": 2,
        "review_policy": {
            "low_confidence_threshold": 0.40,
        },
    }
```

---

## 5.26 测试策略

### 单元测试

- 状态路由；
- 节点输入输出；
- 幂等键；
- 异常分类；
- 复核决策；
- State 迁移。

### 集成测试

- LangGraph + PostgreSQL；
- Workflow + YOLO Tool；
- Workflow + RAG Tool；
- Workflow + Report Tool；
- Interrupt + Resume；
- 服务重启恢复；
- Tool 超时重试。

### 故障注入

- 推理中终止进程；
- PostgreSQL 短时断开；
- 报告写文件失败；
- Checkpoint 后服务重启；
- 人工复核等待 24 小时；
- Artifact 被删除；
- 模型版本下线；
- 输入图片部分损坏。

### 验收闭环

1. 创建任务；
2. 保存输入；
3. 调用 YOLO；
4. 保存识别结果；
5. 产生低置信度复核；
6. 暂停；
7. 人工提交审核；
8. 从原位置恢复；
9. 查询知识；
10. 生成报告；
11. 归档；
12. 完整追溯。

---

## 5.27 第一阶段计划

### Milestone 1：骨架

- 建立 State；
- 建立 StateGraph；
- 使用模拟 Tool；
- 跑通节点和路由；
- 使用内存 Checkpointer 验证。

### Milestone 2：PostgreSQL

- 安装 PostgreSQL Checkpointer；
- 建立业务 Schema；
- 建立任务、事件和复核表；
- 验证服务重启恢复。

### Milestone 3：真实 Tool

- 接入 YOLO26；
- 接入统计 Tool；
- 接入报告 Tool；
- 保存 Tool 执行记录。

### Milestone 4：人工复核

- 实现 Interrupt；
- 实现前端复核页面；
- 实现 Resume；
- 保存审核记录。

### Milestone 5：真实案例

- 使用真实桥梁影像；
- 跑通采集到报告；
- 输出时间和错误统计；
- 形成第一个正式演示案例。

---

## 5.28 推荐源码结构

```text
bridgeai-agent/
├── app/
│   ├── api/
│   │   └── workflow_routes.py
│   ├── workflows/
│   │   ├── bridge_inspection/
│   │   │   ├── graph.py
│   │   │   ├── state.py
│   │   │   ├── nodes.py
│   │   │   ├── routes.py
│   │   │   ├── policies.py
│   │   │   └── migrations.py
│   │   └── registry.py
│   ├── services/
│   │   ├── workflow_service.py
│   │   ├── review_service.py
│   │   └── recovery_service.py
│   ├── repositories/
│   ├── tools/
│   ├── models/
│   ├── database/
│   └── main.py
└── tests/
    ├── unit/
    ├── integration/
    └── scenarios/
```

---

## 5.29 架构决策

### ADR-005-001：采用 LangGraph

**决定：** 使用 StateGraph。

**原因：** 支持持久化、中断恢复、人工复核、长时间运行和细粒度状态图。

**代价：** 需要严格设计节点和 State，框架升级必须回归测试。

### ADR-005-002：PostgreSQL 同时承载业务状态与 Checkpoint

**决定：** 第一阶段使用本机 PostgreSQL。

**原因：** 已部署，事务与 JSONB 能力强，适合本地优先和数据保密。

**约束：** Checkpoint 与业务表分离，大文件不进数据库。

### ADR-005-003：限制 Agent 自由度

**决定：** Agent 只能在预设节点和策略范围内决策。

**原因：** 工程可靠、便于审计、防止跳过关键步骤、支持正式报告责任链。

### ADR-005-004：保持编排框架边界

**决定：** 第一阶段以 LangGraph 为唯一核心编排运行时；领域 State、Tool SDK、业务任务表、事件模型和 Artifact 协议不依赖 LangGraph 私有类型。

**原因：** 降低框架升级、独立 Agent 服务拆分和后续 Google ADK 架构验证的成本，同时避免 Dify 与 LangGraph 对同一任务形成双重状态主控。

**约束：** MCP 用于 Tool 互操作，A2A 或受控服务 API 用于独立 Agent 协作；Dify 仅作为可选低代码应用入口，不负责桥梁巡检长任务的恢复、重试和 Checkpoint。

---

## 5.30 本章结论

BridgeAI-Agent 的 Workflow 架构采用：

> LangGraph StateGraph + PostgreSQL Checkpoint + 业务状态表 + 标准 Tool + Human-in-the-loop。

核心不是让 Agent 任意行动，而是让 Agent 在工程规则和状态机约束下完成动态决策。

第一阶段最重要的成果是：

- 一个稳定的桥梁巡检 Workflow；
- 一个清晰、可迁移的 State；
- 一套可恢复的 PostgreSQL 持久化机制；
- 一个完整的人工复核闭环；
- 一套可审计的 Tool 调用记录；
- 一个从真实影像到 Word/PDF 报告的端到端案例。

对于无人机桥底巡检，Workflow 层负责记录任务、控制权、定位状态、异常中止和人工接管；底层实时飞控与安全控制仍由专用飞控系统和确定性程序负责，不能直接交给大语言模型。

---

## 参考资料

1. LangGraph 官方文档：Persistence  
   https://docs.langchain.com/oss/python/langgraph/persistence
2. LangGraph 官方文档：Interrupts  
   https://docs.langchain.com/oss/python/langgraph/interrupts
3. LangGraph 官方文档：Graph API  
   https://docs.langchain.com/oss/python/langgraph/graph-api
4. LangGraph 官方文档：Memory / PostgreSQL Checkpointer  
   https://docs.langchain.com/oss/python/langgraph/add-memory
5. PostgreSQL 官方网站  
   https://www.postgresql.org/
6. Google Agent Development Kit：Technical Overview  
   https://adk.dev/get-started/about/
7. Dify Workflow Studio  
   https://www.dify.ai/workflows

---

## 修订记录

| 版本 | 日期 | 修订说明 |
|---|---|---|
| V1.0 | 2026-07-15 | 正式发布，纳入 LangGraph、PostgreSQL、人工复核、任务恢复及 GPS 拒止场景 Workflow 预留设计 |
