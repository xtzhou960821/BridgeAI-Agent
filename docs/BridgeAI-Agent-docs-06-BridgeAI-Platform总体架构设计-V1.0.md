# BridgeAI Platform Architecture White Paper

# 第六章 BridgeAI Platform 总体架构设计
## 面向交通基础设施全生命周期的 AI Agent 平台

| 项目 | 内容 |
|---|---|
| 文档名称 | BridgeAI Platform Architecture White Paper |
| 章节 | 第六章 BridgeAI Platform 总体架构设计 |
| 版本 | V1.0 |
| 文档状态 | 正式可交付版 |
| 平台定位 | 面向交通基础设施全生命周期的 AI Agent 平台 |
| 默认开发环境 | Mac Studio / Apple M3 Ultra / 512GB 统一内存 |
| 数据库 | PostgreSQL（本地部署） |
| Agent 编排 | LangGraph 优先 |
| 本地模型运行 | Apple MLX 优先 |
| 视觉模型 | YOLO26 及后续可替换模型 |
| 编制日期 | 2026-07-17 |

---

## 6.1 本章目的

本章用于正式定义 BridgeAI Platform 的产品定位、业务边界、总体架构、核心平台能力、行业 Agent 体系、全生命周期应用模型和后续演进路线。

BridgeAI Platform 不再被定义为单一的桥梁病害检测系统，也不被定义为只服务于运营养护阶段的 AI 工具。

其正式定位为：

> **BridgeAI Platform 是面向交通基础设施全生命周期的 AI Agent 平台。**

平台服务对象包括但不限于：

- 公路；
- 桥梁；
- 隧道；
- 边坡；
- 交通场站；
- 智慧工地；
- 施工现场；
- 运营养护单位；
- 检测单位；
- 监理单位；
- 建设管理单位；
- 设计与咨询单位。

平台覆盖的生命周期包括：

```text
规划
  ↓
勘察
  ↓
设计
  ↓
施工
  ↓
交工验收
  ↓
运营
  ↓
巡检
  ↓
养护
  ↓
应急
  ↓
改扩建
  ↓
退役与数字资产归档
```

本章将回答以下核心问题：

1. BridgeAI 为什么需要从单一 Agent 升级为平台；
2. 平台如何支持交通基础设施全生命周期；
3. 智慧工地 AI Agent 在平台中的位置是什么；
4. 桥梁巡检、无人机、BIM、GIS、IoT 和数字孪生如何统一；
5. 平台如何复用 Workflow、Tool、Knowledge、Memory 和 PostgreSQL；
6. 后续新增道路、隧道或施工 Agent 时，为什么不需要推翻现有架构；
7. 哪些能力属于平台层，哪些属于业务 Agent，哪些属于具体应用。

---

## 6.2 产品愿景

### 6.2.1 愿景

BridgeAI Platform 的愿景是：

> 让 AI Agent 成为交通基础设施建设、施工、运营和养护流程中的长期数字协作者。

这个数字协作者不是简单的聊天机器人，而是能够：

- 读取项目资料；
- 理解工程任务；
- 调用专业工具；
- 分析现场数据；
- 识别风险；
- 组织复核；
- 生成工程成果；
- 保存过程记录；
- 支持管理决策；
- 形成持续积累的数据资产。

### 6.2.2 使命

BridgeAI Platform 的使命包括：

1. 降低工程信息处理成本；
2. 提高现场巡检和管理效率；
3. 将工程经验转化为可复用知识；
4. 将单点 AI 能力升级为流程级智能；
5. 形成交通基础设施全生命周期数据闭环；
6. 为工程决策提供可追溯证据；
7. 促进工程行业从项目制软件走向平台化智能系统。

### 6.2.3 核心价值

BridgeAI Platform 的价值不在于“生成更多文字”，而在于：

```text
现场数据
  ↓
专业识别
  ↓
业务判断
  ↓
人工复核
  ↓
工程成果
  ↓
数据沉淀
  ↓
模型和知识迭代
```

---

## 6.3 行业背景与平台建设必要性

根据现有行业调研，国内工程建设领域的 AI 应用正在从概念验证逐步进入业务流程嵌入阶段。

