---
title: BridgeAI-Agent 第十二章 模型管理与评测体系
version: V1.0
status: 正式版
updated: 2026-07-30
---

# 第十二章 模型管理与评测体系

| 项目 | 内容 |
|---|---|
| 文档编号 | BridgeAI-Agent-docs-12 |
| 章节 | 第十二章 模型管理与评测体系 |
| 版本 | V1.0 |
| 日期 | 2026-07-30 |
| 适用范围 | 桥梁与道路巡检 AI Agent 第一阶段 |
| 模型治理基线 | Model Registry + Dataset Registry + Experiment Tracking + Evaluation Gates |
| 前置章节 | 第三章 Agent、第四章 Tool SDK、第八章数据与数据库、第十章 Prompt 与结构化输出、第十一章后端与前端架构 |

## 12.1 本章目标

本章定义 BridgeAI-Agent 的模型管理与评测体系，使视觉模型、量测模型、Embedding 模型、大语言模型、RAG/Memory 组件、Prompt/Schema 和 Agent Workflow 都能以统一方式登记、评测、发布、回滚和持续改进。

桥梁与道路巡检场景中，模型质量不能只用一个通用指标描述。一个病害检测模型即使 mAP 较高，也可能在关键构件、低照度、雨后路面、斜拍桥底、裂缝细宽度等场景出现漏检；一个大语言模型即使回答流畅，也可能在报告草稿中生成没有证据支撑的处治建议。因此，第十二章的核心不是“选择哪个模型最好”，而是建立可复现、可审计、可持续迭代的模型治理闭环。

本章交付以下内容：

- 模型资产分类、Model Registry、版本、别名、状态和血缘；
- 数据集资产、样本分层、标注规范、固定评测集和难例集；
- 实验追踪、训练记录、推理环境、模型 Artifact 和指标归档；
- 视觉模型、量测模型、Embedding、LLM、RAG、Memory、Prompt/Schema 和 Agent Workflow 的评测指标；
- 发布门禁、Champion/Challenger、灰度、影子评测、回滚和生产漂移监控；
- 人工复核反馈、难例挖掘、数据闭环和持续改进流程；
- 模型调用审计、成本、性能、资源调度和合规边界；
- 第一阶段实施里程碑和 ADR。

## 12.2 范围与模型分类

BridgeAI-Agent 第一阶段涉及的模型和模型化组件包括：

| 类型 | 示例 | 主要用途 | 是否直接产生工程事实 |
|---|---|---|---|
| 视觉检测模型 | YOLO 病害检测、构件识别 | 候选病害框、类别、置信度 | 否，需 Tool/复核晋升 |
| 视觉分割模型 | 裂缝分割、剥落区域分割 | 病害轮廓、面积候选 | 否，需量测和复核 |
| 量测模型/算法 | 裂缝宽度、面积、尺度换算 | 尺寸候选和质量标识 | 条件性，需校准证据 |
| OCR/文档模型 | 报告 OCR、表格解析 | 文档结构和文本抽取 | 否，需来源校验 |
| Embedding 模型 | RAG/Memory 向量化 | 语义召回 | 否，召回结果需回查权威记录 |
| Reranker 模型 | 检索重排 | 提高证据排序 | 否 |
| 大语言模型 | 任务理解、工具选择、报告草稿 | 解释、草稿、结构化输出 | 否，需 Schema/证据/复核 |
| Prompt/Schema | 节点 Prompt、输出 Schema | 约束模型行为 | 不直接产生事实 |
| Workflow Policy | 路由阈值、复核规则 | 控制状态分支 | 是流程规则，需版本化 |

本章把 Prompt、Schema、阈值、路由规则和后处理算法纳入“模型治理相关资产”，因为它们会直接影响最终输出质量和历史复现。

## 12.3 设计原则

