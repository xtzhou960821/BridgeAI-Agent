# BridgeAI-Agent Chapter 12 Model Management and Evaluation Design Spec

## 1. 背景

BridgeAI-Agent 前十一章已经完成项目目标、总体架构、Agent、Tool SDK、Workflow、RAG、Memory、数据与数据库、MCP、Prompt 与结构化输出以及后端/前端架构。第十二章需要继续按照第一章确定的正式目录，定义模型管理与评测体系，使视觉模型、文本模型、Embedding 模型、RAG/Memory 组件、Prompt/Schema 和 Agent 工作流能够以统一的资产登记、评测基线、发布门禁、灰度回滚和生产监控方式治理。

第十二章不得把模型管理简化为“保存一个权重文件”，也不得把评测简化为 mAP、Precision、Recall 或人工观感。桥梁与道路巡检的模型质量必须回到业务场景：低置信度病害是否进入复核、关键病害是否漏检、报告引用是否有证据、模型升级后历史报告是否可复现、不同模型结果冲突能否被解释和审计。

## 2. 范围

正式范围聚焦桥梁与道路巡检 AI Agent 第一阶段，包括：

- 模型资产分类、Model Registry、版本、别名、状态和血缘；
- 数据集资产、样本分层、标注规范、质检、固定评测集和难例集；
- 实验追踪、训练记录、模型 Artifact、配置、环境和指标归档；
- 视觉模型、量测模型、Embedding 模型、LLM、Prompt/Schema、RAG、Memory 和 Agent Workflow 的评测指标；
- 离线评测、回归评测、端到端业务评测和人工复核评测；
- 发布门禁、灰度、回滚、Champion/Challenger、生产漂移和反馈闭环；
- 模型调用审计、成本、性能、资源调度和合规要求；
- 第一阶段模型与评测清单、里程碑和 ADR。

不纳入：

- 具体模型训练代码实现；
- 大规模分布式训练平台建设；
- 商业模型采购和价格比较；
- 通用行业大模型训练；
- 云端 MLOps 平台完整部署；
- 第十三章部署监控安全的基础设施细节。

## 3. 官方资料基线

核验日期：2026-07-30。

正文参考 MLflow 官方文档关于 Experiment Tracking、Model Registry、Model Version、Alias、Artifacts、Evaluation Dataset 和 GenAI Evaluation 的能力说明；参考 Ultralytics YOLO 官方文档关于训练、验证、mAP、Precision、Recall、IoU、Benchmark 和导出格式评测的说明；参考 OpenAI Evals API 作为 LLM/Agent 评测接口的可选外部能力；沿用前十章关于 Tool、Workflow、RAG、Memory、Prompt/Schema、Artifact 和审计的版本约束。

第十二章只把这些技术作为可选实现基线，不把 MLflow、Ultralytics 或任一模型服务作为不可替代依赖。BridgeAI-Agent 的权威模型治理记录仍以 PostgreSQL 业务表、Artifact 版本、评测报告和发布审计为准。

## 4. 设计原则

1. Model as governed artifact：模型是受治理 Artifact，不是可随意替换的文件路径。
2. Dataset before metric：指标必须绑定固定数据集版本、标注规范和样本分层。
3. Business eval over single metric：发布门禁以工程业务指标为主，模型指标为必要但不充分条件。
4. Reproducible by lineage：模型、数据、代码、配置、环境、Prompt、Schema、Tool 和报告都要可追溯。
5. Human review as signal：人工复核不是流程拖累，而是持续改进的重要标注与评测来源。
6. Champion/Challenger：生产默认使用冠军版本，挑战者只能灰度或影子评测。
7. Safe rollback：任何模型、Prompt 或评测策略升级都必须具备回滚和历史复现能力。
8. Local-first with optional cloud：视觉模型和敏感工程数据优先本地，云端模型作为受控适配。

## 5. 章节交付要求

创建 `docs/md/BridgeAI-Agent-第十二章-模型管理与评测体系-V1.0.md`，并同步 `README.md`。正文应包含 12.1 至 12.24、参考资料和修订记录；至少包含：

- 模型资产分类、Model Registry、Dataset Registry 和 Experiment Tracking；
- 视觉模型、Embedding、LLM、Prompt/Schema、RAG、Memory 和 Agent Workflow 评测；
- 固定评测集、难例集、业务场景集、人工复核样本和数据闭环；
- 发布门禁、灰度、回滚、Champion/Challenger、生产漂移和监控；
- 模型调用审计、成本、性能、资源调度和合规；
- 第一阶段模型/评测清单和实施里程碑；
- ADR-012-001 至 ADR-012-008。

## 6. 验证要求

最低验证：

```bash
doc='docs/md/BridgeAI-Agent-第十二章-模型管理与评测体系-V1.0.md'
test -f "$doc"
test "$(rg -c '^## 12\.[0-9]+ ' "$doc")" -eq 24
test "$(rg -c '^### ADR-012-' "$doc")" -eq 8
test "$(awk '/^```/{n++} END{print n%2}' "$doc")" -eq 0
rg -n 'Model Registry|Dataset Registry|Experiment Tracking|mAP|Precision|Recall|Champion|Challenger|灰度|回滚|漂移|人工复核|评测报告' "$doc"
rg -n '第十二章-模型管理与评测体系-V1.0.md|已完成十二章' README.md
git diff --check
```

不得把未搭建的真实模型注册表、评测平台、训练流水线、生产灰度系统或监控看板写成已验证。