当前较成熟的应用包括：

- 规范智能查询；
- 施工方案自动生成；
- AI 组价；
- AI 图模管理；
- 智慧工地视频分析；
- 安全违规识别；
- 无人机巡检；
- 工程资料自动生成；
- 进度对比；
- 报告自动生成。

行业现状显示，大多数应用仍以“单点 AI”或“单点 Agent”为主。

典型单点能力包括：

```text
只做规范问答
只做施工方案生成
只做病害检测
只做安全帽识别
只做进度对比
只做报告生成
```

这些能力具备实际价值，但存在三个明显问题：

1. 业务流程割裂；
2. 数据不能统一沉淀；
3. 多个 AI 工具之间缺乏任务级协同。

BridgeAI Platform 的建设目标，是把这些单点能力组合成可执行、可恢复、可复核、可追溯的工程任务。

例如，智慧工地场景不应只输出“发现未戴安全帽”，而应进一步完成：

```text
发现违规
  ↓
关联人员与区域
  ↓
判断风险等级
  ↓
保存视频证据
  ↓
通知责任人
  ↓
生成整改任务
  ↓
跟踪整改结果
  ↓
形成安全日报
  ↓
进入项目安全档案
```

桥梁巡检场景也不应只输出“发现裂缝”，而应完成：

```text
发现病害
  ↓
关联构件
  ↓
确定位置
  ↓
统计数量
  ↓
检索规范
  ↓
生成复核清单
  ↓
提出处置建议
  ↓
生成报告
  ↓
归档历史记录
  ↓
用于下一次病害演化对比
```

因此，平台化不是扩大概念，而是解决工程流程中的实际断点。

---

## 6.4 产品定位

### 6.4.1 正式定位

BridgeAI Platform 定位为：

> 面向交通基础设施全生命周期，融合 Agent、Workflow、计算机视觉、无人机、BIM、GIS、IoT、RAG 和数字孪生的行业智能平台。

### 6.4.2 BridgeAI 名称的边界

“BridgeAI”作为现阶段产品名称保留，但平台架构不局限于桥梁。

桥梁巡检是当前最成熟的业务入口，也是最早完成真实现场验证的场景。

平台从第一天开始按照以下范围设计：

```text
BridgeAI Platform
├── Bridge Inspection
├── Road Inspection
├── Tunnel Inspection
├── Smart Construction
├── Safety Supervision
├── Quality Management
├── BIM Review
├── Digital Twin
├── Maintenance Planning
└── Emergency Response
```

### 6.4.3 平台不是什么

BridgeAI Platform 不是：

- 单一 YOLO 项目；
- 纯聊天机器人；
- 固定脚本集合；
- 只有 PDF 报告生成的系统；
- 只面向养护阶段的软件；
- 无人工审核的自动决策系统；
- 直接替代工程责任主体的系统；
- 只依赖某一个大模型厂商的平台。

---

## 6.5 全生命周期业务模型

### 6.5.1 规划阶段

Agent 能力：

- 规划资料汇总；
- 路线比选辅助；
- 历史项目检索；
- 环境约束查询；
- 投资估算资料整理；
- 方案风险提示。

### 6.5.2 勘察阶段

Agent 能力：

- 勘察资料整理；
- 地质信息抽取；
- 异常点归类；
- 勘察日志生成；
- 数据缺失检查；
- 勘察报告辅助编制。

### 6.5.3 设计阶段

Agent 能力：

- BIM 模型检查；
- 图纸审查；
- 规范冲突检查；
- 设计变更影响分析；
- 工程量辅助检查；
- 设计问题清单生成。

### 6.5.4 施工阶段

智慧工地 Agent 能力：

- 人员安全识别；
- 临边防护检查；
- 机械设备状态分析；
- 施工进度对比；
- 质量问题识别；
- 旁站记录生成；
- 巡视记录生成；
- 施工日志生成；
- 监理通知单草稿；
- 环境监测；
- 整改闭环跟踪。

### 6.5.5 交工验收阶段

Agent 能力：

- 资料完整性检查；
- 影像证据归档；
- 验收清单生成；
- 问题整改追踪；
- BIM 与实际完成情况对比；
- 竣工资料辅助编制。

