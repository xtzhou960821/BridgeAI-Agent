# BridgeAI-Agent Chapter 9 MCP Tool Integration Implementation Plan

**Goal:** 编制第九章《MCP 工具接入规范》V1.0，完成正式 Markdown、README 同步和基础验证。

**Scope:** 桥梁与道路巡检 AI Agent 第一阶段 MCP Tool 接入；MCP 作为内部 Tool SDK 的外部适配层，不替代 Workflow、RLS、Outbox、Artifact 和审计。

## Task 1: 核验资料与创建正文

- Read chapters 1, 4, 5, 6, 7, 8.
- Verify official MCP 2025-11-25 docs, JSON-RPC 2.0, OAuth/RFC references.
- Create `docs/md/BridgeAI-Agent-第九章-MCP工具接入规范-V1.0.md`.
- Include 9.1-9.25, references and revision record.

## Task 2: 写入核心规范

- Define MCP position, architecture, server grouping and transport choice.
- Map Internal Tool SDK manifest/input/output/errors/artifacts to MCP Tools.
- Define Resources and Prompts exposure boundaries.
- Define lifecycle, capability negotiation, version policy and timeout/cancel behavior.

## Task 3: 写入安全、状态与工程治理

- Define OAuth/token, service identity, organization/project authorization, RLS context.
- Define idempotency, Workflow, Outbox, high-risk human confirmation and audit.
- Define Artifact URI, RAG/Memory, report and damage tool boundaries.
- Define observability, rate limits, deployment and test matrix.

## Task 4: 收尾 README 与验证

- Add ADR-009-001 to ADR-009-008.
- Update README to completed nine chapters and remove Chapter 9 from future list.
- Update `temp/` description because the directory has been intentionally removed.
- Verify structure, ADR count, fence balance, key markers, README paths and diff check.
- Commit with `docs: add chapter 9 mcp tool integration design`.

## Final verification

```bash
set -e
doc='docs/md/BridgeAI-Agent-第九章-MCP工具接入规范-V1.0.md'
test -f "$doc"
test "$(rg -c '^## 9\.[0-9]+ ' "$doc")" -eq 25
test "$(rg -c '^### ADR-009-' "$doc")" -eq 8
test "$(awk '/^```/{n++} END{print n%2}' "$doc")" -eq 0
! rg -n 'TBD|TODO|FIXME|待补充|待确认|后续确定|BridgeAI-Site' "$doc"
rg -q 'MCP Specification 2025-11-25' "$doc"
rg -q 'tools/list' "$doc"
rg -q 'tools/call' "$doc"
rg -q 'resources/list' "$doc"
rg -q 'prompts/list' "$doc"
rg -q 'OAuth' "$doc"
rg -q 'RLS' "$doc"
rg -q 'Outbox' "$doc"
rg -q 'Artifact' "$doc"
rg -q 'Workflow' "$doc"
rg -n '第九章-MCP工具接入规范-V1.0.md|已完成九章' README.md
for md_ref in $(rg -o 'docs/md/[^`]+\.md' README.md); do test -f "$md_ref"; done
git diff --check
git status --short --branch
```