1. **模型是受治理 Artifact。** 权重、配置、Tokenizer、类别表、阈值、后处理代码和运行环境共同构成可发布模型。
2. **数据集先于指标。** 没有固定数据集版本、标注规范和样本分层，任何指标都不可比较。
3. **业务指标优先。** mAP、Precision、Recall 是必要指标，但不能替代漏检风险、复核通过率、报告引用覆盖率和任务成功率。
4. **生产任务固定版本。** 已运行任务必须记录模型、Tool、Prompt、Schema、数据集和报告模板版本，不默认跟随最新版。
5. **人工复核形成反馈。** 复核确认、驳回、修改和补证都是重要训练与评测信号。
6. **发布可回滚。** 模型、Prompt、Embedding 和阈值升级必须有兼容窗口、回滚路径和历史复现能力。
7. **本地优先。** 敏感工程影像、报告和模型推理优先在本地或内网完成；云端模型作为可选适配。
8. **可解释胜过盲目自动化。** 模型输出要能回到样本、权重、Tool、证据、复核和审计。

## 12.4 模型资产架构

模型资产由五类记录共同组成：

```text
Dataset Registry
        │
        ▼
Experiment Run
        │
        ▼
Model Artifact + Config + Environment
        │
        ▼
Model Registry Version
        │
        ▼
Evaluation Report + Release Gate
        │
        ▼
Production Alias / Gateway Route
```

Model Registry 不直接保存大体积模型字节，而保存模型元数据、版本、状态、别名、血缘和 Artifact 引用。模型权重、Tokenizer、配置、导出文件、评测报告和样例输出存储在 MinIO 或兼容对象存储中，由 PostgreSQL 记录不可变元数据。

## 12.5 Model Registry 规范

Model Registry 是模型资产的权威登记入口。每个模型至少包含以下层次：

| 层次 | 说明 |
|---|---|
| Registered Model | 稳定模型名称，例如 `bridge_damage_detector` |
| Model Version | 不可变版本，例如 `12` 或 `1.4.0` |
| Model Alias | 可变别名，例如 `champion`、`candidate`、`shadow` |
| Model Stage | 生命周期状态，例如 `draft`、`validated`、`canary`、`production`、`deprecated` |
| Model Artifact | 权重、配置、导出格式、Tokenizer、类别表 |
| Model Lineage | 数据集、实验、代码、环境、评测报告和审批记录 |

### 12.5.1 模型元数据

```json
{
  "model_id": "model_bridge_damage_detector",
  "registered_name": "bridge_damage_detector",
  "model_type": "vision_detection",
  "version": "1.4.0",
  "aliases": ["candidate"],
  "stage": "validated",
  "framework": "ultralytics-yolo",
  "task_type": "bridge_damage_detection",
  "class_taxonomy_version": "damage_taxonomy.v1.2.0",
  "artifact_refs": [
    "artifact:model_weight_yolo_1_4_0",
    "artifact:model_config_yolo_1_4_0"
  ],
  "training_dataset_version": "dataset.bridge_damage_train.v2026.07",
  "evaluation_report_id": "eval_report_20260730_001",
  "created_by": "ai_engineer_001",
  "created_at": "2026-07-30T12:00:00+08:00"
}
```

### 12.5.2 模型状态机

```text
draft
  -> training
  -> trained
  -> evaluated
  -> validated
  -> canary
  -> production
  -> deprecated
```

失败或中止路径：

```text
training/evaluated/validated/canary
  -> rejected

production
  -> rolled_back
  -> deprecated
```

只有 `validated` 及以上状态的模型可以进入受控灰度；只有 `production` 或指定项目 `canary` 模型可被生产 Workflow 调用。

## 12.6 Dataset Registry 与样本治理

Dataset Registry 负责管理训练集、验证集、测试集、固定回归集、难例集和生产反馈集。

### 12.6.1 数据集类型

| 数据集 | 用途 | 是否可随训练变化 |
|---|---|---|
| `train` | 模型训练 | 可迭代 |
| `validation` | 训练期调参 | 可迭代，但需记录版本 |
| `test_locked` | 发布前固定评测 | 不可随意变更 |
| `regression_fixed` | 升级回归对比 | 不可随意变更 |
| `hard_cases` | 难例、低频、高风险场景 | 可追加，不覆盖 |
| `project_shadow` | 新项目影子评测 | 项目内受控 |
| `human_review_feedback` | 人工复核反馈 | 追加写 |

