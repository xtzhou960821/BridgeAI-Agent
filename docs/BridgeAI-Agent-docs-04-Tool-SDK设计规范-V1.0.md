# BridgeAI-Agent Architecture White Paper

# 第四章 Tool SDK 设计规范

| 项目 | 内容 |
|---|---|
| 文档名称 | BridgeAI-Agent Architecture White Paper |
| 章节 | 第四章 Tool SDK 设计规范 |
| 版本 | V1.0 |
| 状态 | 正式版 |
| 默认开发环境 | Mac Studio / Apple M3 Ultra / 512GB 统一内存 |
| 数据库 | PostgreSQL（本地部署） |
| 编制日期 | 2026-07-14 |

---

## 4.1 本章目标

本章定义 BridgeAI-Agent 的 Tool 设计规范、接口协议、注册机制、执行模型、错误处理、安全边界、版本管理、测试要求和首批 Tool 实现建议。

Tool 是 BridgeAI-Agent 的核心业务资产。

Agent 的能力上限，取决于可用 Tool 的质量，而不是 Prompt 写得有多复杂。

---

## 4.2 Tool 的定义

Tool 是一个具备明确输入、明确输出、独立职责、可测试、可审计、可版本化的专业能力单元。

Tool 可以封装：

- Python 函数；
- 本地模型；
- MLX 推理服务；
- YOLO26 推理；
- FastAPI 服务；
- PostgreSQL 查询；
- GIS 算法；
- 文件处理；
- 报告生成；
- RAG 检索；
- 外部系统接口。

Tool 不等于任意函数。只有满足统一协议、Schema、日志、异常处理和版本管理要求的能力，才能注册为正式 Tool。

---

## 4.3 Tool 设计原则

### 4.3.1 单一职责

一个 Tool 应只完成一类明确工作。

不推荐：

```text
analyze_everything_and_generate_report
```

推荐：

```text
validate_images
preprocess_images
detect_damage
measure_crack
calculate_statistics
retrieve_standard
generate_report
```

### 4.3.2 输入输出结构化

禁止依赖模糊自然语言参数。

输入和输出必须使用 Pydantic Model 或 JSON Schema 描述。

### 4.3.3 可独立测试

Tool 必须可以脱离 Agent 单独运行。

### 4.3.4 幂等

相同输入和相同版本应产生可预期结果，或明确记录随机性来源。

### 4.3.5 可追溯

每次调用应记录：

- tool_name；
- tool_version；
- task_id；
- input_hash；
- 参数；
- 开始时间；
- 结束时间；
- 执行状态；
- 输出摘要；
- artifact；
- 错误信息。

### 4.3.6 可替换

Agent 不应感知 YOLO、MLX、FastAPI 或本地函数的具体实现。

### 4.3.7 本地优先

默认优先调用本地 Tool，只有在策略允许时才使用云端服务。

---

## 4.4 Tool 分类

### 感知类 Tool

- YOLO 病害检测；
- 病害分割；
- OCR；
- 构件识别；
- 图像质量检测；
- 重复图像检测。

### 测量类 Tool

- 裂缝长度测量；
- 裂缝宽度估算；
- 病害面积统计；
- 像素到实际尺寸换算；
- 标尺校准。

### 空间类 Tool

- GIS 坐标转换；
- 图像与构件关联；
- 里程定位；
- 无人机姿态数据解析；
- 三维坐标映射。

### 数据类 Tool

- PostgreSQL 查询；
- 项目数据读取；
- 模型版本查询；
- 历史病害对比；
- 数据集统计。

### 知识类 Tool

- 规范检索；
- 案例检索；
- 处治方案检索；
- 病害知识检索。

### 成果类 Tool

- 图表生成；
- Word 报告生成；
- PDF 报告生成；
- 病害清单导出；
- GIS 图层导出。

---

## 4.5 推荐目录结构