### 6.5.6 运营养护阶段

Agent 能力：

- 无人机巡检；
- 病害识别；
- 历史病害对比；
- 构件健康档案；
- 规范检索；
- 处治建议；
- 维修计划；
- 养护优先级排序；
- 报告生成。

### 6.5.7 应急阶段

Agent 能力：

- 灾后影像分析；
- 风险区域识别；
- 应急巡检任务编排；
- 多源数据汇总；
- 初步损伤清单；
- 应急处置建议；
- 事件过程记录。

### 6.5.8 改扩建阶段

Agent 能力：

- 历史资料检索；
- 既有结构状态汇总；
- 施工影响分析；
- 改扩建风险清单；
- 新旧数据关联；
- 数字资产迁移。

---

## 6.6 平台总体架构

```text
┌────────────────────────────────────────────────────┐
│                  Application Layer                 │
│ Web / Mobile / Desktop / Command Center / API      │
├────────────────────────────────────────────────────┤
│                 Domain Agent Layer                 │
│ Bridge / Road / Tunnel / Smart Construction        │
│ Safety / Quality / BIM / Maintenance / Emergency   │
├────────────────────────────────────────────────────┤
│                Agent Runtime Layer                 │
│ Planning / Routing / State / Memory / Policy       │
│ Human Review / Audit / Result Composition          │
├────────────────────────────────────────────────────┤
│              Workflow Orchestration Layer          │
│ LangGraph / StateGraph / Checkpoint / Interrupt    │
│ Retry / Recovery / Versioning / Scheduling         │
├────────────────────────────────────────────────────┤
│                 Capability Layer                   │
│ Vision / UAV / GIS / BIM / IoT / RAG / Report      │
│ OCR / Measurement / Statistics / Notification      │
├────────────────────────────────────────────────────┤
│                   Data Layer                       │
│ PostgreSQL / Vector Store / Object Storage         │
│ Time Series / File Assets / Model Registry         │
├────────────────────────────────────────────────────┤
│                  Model Layer                       │
│ MLX LLM / YOLO26 / Embedding / OCR / Segmentation  │
│ Optional Cloud Models / Model Gateway              │
├────────────────────────────────────────────────────┤
│              Infrastructure Layer                  │
│ Mac Studio / Edge Compute / UAV / Server / Network │
└────────────────────────────────────────────────────┘
```

---

## 6.7 平台分层原则

### 6.7.1 Platform First

平台能力优先沉淀。

如果某个能力会被多个 Agent 使用，应进入平台能力层，而不是复制到不同 Agent 中。

例如：

- 报告生成；
- 规范检索；
- 用户权限；
- 任务状态；
- Artifact 管理；
- 审计日志；
- 模型调用；
- Tool 注册；
- 文件处理。

### 6.7.2 Domain Separation

行业 Agent 只负责领域逻辑。

例如 Smart Construction Agent 可以理解施工现场风险，但不应自己实现数据库连接池或 PDF 渲染。

### 6.7.3 Workflow Driven

所有正式业务任务必须进入 Workflow。

不能通过一次自由对话直接生成正式工程成果。

### 6.7.4 Local First

平台优先支持本地部署：

- PostgreSQL 本地运行；
- MLX 本地运行；
- YOLO 本地运行；
- 工程资料本地保存；
- 云模型作为可选能力；
- 敏感数据默认不出本地。

### 6.7.5 Human-in-the-loop

重大工程结论、正式报告、整改通知和安全处置必须保留人工审核。

### 6.7.6 Evidence First

任何工程结论都必须关联证据：

- 图片；
- 视频；
- 传感器数据；
- Tool 输出；
- 规范来源；
- 人工复核记录；
- 模型版本；
- 时间戳。

### 6.7.7 Model Agnostic

平台不得绑定单一大模型。

通过 Model Gateway 支持：

- MLX 本地模型；
- Qwen；
- DeepSeek；
- OpenAI；
- 其他兼容模型。

### 6.7.8 Physical AI Safety

涉及无人机、机械设备或现场执行时，大语言模型只负责任务级决策，不直接执行实时飞控或设备闭环控制。