### 12.6.2 样本分层

桥梁与道路巡检样本必须按业务场景分层，而不是只随机切分。

| 维度 | 示例 |
|---|---|
| 资产类型 | 桥梁、道路、隧道入口、涵洞 |
| 构件类型 | 梁、板、墩、台、支座、桥面铺装、护栏 |
| 病害类型 | 裂缝、剥落、露筋、锈蚀、渗水、坑槽、车辙 |
| 严重程度 | 轻微、中等、严重、需复核 |
| 拍摄条件 | 低照度、逆光、雨后、斜拍、运动模糊 |
| 设备来源 | 无人机、手持相机、车载设备、历史报告图片 |
| 地域与材料 | 不同地区、混凝土、钢结构、沥青、水泥路面 |
| 负样本 | 无病害构件、纹理干扰、阴影、污渍、伸缩缝 |

每个固定评测集必须保存样本清单、Artifact 版本、标注版本、划分规则和哈希摘要。

## 12.7 标注规范与质量控制

模型质量的上限常常由标注质量决定。标注系统必须管理：

- 病害类别定义；
- 构件和位置标注规则；
- 框、分割、关键点、线段和量测标注要求；
- 模糊、遮挡、尺度不明和多病害重叠场景；
- 负样本和忽略区域；
- 标注人、复核人和质检状态；
- 标注工具版本和导出格式。

### 12.7.1 标注状态

```text
imported
  -> labeling
  -> labeled
  -> qa_review
  -> accepted
  -> rejected
  -> superseded
```

`accepted` 标注可进入训练和固定评测集。`rejected` 和 `superseded` 标注不得继续作为有效标签参与新模型训练，但历史实验仍保留当时引用。

### 12.7.2 质检指标

| 指标 | 说明 |
|---|---|
| 标注完整率 | 样本是否覆盖所有目标病害 |
| 类别一致率 | 不同标注人类别判断是否一致 |
| 边界一致率 | 框/分割边界 IoU 或偏差 |
| 位置描述一致率 | 构件、桩号、相对位置是否一致 |
| 低频类别覆盖 | 稀缺病害是否达到最低样本量 |
| 负样本有效率 | 负样本是否真实具有干扰性 |

## 12.8 Experiment Tracking

Experiment Tracking 记录训练、微调、导出、评测和 Prompt/Schema 回归实验。每一次实验至少记录：

| 字段 | 说明 |
|---|---|
| `experiment_id` | 实验 ID |
| `run_id` | 单次运行 ID |
| `model_family` | YOLO、MLX LLM、Embedding、Reranker 等 |
| `dataset_versions` | 训练、验证、测试数据集版本 |
| `code_version` | Git commit 或容器镜像摘要 |
| `config_hash` | 超参数、增强、阈值、后处理配置 |
| `environment` | Python、框架、设备、依赖版本 |
| `artifact_refs` | 权重、日志、曲线、混淆矩阵、示例输出 |
| `metrics` | 模型指标和业务指标 |
| `owner` | 负责人 |
| `started_at` / `completed_at` | 时间 |

实验记录不得只保存“最佳模型文件”。如果没有数据集、代码、配置和环境，模型版本无法复现。

## 12.9 视觉模型评测

视觉模型评测分为基础指标、分层指标和工程指标。

### 12.9.1 基础指标

| 指标 | 说明 | 用途 |
|---|---|---|
| Precision | 预测为病害的样本中有多少是真病害 | 控制误检 |
| Recall | 真实病害中有多少被检测出 | 控制漏检 |
| mAP@0.5 | IoU 0.5 下平均精度 | 常规检测对比 |
| mAP@0.5:0.95 | 多 IoU 阈值平均精度 | 更严格的定位质量 |
| Confusion Matrix | 类别混淆关系 | 找出易混病害 |
| FPS / latency | 推理速度 | 生产吞吐 |
| peak memory | 峰值内存 | 本地部署容量 |

