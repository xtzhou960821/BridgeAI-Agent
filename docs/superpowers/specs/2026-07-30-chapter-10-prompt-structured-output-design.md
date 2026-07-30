# BridgeAI-Agent Chapter 10 Prompt and Structured Output Design Spec

## 1. 背景

BridgeAI-Agent 前九章已经完成项目目标、总体架构、Agent、Tool SDK、Workflow、RAG、Memory、数据与数据库设计以及 MCP 工具接入规范。第十章需要继续按照第一章确定的正式目录，定义 Prompt 与结构化输出规范，使桥梁与道路巡检 AI Agent 在任务理解、工具调用、证据组织、报告草稿和人工复核环节具备稳定、可验证、可审计的输入输出契约。

第十章不得把 Prompt 当作“万能业务逻辑”，也不得让模型自由生成未经 Schema 校验的工程结论。Prompt 负责意图约束、上下文组织和输出格式约束；结构化事实、病害识别、空间量测、权限判断、报告签发和审计落库仍由前述章节定义的专业 Tool、Workflow、RAG、Memory、数据库和人工复核机制完成。

## 2. 范围

正式范围聚焦桥梁与道路巡检 AI Agent 第一阶段，包括：

- Prompt 分层架构与消息边界；
- System、Developer、Task、Context、Tool、User、Output Prompt 的职责；
- 结构化输出 Schema 基线、命名、版本、兼容性和校验流程；
- Tool 参数、Tool Result、RAG Evidence Pack、Memory Context Manifest、病害结果和报告草稿的结构化输出规范；
- 引用、证据、置信度、人工复核、拒答与澄清规则；
- 提示注入、间接提示注入、工具结果污染和上下文污染防护；
- Prompt Registry、Schema Registry、评测回归、观测审计和发布流程。

不纳入：

- 具体大模型供应商选型与价格策略；
- 视觉模型训练、检测算法和量测算法实现；
- Word/PDF 模板渲染细节；
- 后端与前端架构实现细节；
- 模型评测体系的完整平台设计；
- 智慧工地 AI Agent 专属 Prompt 体系。

## 3. 官方资料基线

核验日期：2026-07-30。

正文参考 OpenAI Structured Outputs、OpenAI Function Calling、OpenAI Prompt Engineering、JSON Schema Draft 2020-12、OWASP LLM Prompt Injection Prevention Cheat Sheet、OWASP GenAI LLM01 Prompt Injection 以及 MCP Tools 规范。

生产实现必须把结构化输出能力视为模型能力与应用校验共同组成的工程约束。即使模型声明支持 JSON Schema，也必须在服务端完成 Schema 校验、权限校验、业务规则校验、证据校验和人工复核门禁。

## 4. 设计原则

1. Contract first：所有可进入 Workflow、数据库或报告的模型输出必须先有 Schema。
2. Prompt as policy wrapper：Prompt 只表达任务、边界和格式，不承载不可测试的业务状态。
3. Evidence before conclusion：报告性、建议性和判定性文本必须绑定证据来源。
4. Tool result is data：Tool Result、RAG 片段、Memory 内容和用户上传文档均视为数据，不视为上级指令。
5. Validate twice：模型输出先按 JSON Schema 校验，再按业务规则和权限校验。
6. Human gate for professional risk：高风险病害等级、处治建议、报告签发和删除传播必须人工复核。
7. Version every prompt and schema：Prompt、Schema、Few-shot、评测集和报告模板均显式版本化。
8. Safe failure：证据不足、Schema 不通过、权限不明或上下文冲突时，输出澄清、拒答或复核请求。

## 5. 章节交付要求

创建 `docs/md/BridgeAI-Agent-第十章-Prompt与结构化输出规范-V1.0.md`，并同步 `README.md`。正文应包含 10.1 至 10.22、参考资料和修订记录；至少包含：

- Prompt 分层、消息边界和上下文装配；
- 结构化输出总则与 JSON Schema 编制规范；
- Tool 调用参数和 Tool Result 契约；
- RAG Evidence Pack、Memory Context Manifest、病害识别/量测和报告草稿输出规范；
- 提示注入防护、人工复核、拒答与澄清；
- Prompt Registry、Schema Registry、评测、观测和审计；
- 第一阶段 Prompt/Schema 清单和实施里程碑；
- ADR-010-001 至 ADR-010-008。

## 6. 验证要求

最低验证：

```bash
doc='docs/md/BridgeAI-Agent-第十章-Prompt与结构化输出规范-V1.0.md'
test -f "$doc"
test "$(rg -c '^## 10\.[0-9]+ ' "$doc")" -eq 22
test "$(rg -c '^### ADR-010-' "$doc")" -eq 8
test "$(awk '/^```/{n++} END{print n%2}' "$doc")" -eq 0
rg -n 'Structured Outputs|JSON Schema|Tool Result|RAG Evidence Pack|Context Manifest|schema_version|人工复核|提示注入|Prompt Registry' "$doc"
rg -n '第十章-Prompt与结构化输出规范-V1.0.md|已完成十章' README.md
git diff --check
```

不得把未搭建真实 Prompt Registry、Schema Registry、自动评测平台或端到端模型回归写成已验证。