---

## 6.8 Agent Runtime

Agent Runtime 是平台所有业务 Agent 的共同运行时。

主要模块：

```text
Agent Runtime
├── Intent Parser
├── Context Builder
├── Planner
├── Policy Engine
├── Tool Router
├── Executor
├── State Manager
├── Memory Manager
├── Review Manager
├── Result Composer
└── Audit Logger
```

### 6.8.1 Intent Parser

识别任务类型、对象、范围和输出。

### 6.8.2 Planner

基于模板计划生成任务步骤。

### 6.8.3 Policy Engine

执行权限、工程规则和安全策略。

### 6.8.4 Tool Router

选择正确 Tool 和版本。

### 6.8.5 State Manager

管理 LangGraph State 和 PostgreSQL 持久化。

### 6.8.6 Review Manager

创建和恢复人工复核节点。

### 6.8.7 Audit Logger

记录完整决策链。

---

## 6.9 Workflow Engine

Workflow Engine 统一负责：

- 状态流转；
- 条件路由；
- 人工中断；
- 失败重试；
- 任务恢复；
- 长任务执行；
- 版本控制；
- 事件日志。

第一阶段采用 LangGraph。

推荐业务 Workflow：

```text
BridgeInspectionWorkflow
SmartConstructionSafetyWorkflow
QualityInspectionWorkflow
ConstructionDailyReportWorkflow
UAVMissionWorkflow
MaintenancePlanningWorkflow
EmergencyInspectionWorkflow
```

---

## 6.10 Knowledge Center

Knowledge Center 是平台统一知识底座。

知识类型：

- 国家规范；
- 行业标准；
- 地方标准；
- 企业标准；
- 施工组织设计；
- 检测报告；
- 监理资料；
- 养护案例；
- 设计图纸说明；
- 历史项目经验；
- 设备说明书。

Knowledge Center 不只是向量库，还包括：

- 文档解析；
- 元数据；
- 版本管理；
- 生效状态；
- 权限；
- 引用；
- 章节定位；
- 知识审核。

RAG 输出必须包含：

```json
{
  "document_id": "STD-001",
  "document_title": "某工程规范",
  "version": "2025",
  "chapter": "5.2",
  "source_text": "原文片段",
  "effective_status": "active",
  "retrieval_score": 0.89
}
```

---

## 6.11 Tool Center

Tool Center 管理所有可复用专业能力。

### 视觉 Tool

- 病害检测；
- 安全帽识别；
- 临边防护识别；
- 车辆识别；
- 构件识别；
- 裂缝分割；
- 图像质量检查。

### 无人机 Tool

- 任务创建；
- 航线读取；
- 影像接收；
- 飞行状态读取；
- 定位状态读取；
- 任务暂停；
- 人工接管请求。

### BIM/GIS Tool

- 构件查询；
- 坐标转换；
- 模型关联；
- 病害挂接；
- 空间统计；
- 图层导出。

### 工程资料 Tool

- 规范检索；
- 施工日志生成；
- 旁站记录生成；
- 报告生成；
- 整改通知草稿；
- 验收资料整理。

### 数据 Tool

- PostgreSQL 查询；
- 历史项目对比；
- 模型版本查询；
- 数据集统计；
- 任务进度查询。

---

## 6.12 PostgreSQL 数据中心

PostgreSQL 作为平台核心事务数据库。

建议 Schema：

```text
bridgeai_core
bridgeai_project
bridgeai_workflow
bridgeai_agent
bridgeai_tool
bridgeai_model
bridgeai_knowledge
bridgeai_construction
bridgeai_asset
bridgeai_uav
bridgeai_report
bridgeai_audit
```

### 核心实体

- 用户；
- 组织；
- 项目；
- 标段；
- 资产；
- 桥梁；
- 隧道；
- 工点；
- 构件；
- 任务；
- Workflow；
- Agent；
- Tool；
- 模型；
- 病害；
- 风险事件；
- 整改任务；
- 报告；
- Artifact；
- 审核记录。

### 数据原则