### 12.9.2 分层指标

每个模型发布前必须输出分层评测：

- 按病害类别；
- 按构件类型；
- 按拍摄条件；
- 按设备来源；
- 按轻微/严重程度；
- 按新项目与历史项目；
- 按负样本干扰类型。

如果总体 mAP 提升但高风险病害 Recall 下降，发布门禁应阻断。

### 12.9.3 工程指标

| 指标 | 说明 |
|---|---|
| 关键病害漏检率 | 高风险类别漏检占比 |
| 复核命中率 | 进入人工复核的候选中最终确认比例 |
| 误检工时 | 每 100 张图需人工驳回的候选数 |
| 报告可用率 | 检测结果能直接进入报告草稿的比例 |
| 低置信覆盖 | 低置信结果是否正确触发复核 |
| 位置可用率 | 病害能映射到构件或路线位置的比例 |

## 12.10 量测与空间模型评测

裂缝宽度、长度、面积、构件定位和路线位置不仅要识别正确，还要量测可信。

| 评测项 | 指标 |
|---|---|
| 裂缝宽度 | MAE、P95 误差、超阈值误差率 |
| 裂缝长度 | 相对误差、端点偏差 |
| 剥落面积 | IoU、面积相对误差 |
| 构件映射 | Top-1 准确率、冲突率 |
| GIS 坐标 | 平面误差、SRID 正确率 |
| 桩号定位 | 米级误差、路线方向错误率 |
| 尺度校准 | 标尺识别率、尺度缺失报警率 |

量测模型发布必须绑定校准证据。没有尺度、坐标系或构件基准的量测结果应标记为 `requires_review`。

## 12.11 Embedding、Reranker 与检索评测

Embedding 和 Reranker 影响 RAG 与 Memory 召回质量。评测不能只看语义相似度分数，而要看是否找到了正确证据。

| 指标 | 说明 |
|---|---|
| Recall@K | 正确证据是否出现在前 K 个候选中 |
| MRR | 正确证据排名位置 |
| nDCG | 排序质量 |
| Citation Hit Rate | 报告引用能否命中正确条文或案例 |
| Permission Leakage Rate | 是否召回无权限证据 |
| Version Correctness | 是否命中有效版本 |
| Conflict Surfacing Rate | 冲突证据是否被暴露 |

RAG 与 Memory 的评测必须带权限维度：同一查询在不同组织、项目和角色下可能有不同合法结果。

## 12.12 LLM、Prompt 与结构化输出评测

大语言模型在 BridgeAI-Agent 中主要负责任务理解、工具选择、证据解释、报告草稿和澄清拒答。评测应覆盖：

| 评测项 | 指标 |
|---|---|
| 任务理解 | 意图识别准确率、缺失信息识别率 |
| Tool 调用 | 参数合法率、越权拦截率、错误工具选择率 |
| 结构化输出 | JSON 合法率、Schema 通过率、业务校验通过率 |
| 报告草稿 | 引用覆盖率、事实一致率、工程表达合格率 |
| 拒答与澄清 | 不安全请求拒答率、澄清问题有效率 |
| 提示注入 | 绕过失败率、污染识别率 |
| 成本性能 | token 消耗、延迟、重试率 |

LLM 评测集必须保存 Prompt 版本、Schema 版本、模型版本、RAG Evidence Pack、Memory Context 和期望输出。若任一输入版本变化，评测结果不得与旧结果直接混比。

## 12.13 Agent 与 Workflow 端到端评测

Agent 和 Workflow 的评测关注完整任务闭环：

```text
上传资料
  -> 创建任务
  -> 影像校验
  -> 病害检测
  -> 量测和定位
  -> RAG 证据检索
  -> 人工复核
  -> 报告草稿
  -> 渲染和签发
```

端到端指标：