```text
bridgeai-agent/
├── agent/
├── tools/
│   ├── base/
│   │   ├── tool.py
│   │   ├── context.py
│   │   ├── result.py
│   │   ├── errors.py
│   │   └── registry.py
│   ├── vision/
│   │   ├── yolo_detection/
│   │   ├── image_quality/
│   │   └── segmentation/
│   ├── measurement/
│   │   ├── crack_width/
│   │   └── damage_area/
│   ├── gis/
│   ├── rag/
│   ├── database/
│   ├── report/
│   └── statistics/
├── models/
├── repositories/
├── workflows/
└── tests/
```

---

## 4.6 Tool 基础协议

### Tool Context

```python
from pydantic import BaseModel
from typing import Any

class ToolContext(BaseModel):
    task_id: str
    project_id: str | None = None
    user_id: str | None = None
    trace_id: str
    working_directory: str
    metadata: dict[str, Any] = {}
```

### Tool Result

```python
from pydantic import BaseModel
from typing import Any, Literal

class ToolArtifact(BaseModel):
    artifact_id: str
    artifact_type: str
    path: str
    mime_type: str | None = None
    checksum: str | None = None

class ToolResult(BaseModel):
    status: Literal["success", "failed", "partial"]
    data: dict[str, Any] = {}
    artifacts: list[ToolArtifact] = []
    warnings: list[str] = []
    metrics: dict[str, float] = {}
    error_code: str | None = None
    error_message: str | None = None
```

### Base Tool

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel

class BaseTool(ABC):
    name: str
    version: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]

    @abstractmethod
    async def execute(
        self,
        context: ToolContext,
        payload: BaseModel,
    ) -> ToolResult:
        raise NotImplementedError
```

---

## 4.7 Tool Manifest

每个 Tool 必须提供 Manifest：

```yaml
name: yolo_damage_detection
version: 1.0.0
description: 使用指定YOLO模型对桥梁图像执行病害检测
category: vision
execution_mode: local
timeout_seconds: 1800
retry_policy:
  max_attempts: 2
  backoff_seconds: 5
resources:
  unified_memory_mb: 24576
  cpu_threads: 12
permissions:
  filesystem_read: true
  filesystem_write: true
  database_read: true
  database_write: true
production_ready: true
```

---

## 4.8 Tool Registry

Tool Registry 负责：

- 注册；
- 查询；
- 启用；
- 禁用；
- 版本选择；
- 能力发现；
- 生产状态管理；
- 权限策略；
- 健康状态。

建议 Registry 结构：

```python
class ToolRegistry:
    def register(self, tool: BaseTool) -> None: ...
    def unregister(self, name: str, version: str) -> None: ...
    def get(self, name: str, version: str | None = None) -> BaseTool: ...
    def list_enabled(self) -> list[BaseTool]: ...
    def health(self, name: str) -> dict: ...
```

---

## 4.9 Tool 调用流程

```text
Agent
  ↓
Tool Router
  ↓
Tool Registry
  ↓
Permission Check
  ↓
Input Validation
  ↓
Idempotency Check
  ↓
Resource Check
  ↓
Tool Execute
  ↓
Output Validation
  ↓
Persist Result
  ↓
Return to Agent
```

---

## 4.10 PostgreSQL 中的 Tool 元数据设计

### tools

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | Tool ID |
| name | varchar | Tool 名称 |
| version | varchar | 版本 |
| category | varchar | 分类 |
| description | text | 描述 |
| manifest | jsonb | Manifest |
| enabled | boolean | 是否启用 |
| production_ready | boolean | 是否可生产使用 |
| created_at | timestamptz | 创建时间 |

### tool_executions

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | 执行ID |
| task_id | uuid | Agent任务 |
| tool_id | uuid | Tool |
| trace_id | varchar | 链路ID |
| input_hash | varchar | 输入哈希 |
| input_json | jsonb | 输入 |
| output_json | jsonb | 输出摘要 |
| status | varchar | 状态 |
| started_at | timestamptz | 开始时间 |
| finished_at | timestamptz | 结束时间 |
| duration_ms | bigint | 耗时 |
| error_code | varchar | 错误码 |

### tool_artifacts

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | Artifact ID |
| execution_id | uuid | 执行ID |
| artifact_type | varchar | 类型 |
| path | text | 路径 |
| checksum | varchar | 校验值 |
| metadata | jsonb | 元数据 |

---

## 4.11 YOLO Damage Detection Tool 示例

### 输入模型

```python
from pydantic import BaseModel, Field