1. 业务主键使用 UUID；
2. 时间字段使用 `TIMESTAMPTZ`；
3. 结构化扩展字段使用 JSONB；
4. 高频检索字段必须独立建列；
5. 大文件不直接存数据库；
6. 所有正式成果必须版本化；
7. 所有关键变更必须审计；
8. 项目和组织必须权限隔离。

---

## 6.13 Model Gateway

Model Gateway 统一管理模型调用。

```text
Agent / Tool
    ↓
Model Gateway
    ├── MLX Local LLM
    ├── YOLO26
    ├── Embedding Model
    ├── OCR Model
    ├── Segmentation Model
    └── Optional Cloud LLM
```

职责：

- 模型注册；
- 版本选择；
- 资源分配；
- 模型预热；
- 请求排队；
- 日志；
- 限流；
- 降级；
- 成本统计；
- 性能监控。

针对 Mac Studio：

- 避免多个进程重复加载大模型；
- 统一管理内存；
- 训练与在线任务隔离；
- 对 YOLO 和 LLM 设置独立并发上限；
- 对大批量图片分批处理；
- 使用模型常驻和延迟卸载策略。

---

## 6.14 Domain Agent 体系

### 6.14.1 Bridge Inspection Agent

负责桥梁巡检与养护。

能力：

- 无人机影像处理；
- 病害检测；
- 构件定位；
- 历史对比；
- 规范检索；
- 处治建议；
- 检测报告生成。

### 6.14.2 Smart Construction Agent

负责施工阶段现场管理。

能力：

- 安全巡检；
- 质量巡检；
- 进度识别；
- 旁站记录；
- 巡视记录；
- 施工日志；
- 整改闭环；
- 设备状态汇总；
- 环境监测；
- 智慧工地日报。

### 6.14.3 Safety Supervision Agent

负责安全风险识别和闭环管理。

能力：

- 人员违规识别；
- 未佩戴安全帽；
- 临边防护缺失；
- 违规动火；
- 危险区域闯入；
- 高风险事件升级；
- 整改追踪。

### 6.14.4 Quality Inspection Agent

负责施工质量检查。

能力：

- 质量问题识别；
- 检测数据汇总；
- 验收清单；
- 问题复核；
- 质量报告；
- 整改复验。

### 6.14.5 BIM Review Agent

负责设计和模型检查。

能力：

- 图模一致性；
- 构件属性检查；
- 规范冲突；
- 模型完整性；
- 设计变更影响；
- 工程量辅助核对。

### 6.14.6 Road Asset Agent

负责道路资产管理。

能力：

- 路面病害；
- 附属设施；
- 里程定位；
- 历史演化；
- 维修计划；
- 道路资产台账。

### 6.14.7 Tunnel Inspection Agent

负责隧道巡检。

能力：

- 衬砌裂缝；
- 渗漏水；
- 脱落；
- 设备状态；
- 空间定位；
- 隧道巡检报告。

### 6.14.8 Maintenance Planning Agent

负责养护决策辅助。

能力：

- 病害优先级；
- 预算约束；
- 维修方案；
- 年度计划；
- 历史成本；
- 资源调度建议。

### 6.14.9 Emergency Response Agent

负责应急事件辅助。

能力：

- 应急数据汇总；
- 无人机快速巡检；
- 风险分区；
- 初步损伤清单；
- 处置流程；
- 事件报告。

### 6.14.10 Digital Twin Agent

负责数字资产和数字孪生。

能力：

- BIM/GIS/IoT 数据关联；
- 历史状态查询；
- 实时状态展示；
- 病害挂接；
- 资产健康档案；
- 生命周期数据查询。

---

## 6.15 Smart Construction Agent 详细定位

智慧工地 Agent 必须作为一级业务 Agent，而不是桥梁巡检的附属模块。

### 6.15.1 输入数据

- 视频监控；
- 无人机影像；
- IoT 传感器；
- 人员定位；
- 机械设备；
- BIM；
- 施工计划；
- 监理记录；
- 语音输入；
- 环境监测。

### 6.15.2 输出成果

- 安全事件；
- 质量问题；
- 施工进度；
- 整改任务；
- 巡视记录；
- 旁站记录；
- 日报；
- 周报；
- 风险趋势；
- 项目管理驾驶舱数据。

