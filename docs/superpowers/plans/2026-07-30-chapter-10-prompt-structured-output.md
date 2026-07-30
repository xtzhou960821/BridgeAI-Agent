# BridgeAI-Agent Chapter 10 Prompt and Structured Output Implementation Plan

**Goal:** 编制第十章《Prompt 与结构化输出规范》V1.0，完成正式 Markdown、README 同步和基础验证。

**Scope:** 桥梁与道路巡检 AI Agent 第一阶段 Prompt、结构化输出、证据引用、人工复核和安全防护规范。

## Task 1: 核验资料与创建正文

- Read chapters 1, 4, 5, 6, 7, 8, 9 for boundaries.
- Verify official OpenAI Structured Outputs, Function Calling and Prompt Engineering docs.
- Verify JSON Schema 2020-12 and OWASP prompt injection guidance.
- Create `docs/md/BridgeAI-Agent-第十章-Prompt与结构化输出规范-V1.0.md`.
- Include 10.1-10.22, references and revision record.

## Task 2: 写入 Prompt 与上下文规范

- Define Prompt role in BridgeAI-Agent.
- Define system/developer/task/context/tool/user/output message boundaries.
- Define Context Pack assembly with RAG Evidence Pack and Memory Context Manifest separation.
- Define prompt anti-patterns and reusable prompt package structure.

## Task 3: 写入结构化输出与业务契约

- Define JSON Schema naming, version, compatibility and validation rules.
- Define Tool argument, Tool Result, RAG, Memory, damage detection, measurement and report draft schemas.
- Define citation, confidence, refusal, clarification and human review output semantics.
- Define examples for key schemas.

## Task 4: 写入治理、安全、README 与验证

- Define prompt injection protection, output filtering, tool-result quarantine and registry workflow.
- Define evaluation, observability, audit, release gates and first-stage milestones.
- Add ADR-010-001 to ADR-010-008.
- Update README to completed ten chapters and remove Chapter 10 from future list.
- Verify structure, ADR count, fence balance, key markers, README paths and diff check.
- Commit with `docs: add chapter 10 prompt structured output design`.

## Final verification

```bash
set -e
doc='docs/md/BridgeAI-Agent-第十章-Prompt与结构化输出规范-V1.0.md'
test -f "$doc"
test "$(rg -c '^## 10\.[0-9]+ ' "$doc")" -eq 22
test "$(rg -c '^### ADR-010-' "$doc")" -eq 8
test "$(awk '/^```/{n++} END{print n%2}' "$doc")" -eq 0
! rg -n 'TBD|TODO|FIXME|待补充|待确认|后续确定|BridgeAI-Site' "$doc"
rg -q 'Structured Outputs' "$doc"
rg -q 'JSON Schema' "$doc"
rg -q 'Tool Result' "$doc"
rg -q 'RAG Evidence Pack' "$doc"
rg -q 'Context Manifest' "$doc"
rg -q 'schema_version' "$doc"
rg -q '人工复核' "$doc"
rg -q '提示注入' "$doc"
rg -q 'Prompt Registry' "$doc"
rg -n '第十章-Prompt与结构化输出规范-V1.0.md|已完成十章' README.md
for md_ref in $(rg -o 'docs/md/[^`]+\.md' README.md); do test -f "$md_ref"; done
git diff --check
git status --short --branch
```