| 指标 | 说明 |
|---|---|
| 任务成功率 | 从创建到完成的比例 |
| 节点恢复率 | 失败后能从稳定节点恢复的比例 |
| 重复副作用率 | 幂等失败导致的重复结果 |
| 人工复核触发准确率 | 应复核项是否进入复核 |
| 报告签发阻断正确率 | 不满足门禁的报告是否被阻断 |
| 审计完整率 | 是否能回溯模型、数据、Prompt、Tool 和证据 |
| 平均处理时长 | 总时长和各节点时长 |

端到端评测应使用真实结构的项目样本，不用单张图片和模拟报告代替完整业务链。

## 12.14 固定评测集与难例集

固定评测集用于比较模型版本，难例集用于防止已知风险回归。

### 12.14.1 固定评测集规则

- 样本清单不可原地修改；
- 标注版本不可覆盖；
- 每次评测记录模型、配置、阈值、后处理版本；
- 若发现标注错误，创建新评测集版本；
- 历史评测报告继续引用旧版本；
- 不得把失败样本从固定集删除来提升指标。

### 12.14.2 难例来源

| 来源 | 示例 |
|---|---|
| 人工驳回 | 模型误把阴影识别为裂缝 |
| 人工补检 | 模型漏检细裂缝 |
| 项目投诉 | 报告中病害位置不准确 |
| 低置信复核 | 置信度低但最终确认为真实病害 |
| 新设备 | 新无人机或相机导致成像分布变化 |
| 新环境 | 夜间、雨后、强反光、遮挡 |

难例集只追加，不覆盖。进入发布门禁的难例集必须锁定版本。

## 12.15 Model Gateway 与运行时治理

Model Gateway 是模型调用的统一入口，负责加载、路由、并发、资源、审计和降级。

```text
Tool / Agent / RAG / Report
        │
        ▼
Model Gateway
        ├── Vision Model Runtime
        ├── MLX LLM Runtime
        ├── Embedding Runtime
        ├── Reranker Runtime
        └── Optional Cloud LLM Adapter
```

### 12.15.1 Gateway 职责

| 职责 | 说明 |
|---|---|
| 模型解析 | 根据任务、项目和策略选择模型版本 |
| 加载管理 | 预热、卸载、缓存、并发限制 |
| 资源控制 | GPU/CPU/统一内存预算 |
| 输入校验 | Artifact、尺寸、格式、权限 |
| 输出校验 | Schema、置信度、Artifact、错误码 |
| 审计 | 记录 model_call_id、版本、耗时、成本 |
| 降级 | 模型不可用时切备用或转人工 |

Agent 和 Tool 不直接硬编码权重路径。所有模型调用都通过 Model Gateway 或 Tool Runtime 的受控适配。

## 12.16 发布门禁

模型发布分为四类门禁：

| 门禁 | 内容 |
|---|---|
| 数据门禁 | 数据集版本、标注质检、样本分层、难例覆盖 |
| 模型门禁 | 基础指标、分层指标、性能、资源 |
| 业务门禁 | 复核命中、报告可用、端到端任务成功 |
| 安全门禁 | 权限、提示注入、无证据拒答、越权召回 |

### 12.16.1 发布判定

```json
{
  "release_gate_id": "gate_20260730_001",
  "model_version": "bridge_damage_detector:1.4.0",
  "decision": "blocked",
  "reasons": [
    {
      "code": "HIGH_RISK_RECALL_REGRESSION",
      "message": "支座锈蚀 Recall 较 production 版本下降 4.2%",
      "metric": "recall.support_corrosion",
      "threshold": "no_regression"
    }
  ],
  "allowed_actions": ["investigate", "add_hard_cases", "rerun_evaluation"]
}
```

门禁失败时不得把模型标记为 production。可以进入 `rejected`、`draft` 返工或 `shadow` 影子评测。

## 12.17 Champion/Challenger、灰度与回滚

生产模型采用 Champion/Challenger 策略：

| 角色 | 含义 |
|---|---|
| Champion | 当前生产默认模型 |
| Challenger | 候选模型，只进行灰度或影子评测 |
| Shadow | 只旁路运行，不影响正式结果 |
| Canary | 在小范围项目或样本上产生受控结果 |

### 12.17.1 灰度规则

