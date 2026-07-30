# BridgeAI-Agent

BridgeAI-Agent 是面向桥梁与道路巡检、病害检测和工程报告闭环的行业级 AI Agent 架构设计项目。

本仓库当前主要沉淀 V1.0 设计文档。正式文档主线已完成十一章：项目背景、总体架构、Agent、Tool SDK、Workflow、RAG 行业知识库、Memory 与项目上下文、数据与数据库设计、MCP 工具接入规范、Prompt 与结构化输出规范，以及后端与前端架构。

## 目录结构

```text
.
├── agent/       # Agent 模块预留目录
├── backend/     # 后端服务预留目录
├── docs/
│   ├── md/      # 第一套目录的正式 Markdown 设计文档
│   ├── superpowers/
│   │   ├── specs/   # 已确认的章节编制设计
│   │   └── plans/   # 已确认的章节实施计划
│   └── ai-agent-workflow-infographic.png
├── examples/    # 示例与演示材料预留目录
├── frontend/    # 前端应用预留目录
└── tools/       # Tool SDK 与工具实现预留目录
```

## 正式架构文档

1. `docs/md/BridgeAI-Agent-第一章-项目背景与建设目标-V1.0.md`
2. `docs/md/BridgeAI-Agent-第二章-总体架构设计-V1.0.md`
3. `docs/md/BridgeAI-Agent-第三章-Agent总体设计-V1.0.md`
4. `docs/md/BridgeAI-Agent-第四章-Tool-SDK设计规范-V1.0.md`
5. `docs/md/BridgeAI-Agent-第五章-Workflow与任务编排系统设计-V1.0.md`
6. `docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md`
7. `docs/md/BridgeAI-Agent-第七章-Memory与项目上下文设计-V1.0.md`
8. `docs/md/BridgeAI-Agent-第八章-数据与数据库设计-V1.0.md`
9. `docs/md/BridgeAI-Agent-第九章-MCP工具接入规范-V1.0.md`
10. `docs/md/BridgeAI-Agent-第十章-Prompt与结构化输出规范-V1.0.md`
11. `docs/md/BridgeAI-Agent-第十一章-后端与前端架构-V1.0.md`

当前正式主线聚焦桥梁与道路巡检 AI Agent。历史 `temp/` 参考目录已清理，避免与 `docs/md/` 当前第一套正式目录混淆；智慧工地 BridgeAI-Site 不属于当前正式主线。

## 后续章节

按照第一章确定的目录，后续将继续编制：

- 第十二章：模型管理与评测体系；
- 第十三章：部署、监控与安全；
- 第十四章：实施路线图与版本规划。

当前 `agent/`、`backend/`、`frontend/`、`tools/` 和 `examples/` 为后续研发预留目录。