class DetectionInput(BaseModel):
    image_paths: list[str]
    model_version: str
    confidence_threshold: float = Field(default=0.35, ge=0, le=1)
    iou_threshold: float = Field(default=0.50, ge=0, le=1)
    save_annotated_images: bool = True
```

### 输出模型

```python
class DetectionItem(BaseModel):
    image_path: str
    class_name: str
    confidence: float
    bbox: list[float]
    mask_path: str | None = None

class DetectionOutput(BaseModel):
    detections: list[DetectionItem]
    image_count: int
    detection_count: int
    model_version: str
```

### 执行骨架

```python
class YoloDamageDetectionTool(BaseTool):
    name = "yolo_damage_detection"
    version = "1.0.0"
    description = "桥梁病害YOLO检测工具"
    input_model = DetectionInput
    output_model = DetectionOutput

    async def execute(
        self,
        context: ToolContext,
        payload: DetectionInput,
    ) -> ToolResult:
        try:
            # 1. 校验图像路径
            # 2. 从Model Registry加载模型
            # 3. 执行推理
            # 4. 保存结构化结果
            # 5. 生成标注图
            # 6. 写入PostgreSQL
            # 7. 返回ToolResult
            return ToolResult(
                status="success",
                data={
                    "model_version": payload.model_version,
                    "image_count": len(payload.image_paths),
                },
            )
        except Exception as exc:
            return ToolResult(
                status="failed",
                error_code="YOLO_EXECUTION_FAILED",
                error_message=str(exc),
            )
```

---

## 4.12 MLX Tool 适配

MLX 相关能力应通过独立 Model Gateway 暴露。

不推荐：

```python
Agent -> 直接 import mlx_lm
```

推荐：

```text
Agent
  ↓
Tool
  ↓
Model Gateway
  ↓