### 6.15.3 典型 Workflow

```text
视频事件产生
  ↓
AI识别
  ↓
Agent判断风险
  ↓
关联工点和责任单位
  ↓
保存证据
  ↓
创建整改任务
  ↓
责任人处理
  ↓
复核
  ↓
关闭事件
  ↓
写入安全档案
```

### 6.15.4 Human-in-the-loop

以下内容必须人工审核：

- 高风险安全事件；
- 监理通知；
- 质量结论；
- 验收结论；
- 正式整改关闭；
- 对责任单位的正式通知。

---

## 6.16 BridgeAI-UAV 在平台中的位置

BridgeAI-UAV 是平台能力模块和业务产品，不是整个平台本身。

```text
BridgeAI Platform
  ↓
UAV Capability
  ↓
Bridge Inspection Agent
  ↓
UAV Mission Workflow
```

BridgeAI-UAV 可以被多个 Agent 使用：

- Bridge Inspection Agent；
- Smart Construction Agent；
- Emergency Response Agent；
- Road Asset Agent；
- Tunnel Portal Inspection；
- Digital Twin Agent。

### 已验证能力

- YOLO26 已完成训练；
- 已部署至妙算3；
- 已实现边飞边识别；
- 遥控器实时显示识别框；
- 本地 Mac Studio 支持训练与开发；
- PostgreSQL 已在本地部署。

### 正在研发

- GPS 拒止环境下飞控接管；
- 双目视觉定位条件下短航线执行；
- 航线状态与控制权状态统一记录；
- 后续激光 SLAM 增强。

### 安全边界

Agent 不直接控制：

- 电机；
- PID；
- 姿态闭环；
- 飞控实时控制量。

Agent 只负责：

- 任务创建；
- 任务状态；
- 航线级决策；
- 异常升级；
- 人工接管请求；
- 任务结果归档。

---

## 6.17 数字闭环

BridgeAI Platform 的核心不是一次任务，而是持续闭环。

```text
现场采集
  ↓
AI识别
  ↓
人工复核
  ↓
正式成果
  ↓
项目数据库
  ↓
历史对比
  ↓
难例提取
  ↓
重新标注
  ↓
模型训练
  ↓
模型评测
  ↓
部署升级
  ↓
再次巡检
```

这个闭环形成五类资产：

1. 数据资产；
2. 模型资产；
3. 知识资产；
4. Workflow 资产；
5. 工程案例资产。

---

## 6.18 平台应用架构

```text
┌─────────────────────────────────────────────┐
│              BridgeAI Web Portal            │
├─────────────────────────────────────────────┤
│ Project Center                              │
│ Task Center                                 │
│ Smart Construction                         │
│ Inspection Center                          │
│ Knowledge Center                           │
│ Report Center                              │
│ Model Center                               │
│ Digital Twin                               │
│ System Administration                      │
└─────────────────────────────────────────────┘
```

### Project Center

管理：

- 项目；
- 标段；
- 桥梁；
- 隧道；
- 工点；
- 参建单位；
- 用户权限。

### Task Center

管理：

- Agent 任务；
- Workflow；
- 进度；
- 错误；
- 人工复核；
- Artifact。

### Smart Construction

管理：

- 视频；
- 安全事件；
- 质量事件；
- 进度；
- 整改；
- 日志；
- 旁站记录。

### Inspection Center

管理：

- 无人机任务；
- 病害；
- 构件；
- 历史对比；
- 检测报告。

### Model Center

管理：

- 数据集；
- 模型；
- 评测；
- 部署；
- 版本；
- 难例。

---

## 6.19 推荐代码目录

```text
bridgeai-platform/
├── docs/
├── apps/
│   ├── api/
│   ├── web/
│   └── worker/
├── platform/
│   ├── agent_runtime/
│   ├── workflow_engine/
│   ├── tool_center/
│   ├── knowledge_center/
│   ├── model_gateway/
│   ├── memory/
│   ├── security/
│   └── audit/
├── domains/
│   ├── bridge/
│   ├── road/
│   ├── tunnel/
│   ├── smart_construction/
│   ├── safety/
│   ├── quality/
│   ├── maintenance/
│   ├── emergency/
│   └── digital_twin/
├── capabilities/
│   ├── vision/
│   ├── uav/
│   ├── bim/
│   ├── gis/
│   ├── iot/
│   ├── reporting/
│   ├── rag/
│   └── notification/
├── data/
│   ├── repositories/
│   ├── migrations/
│   └── schemas/
├── models/
├── deployment/
├── tests/
└── scripts/
```