- 灰度范围按组织、项目、资产类型、任务类型和用户角色控制；
- 高风险报告签发仍以 Champion 结果为主；
- Challenger 输出必须单独标识；
- 影子评测不得写入正式病害结论；
- 灰度期间自动收集差异、复核意见和性能指标；
- 回滚只切换别名或路由，不删除模型和评测记录。

### 12.17.2 回滚触发

| 触发 | 动作 |
|---|---|
| 高风险漏检上升 | 立即停止灰度，切回 Champion |
| 报告草稿事实错误上升 | 停用相关 LLM/Prompt 组合 |
| 延迟或内存超限 | 降级到轻量模型或排队 |
| 权限或证据泄漏 | 安全事件处理，冻结发布 |
| 人工复核驳回率异常 | 暂停生产别名切换 |

## 12.18 生产监控与漂移检测

生产监控不仅看服务可用，还要看模型质量是否漂移。

| 监控项 | 指标 |
|---|---|
| 输入分布 | 图像尺寸、亮度、模糊、设备、项目区域 |
| 输出分布 | 病害数量、类别比例、置信度分布 |
| 复核结果 | 确认率、驳回率、修改率、补证率 |
| 业务结果 | 报告通过率、开放问题数量、签发阻断 |
| 性能资源 | 延迟、吞吐、内存、加载时间 |
| RAG/Memory | 召回命中、无证据、冲突、权限拒绝 |
| LLM 输出 | Schema 失败、拒答、注入拦截、token 消耗 |

漂移告警必须关联模型版本、项目、设备、数据集分层和最近发布事件。不能只说“模型效果下降”，必须能定位到场景或版本。

## 12.19 人工复核反馈与数据闭环

人工复核是模型改进闭环的核心。

```text
AI 候选结果
  -> 人工确认 / 驳回 / 修改 / 补证
  -> Review Event
  -> Feedback Dataset Candidate
  -> 标注质检
  -> Dataset Registry 新版本
  -> 训练/评测
  -> 发布门禁
```

### 12.19.1 反馈类型

| 类型 | 用途 |
|---|---|
| `false_positive` | 降低误检 |
| `false_negative` | 补充漏检样本 |
| `class_correction` | 修正类别混淆 |
| `measurement_correction` | 改进量测 |
| `location_correction` | 改进构件/桩号映射 |
| `report_text_revision` | 改进报告草稿 |
| `citation_correction` | 改进 RAG 引用 |
| `unsafe_output` | 改进安全评测 |

反馈进入训练集前必须经过标注质检和脱敏处理，不能把单次人工修改直接变成生产模型更新。

## 12.20 成本、性能与资源调度

模型管理必须同时关注质量、成本和资源。

| 模型类型 | 主要资源 | 控制策略 |
|---|---|---|
| YOLO 检测 | GPU/统一内存/CPU | 批量推理、并发限制、预热 |
| 分割模型 | GPU/内存 | 按需加载、区域裁剪 |
| MLX LLM | 统一内存 | 与视觉推理错峰、上下文预算 |
| Embedding | CPU/GPU | 批处理、索引任务队列 |
| Reranker | GPU/CPU | Top-K 限制、缓存 |
| Cloud LLM | token 成本/网络 | 策略白名单、脱敏、预算 |

每次模型调用至少记录：

- `model_call_id`；
- `model_id`、`model_version`、`alias`；
- 输入 Artifact 和哈希；
- 输出 Artifact 和哈希；
- 延迟、内存、token 或推理步数；
- 调用方 Tool/Workflow 节点；
- 成功/失败/降级状态；
- 审计和 trace ID。

## 12.21 安全、合规与数据保护

模型治理必须遵守工程数据安全和责任边界：

- 敏感项目影像默认不出本地或内网；
- 云端 LLM 调用必须完成脱敏、授权和审计；
- 模型训练数据必须有来源、授权和保留策略；
- 已签发报告和人工复核记录不得因模型升级改写；
- 模型评测报告不得泄露原始敏感图片；
- 模型输出不得绕过人工复核和签发责任；
- 训练/评测环境不得保存生产密钥；
- 外部模型权重和依赖必须记录来源和许可证。

