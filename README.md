# BridgeAI-Agent

BridgeAI-Agent 是面向桥梁与道路巡检、病害检测和工程报告闭环的行业级 AI Agent 架构设计项目。

本仓库当前主要沉淀 V1.0 设计文档。正式文档主线已完成十四章：项目背景、总体架构、Agent、Tool SDK、Workflow、RAG 行业知识库、Memory 与项目上下文、数据与数据库设计、MCP 工具接入规范、Prompt 与结构化输出规范、后端与前端架构、模型管理与评测体系、部署监控与安全，以及实施路线图与版本规划。

## 目录结构

```text
.
├── agent/       # Agent Runner 与 Workflow 最小骨架
├── backend/     # 后端服务、API 入口与数据库迁移骨架
├── docs/
│   ├── md/      # 第一套目录的正式 Markdown 设计文档
│   ├── superpowers/
│   │   ├── specs/   # 已确认的章节编制设计
│   │   └── plans/   # 已确认的章节实施计划
│   └── ai-agent-workflow-infographic.png
├── examples/    # 示例任务与演示材料
├── frontend/    # Vue + TypeScript 工作台骨架
├── tests/       # Python 核心骨架测试
└── tools/       # Tool SDK 与工具执行骨架
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
12. `docs/md/BridgeAI-Agent-第十二章-模型管理与评测体系-V1.0.md`
13. `docs/md/BridgeAI-Agent-第十三章-部署监控与安全-V1.0.md`
14. `docs/md/BridgeAI-Agent-第十四章-实施路线图与版本规划-V1.0.md`

当前正式主线聚焦桥梁与道路巡检 AI Agent。历史 `temp/` 参考目录已清理，避免与 `docs/md/` 当前第一套正式目录混淆；智慧工地 BridgeAI-Site 不属于当前正式主线。

## 开发状态

当前已进入 V0.2 可运行工作台阶段，已完成：

- Tool SDK：Tool Manifest、注册表、执行器和必填输入校验；
- Workflow：任务状态创建、推进、失败和恢复；
- Agent Runner：桥梁巡检示例任务的最小单 Agent 调用循环，并在任务理解阶段通过 Model Gateway 调用当前 Agent 模型；
- Backend：FastAPI 健康检查、任务创建、列表、详情、执行和历史接口；
- Backend API：保留 `POST /api/v1/tasks/runs` 兼容接口，并将其纳入持久化执行链路；
- Frontend：Vue + TypeScript 工作台支持创建任务、重复执行和切换历史快照；
- Data：PostgreSQL 保存任务主记录，以及每次执行的模型、Workflow 和 Tool JSONB 快照。

本地验证：

```bash
BRIDGEAI_TEST_DATABASE_URL="$BRIDGEAI_TEST_DATABASE_URL" ./.venv/bin/python -m pytest -q
npm test --prefix frontend
npm run build --prefix frontend
```

`BRIDGEAI_TEST_DATABASE_URL` 必须明确指向数据库 `bridgeai_agent_test`；测试保护会拒绝其他数据库名。

本地首次启动前先显式应用迁移；后端不会在启动时自动修改数据库结构：

```bash
set -a
source .env
set +a
./.venv/bin/python -m backend.app.repositories.postgres.migrate
./.venv/bin/python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
npm run dev --prefix frontend -- --host 127.0.0.1 --port 5173
```

详细说明见 `docs/development/v0.2-local-runbook.md`。

## 后续工作

第一套正式目录十四章已完成。后续可进入：

- 按第十四章路线图拆分研发任务；
- 编制后端、前端、Tool SDK、Agent/Workflow 的实现级 Issue；
- 建立样例项目、演示数据、评测集和部署 Runbook；
- 根据实际研发进展修订 V1.1、V1.2 和 V2.0 规划。

当前 `agent/`、`backend/`、`frontend/`、`tools/` 和 `examples/` 已承载 V0.2 可运行工程。后续将继续补齐 Artifact 对象存储、异步执行、病害复核、报告闭环和部署能力。

当前 Agent 默认模型配置为 oMLX 的 `DeepSeek-V4-Flash-4bit`，API base URL 为 `https://omlx.cpolar.cn/v1`。当前 V0.2 已在任务理解阶段通过 OpenAI-compatible Model Gateway 调用该模型，并随 Workflow 返回模型理解结果、模型 Profile 和 usage。