---

## 6.20 部署架构

### 第一阶段：单机开发部署

```text
Mac Studio
├── FastAPI
├── LangGraph
├── PostgreSQL
├── MLX
├── YOLO26
├── Vector Database
├── Object Storage
└── Vue Web
```

适合：

- 单人研发；
- PoC；
- 本地模型测试；
- 数据保密；
- 小规模项目。

### 第二阶段：本地服务器部署

```text
Application Server
Model Server
PostgreSQL Server
Object Storage
Edge Devices
```

适合：

- 团队协作；
- 多项目；
- 多用户；
- 私有化交付。

### 第三阶段：边云协同

```text
Edge
├── UAV
├── 妙算3
├── Camera
└── IoT Gateway

Local Center
├── PostgreSQL
├── Workflow
├── Knowledge
└── Model Service

Optional Cloud
├── Backup
├── Remote Collaboration
└── Large Model Service
```

---

## 6.21 权限与安全

### 权限层级

- 组织；
- 项目；
- 标段；
- 资产；
- Agent；
- Tool；
- 报告；
- 数据；
- 模型。

### 安全要求

1. 数据默认本地保存；
2. 云端调用必须脱敏；
3. 项目之间隔离；
4. Tool 白名单；
5. Agent 不得执行任意 Shell；
6. 正式成果必须审核；
7. 关键操作记录审计；
8. 无人机和设备操作保留人工优先权；
9. 模型输出不得直接替代工程责任；
10. 规范引用必须可追溯。

---

## 6.22 平台演进路线

### Phase 1：桥梁巡检闭环

目标：

- Agent；
- Workflow；
- YOLO；
- RAG；
- 报告；
- PostgreSQL；
- 人工审核。

### Phase 2：智慧工地 Agent

目标：

- 视频安全识别；
- 整改闭环；
- 施工日志；
- 巡视记录；
- 旁站记录；
- 日报周报。

### Phase 3：多资产扩展

目标：

- 道路；
- 隧道；
- 边坡；
- 多种巡检设备；
- 多项目管理。

### Phase 4：数字孪生

目标：

- BIM；
- GIS；
- IoT；
- 历史检测；
- 实时状态；
- 全生命周期档案。

### Phase 5：多 Agent 协同

目标：

- 项目 Agent；
- 安全 Agent；
- 质量 Agent；
- 进度 Agent；
- 报告 Agent；
- 知识 Agent；
- 调度 Agent。

---

## 6.23 V1.0 实施范围

第六章定义的是平台总体架构，但 V1.0 研发不应一次实现全部能力。

建议 V1.0 只实现：

1. 平台基础用户与项目；
2. PostgreSQL 数据中心；
3. Agent Runtime；
4. LangGraph Workflow；
5. Tool Center；
6. Bridge Inspection Agent；
7. Smart Construction Agent 的最小骨架；
8. YOLO26 Tool；
9. RAG Tool；
10. Word/PDF Report Tool；
11. 人工审核；
12. 完整审计日志。

暂不实现：

- 全自动多 Agent；
- 大规模数字孪生；
- 全部 BIM 功能；
- 全部施工管理模块；
- 完全自主无人机飞控；
- 无人工审核的正式结论；
- 覆盖所有交通基础设施类型。

---

## 6.24 架构决策记录

### ADR-006-001：从单一桥梁 Agent 升级为全生命周期平台

**决定：**

BridgeAI 从桥梁巡检产品升级为交通基础设施全生命周期 AI Agent 平台。

**原因：**

- 现有能力已覆盖无人机、病害检测、智慧工地、视频和报告；
- 施工与养护数据天然连续；
- 共用 Workflow、Knowledge、Tool 和 PostgreSQL；
- 平台化可以降低后续 Agent 开发成本；
- 符合长期产品战略。