模型安全事件包括：

| 事件 | 示例 |
|---|---|
| 数据泄漏 | 评测样本被上传到未授权云服务 |
| 权限绕过 | 模型召回无权限项目证据 |
| 输出污染 | LLM 生成无依据工程结论 |
| 训练污染 | 恶意或错误标注进入训练集 |
| 供应链风险 | 未知来源权重进入生产 |

## 12.22 评测报告与发布记录

每次候选模型进入 `validated`、`canary` 或 `production` 前，必须生成评测报告。

### 12.22.1 评测报告结构

```json
{
  "evaluation_report_id": "eval_report_20260730_001",
  "model_version": "bridge_damage_detector:1.4.0",
  "baseline_model_version": "bridge_damage_detector:1.3.2",
  "dataset_versions": [
    "dataset.bridge_damage_test_locked.v2026.07",
    "dataset.bridge_damage_hard_cases.v2026.07"
  ],
  "metric_summary": {
    "map50": 0.842,
    "precision": 0.887,
    "recall": 0.801,
    "high_risk_recall_delta": -0.042
  },
  "business_summary": {
    "review_hit_rate": 0.73,
    "report_ready_rate": 0.68,
    "manual_reject_per_100_images": 12.4
  },
  "decision": "blocked",
  "reviewers": ["ai_engineer_001", "bridge_engineer_007"],
  "created_at": "2026-07-30T12:30:00+08:00"
}
```

### 12.22.2 发布记录

发布记录必须包含：

- 发布范围；
- 旧版本和新版本；
- 别名切换时间；
- 审批人；
- 门禁结果；
- 回滚方案；
- 观察窗口；
- 生产监控指标；
- 是否影响历史任务复现。

## 12.23 第一阶段实施里程碑

### 12.23.1 M1：模型与数据资产登记

目标：

- 建立 Model Registry、Dataset Registry 和 Artifact 引用；
- 登记现有 YOLO/MLX/Embedding 模型；
- 登记现有训练集、验证集、固定评测集和难例集；
- 建立模型调用审计字段。

验收：

- 每个生产模型有权重、配置、类别表和评测报告引用；
- 每个数据集有样本清单、标注版本和哈希；
- 生产任务能记录模型版本。

### 12.23.2 M2：视觉模型固定评测与回归

目标：

- 建立桥梁/道路病害固定评测集；
- 输出 Precision、Recall、mAP、混淆矩阵、分层指标和工程指标；
- 建立升级回归比较；
- 接入人工复核反馈候选集。

验收：

- 新模型发布前自动生成评测报告；
- 高风险病害 Recall 下降会阻断发布；
- 难例集不会被覆盖修改；
- 复核反馈能进入候选数据集。

### 12.23.3 M3：LLM、RAG、Memory 与 Agent 评测

目标：

- 建立任务理解、Tool 调用、RAG 引用、Memory 使用、报告草稿和安全注入评测集；
- 评测结果按模型、Prompt、Schema、Tool 和 Evidence 版本归档；
- 端到端任务闭环评测接入 Workflow；
- 引入无证据拒答和人工复核触发指标。

验收：

- Prompt/LLM 升级有回归报告；
- RAG 无权限召回率为 0；
- 报告草稿关键结论引用覆盖达到阈值；
- 端到端任务审计链完整。

### 12.23.4 M4：灰度、监控与持续迭代

目标：

- 实现 Champion/Challenger 别名和灰度范围；
- 建立生产漂移监控；
- 建立模型回滚 Runbook；
- 将评测报告和生产指标展示到管理后台。

验收：

- 灰度模型可按项目范围启停；
- 回滚不破坏历史任务；
- 漂移告警可定位场景；
- 管理后台能查看模型版本、评测报告和发布记录。

## 12.24 架构决策记录

### ADR-012-001：模型治理记录以 BridgeAI Registry 为权威

**状态：** Accepted