MLX Runtime
```

优势：

- 模型加载集中管理；
- 支持常驻与卸载；
- 避免多个 Tool 重复占用统一内存；
- 支持并发限制；
- 支持不同模型路由；
- 支持性能监控。

---

## 4.13 资源调度

M3 Ultra + 512GB 统一内存具有强大本地能力，但 Tool 仍必须声明资源需求。

建议字段：

- `unified_memory_mb`
- `cpu_threads`
- `gpu_required`
- `max_concurrency`
- `exclusive`
- `estimated_duration_seconds`

资源调度器应避免：

- 大模型和大规模视觉推理同时无限并发；
- 训练任务抢占生产 Agent；
- 同一模型重复加载多个副本；
- 报告生成任务阻塞推理任务；
- 单个项目耗尽全部内存。

---

## 4.14 错误码规范

示例：

| 错误码 | 说明 |
|---|---|
| TOOL_INPUT_INVALID | 输入不符合 Schema |
| TOOL_NOT_FOUND | Tool 未注册 |
| TOOL_DISABLED | Tool 已禁用 |
| TOOL_TIMEOUT | Tool 超时 |
| TOOL_PERMISSION_DENIED | 权限不足 |
| MODEL_NOT_FOUND | 模型不存在 |
| MODEL_LOAD_FAILED | 模型加载失败 |
| DATABASE_ERROR | 数据库错误 |
| FILE_NOT_FOUND | 文件不存在 |
| OUTPUT_SCHEMA_INVALID | 输出不符合 Schema |
| RESOURCE_LIMIT_EXCEEDED | 资源不足 |
| UNKNOWN_ERROR | 未知错误 |

---

## 4.15 重试策略

允许重试：

- 短暂数据库连接失败；
- 临时文件锁；
- 模型服务未就绪；
- 可恢复网络异常；
- 超时但后台进程已安全终止。

不允许自动重试：

- 参数错误；
- 权限错误；
- 文件不存在；
- 模型版本不存在；
- 业务规则不满足；
- 输出 Schema 错误重复发生。

---

## 4.16 缓存策略

可缓存内容：

- 相同图像哈希 + 相同模型版本的推理结果；
- 相同规范检索请求；
- 不变的项目元数据；
- 已生成的统计图表；
- 相同报告数据的中间渲染结果。

缓存键必须包含：

```text
tool_name + tool_version + input_hash + model_version + parameter_hash
```

---

## 4.17 Tool 安全

- 文件路径限制在项目工作目录；
- 禁止任意路径读取；
- 禁止任意 SQL；
- 数据库访问通过 Repository；
- 禁止 Tool 自行修改权限；
- 外部命令必须白名单；
- 所有 Artifact 计算校验值；
- Tool 输出进入 Agent 前必须验证；
- Tool 不得将敏感数据写入普通日志。

---

## 4.18 Tool 测试规范

### 单元测试

- 正常输入；
- 边界参数；
- 空输入；
- 错误输入；
- 大批量输入；
- 输出 Schema；
- 异常映射。

### 集成测试

- Tool + PostgreSQL；
- Tool + Model Gateway；
- Tool + 文件存储；
- Tool + Agent Executor。

### 回归测试

模型或 Tool 升级后必须运行固定样本集并比较：

- 精度；
- 召回率；
- 推理时长；
- 内存占用；
- 输出结构；
- Artifact 一致性。

---

## 4.19 第一阶段 Tool 清单

优先级 P0：

1. `validate_image_batch`
2. `preprocess_image_batch`
3. `yolo_damage_detection`
4. `calculate_damage_statistics`
5. `retrieve_engineering_standard`
6. `generate_repair_advice`
7. `create_review_items`
8. `generate_word_report`
9. `generate_pdf_report`
10. `archive_task_result`

优先级 P1：

1. `measure_crack_width`
2. `measure_damage_area`
3. `map_damage_to_component`
4. `gis_coordinate_transform`
5. `historical_damage_compare`
6. `dataset_quality_analysis`

---

## 4.20 Tool 与 MCP

第一阶段不要求所有 Tool 直接实现为 MCP Server。

建议先建立内部稳定 Tool SDK，待接口成熟后增加面向不同调用方的适配器：

```text
Internal Tool SDK
        │
        ├── Native Python / LangGraph Adapter
        ├── FastAPI / OpenAPI Adapter
        └── MCP Server Adapter
                 │
                 ├── Google ADK（Function Tool 或 MCP）
                 ├── Dify（HTTP / OpenAPI / MCP）
                 └── 其他 MCP Client
```

这样可以避免在业务尚未稳定时过早被某个协议或编排框架绑定。MCP 的职责是标准化 Tool 调用；独立 Agent 服务之间的协作应使用 A2A 或受控服务 API，并由 Workflow 层统一记录任务状态、权限和审计事件。

---

## 4.21 版本管理

Tool 使用语义化版本：

```text
MAJOR.MINOR.PATCH
```

- MAJOR：输入输出不兼容；
- MINOR：向后兼容地增加功能；
- PATCH：修复问题。

生产任务必须固定 Tool 版本，不得默认跟随“最新版”。

---

## 4.22 发布流程

```text
开发
  ↓
单元测试
  ↓
集成测试
  ↓
固定样本回归
  ↓
性能测试
  ↓
人工评审
  ↓
标记 production_ready
  ↓
注册到生产 Tool Registry
```

---

## 4.23 本章结论

Tool 是 BridgeAI-Agent 的专业能力载体。

第一阶段的重点不是追求 Tool 数量，而是建立：

- 统一 BaseTool；
- Pydantic Schema；
- Tool Registry；
- PostgreSQL 执行记录；
- 幂等机制；
- 版本控制；
- 资源调度；
- 审计日志；
- 自动化测试。

BridgeAI-Agent 最重要的长期壁垒，将不是某一个 Agent Prompt，而是不断积累的高质量行业 Tool、数据资产、模型版本、工程知识和完整执行记录。