**影响：**

- 平台层和业务域必须解耦；
- 智慧工地成为一级业务域；
- 桥梁巡检不再代表整个平台；
- 后续章节必须覆盖施工阶段。

### ADR-006-002：智慧工地 Agent 作为一级 Agent

**决定：**

Smart Construction Agent 与 Bridge Inspection Agent 平级。

**原因：**

- 施工阶段是全生命周期的重要环节；
- 用户已有智慧工地和视频监控基础；
- 安全、质量、进度和资料具备明确应用价值；
- 能与无人机和边缘 AI 形成协同。

### ADR-006-003：统一 PostgreSQL 数据中心

**决定：**

第一阶段以本地 PostgreSQL 作为统一事务数据中心。

**原因：**

- 已部署；
- 事务能力可靠；
- JSONB 适合 Agent 状态；
- 支持 GIS 扩展；
- 运维简单；
- 满足本地数据安全要求。

### ADR-006-004：本地优先，边云协同

**决定：**

模型和工程数据优先本地运行，云端作为可选增强。

**原因：**

- 工程数据敏感；
- Mac Studio 本地算力充足；
- MLX 适合 Apple Silicon；
- 边缘环境网络不稳定；
- 降低长期调用成本。

---

## 6.25 风险与约束

### 平台范围过大

应对：

- 以桥梁巡检为首个完整闭环；
- 智慧工地从最小场景切入；
- 平台架构先统一，业务逐步实现。

### Agent 幻觉

应对：

- RAG；
- 结构化输出；
- 工程规则；
- 人工审核；
- Tool 优先；
- 引用原文。

### 数据割裂

应对：

- 统一项目和资产 ID；
- 统一 PostgreSQL；
- Artifact 统一管理；
- 标准接口。

### 无人机安全

应对：

- Agent 不直接控制飞控闭环；
- 人工接管优先；
- 任务级控制；
- 安全状态机；
- 受控现场测试。

### 个人开发压力

应对：

- 不同时启动全部 Agent；
- 优先平台骨架；
- 逐个业务闭环；
- 文档、架构和代码同步；
- 用真实项目驱动迭代。

---

## 6.26 本章结论

BridgeAI Platform 的正式定位是：

> **面向交通基础设施全生命周期的 AI Agent 平台。**

平台的核心结构为：

```text
平台能力
  +
行业 Agent
  +
专业 Tool
  +
Workflow
  +
PostgreSQL
  +
工程知识
  +
人工审核
```

Bridge Inspection Agent 是第一批成熟落地 Agent。

Smart Construction Agent 是施工阶段的一级 Agent，与桥梁巡检 Agent 平级。

BridgeAI-UAV 是平台的无人机能力模块，可以同时服务于桥梁巡检、智慧工地、道路资产和应急巡检。

平台 V1.0 不追求一次实现全部业务，而应优先构建：

- 一个稳定的平台底座；
- 一个完整桥梁巡检闭环；
- 一个智慧工地最小闭环；
- 一套可扩展的 Agent、Workflow 和 Tool 标准；
- 一个统一的 PostgreSQL 数据中心；
- 一个可持续演进的数据和模型闭环。

本章作为 BridgeAI Platform 后续所有业务章节的总体架构依据。

---

## 后续章节建议

- 第七章：BridgeAI-UAV 自主巡检系统设计；
- 第八章：Smart Construction Agent 智慧工地系统设计；
- 第九章：Knowledge Center 与工程 RAG；
- 第十章：Memory 与项目上下文；
- 第十一章：Multi-Agent 协同；
- 第十二章：BIM、GIS、IoT 与数字孪生；
- 第十三章：部署、安全与运维；
- 第十四章：工程实践与真实案例；
- 第十五章：工程建设领域 AI 与 AI Agent 应用现状及产品战略。

---

## 修订记录

| 版本 | 日期 | 修订说明 |
|---|---|---|
| V1.0 | 2026-07-17 | 正式定义 BridgeAI Platform 为交通基础设施全生命周期 AI Agent 平台，并将智慧工地 Agent 纳入一级业务域 |