**背景：** MLflow 等工具适合实验追踪和模型注册，但 BridgeAI-Agent 还需要绑定项目、Artifact、Workflow、报告和审计。

**决定：** BridgeAI 自有 Registry 作为生产权威记录，MLflow 等外部工具作为可选实验与评测后端。

**后果：** 需要维护一套业务模型治理表；但生产复现和审计可以与巡检业务实体闭合。

### ADR-012-002：发布门禁以业务指标为主，模型指标为辅

**状态：** Accepted

**背景：** 总体 mAP 提升可能掩盖关键病害 Recall 下降或人工复核工时增加。

**决定：** 模型发布必须同时满足基础模型指标、分层指标、业务指标和安全指标。

**后果：** 发布流程更严格，但能避免“指标好看、工程不可用”的模型进入生产。

### ADR-012-003：固定评测集不可原地修改

**状态：** Accepted

**背景：** 如果评测集被静默修改，不同模型版本指标不可比较。

**决定：** 固定评测集、标注版本和样本清单均不可原地覆盖，修正错误时创建新版本。

**后果：** 数据管理成本增加，但模型比较和历史复现更可靠。

### ADR-012-004：人工复核反馈先质检再进入训练

**状态：** Accepted

**背景：** 单次人工修改可能来自项目特殊要求、误操作或临时表达偏好。

**决定：** 人工复核反馈先进入候选集，经标注质检、脱敏和版本登记后才能进入训练或固定评测。

**后果：** 数据闭环速度更慢，但能降低训练污染风险。

### ADR-012-005：Embedding/RAG 模型升级必须重建并验证索引版本

**状态：** Accepted

**背景：** Embedding 模型变化会改变向量空间，旧索引不可直接混用。

**决定：** Embedding、切分、Reranker 或过滤策略升级时，创建新索引版本并通过召回、权限和引用评测后切换。

**后果：** 索引重建成本增加，但避免新旧向量空间混杂导致证据错误。

### ADR-012-006：LLM 与 Prompt/Schema 作为组合体评测

**状态：** Accepted

**背景：** LLM 输出质量取决于模型、Prompt、Schema、Tool 描述、RAG 和 Memory 上下文。

**决定：** LLM 发布或 Prompt/Schema 发布必须记录组合版本并执行组合回归。

**后果：** 评测矩阵变大，但可以定位质量回归来自模型还是 Prompt/Schema。

### ADR-012-007：灰度和影子评测不得改写正式结论

**状态：** Accepted

**背景：** Challenger 模型可能表现不稳定，若直接写入正式病害和报告，会破坏工程责任链。

**决定：** Challenger 在影子和灰度阶段默认只生成对比结果；正式结论仍由 Champion 或人工确认路径产生。

**后果：** 新模型验证周期更长，但生产结果更安全。

### ADR-012-008：模型回滚通过别名/路由切换而非删除

**状态：** Accepted

**背景：** 删除模型会破坏历史任务复现和审计链。

**决定：** 回滚通过 Model Alias、Gateway Route 或发布策略切回旧版本，保留所有模型和评测记录。

**后果：** Registry 中会保留更多历史版本，但审计和复现能力完整。

## 参考资料

1. [MLflow 官方文档：Model Registry](https://mlflow.org/docs/latest/model-registry.html)
2. [MLflow 官方文档：Tracking](https://mlflow.org/docs/latest/tracking.html)
3. [MLflow 官方文档：GenAI Evaluation](https://mlflow.org/docs/latest/genai/eval-monitor/)
4. [Ultralytics 官方文档：Model Validation](https://docs.ultralytics.com/modes/val/)
5. [Ultralytics 官方文档：Benchmark](https://docs.ultralytics.com/modes/benchmark/)
6. [OpenAI Platform Docs：Evals](https://platform.openai.com/docs/guides/evals)

## 修订记录

| 版本 | 日期 | 修订内容 | 修订人 |
|---|---|---|---|
| V1.0 | 2026-07-30 | 创建第十二章，定义模型资产、数据集、实验追踪、评测、发布门禁、灰度回滚和生产反馈闭环 | Codex |
