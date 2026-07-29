# BridgeAI-Agent Chapter 6 RAG Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a verified V1.0 sixth chapter that defines an implementable RAG industry knowledge base for bridge and road inspection AI Agent workflows.

**Architecture:** The chapter will define PostgreSQL as the authoritative metadata, version, permission, and audit store; Qdrant as the dense and sparse retrieval index; and MinIO as the original-document and parsed-artifact store. Retrieval will use permission filtering, hybrid recall, reranking, evidence packaging, constrained generation, citation validation, and human review for consequential engineering conclusions.

**Tech Stack:** Markdown, PostgreSQL, Qdrant Query API, MinIO object storage, Pydantic contracts, BridgeAI Tool SDK, LangGraph Workflow, local embedding and reranking models, official Ministry of Transport standards sources.

## Global Constraints

- Create only `docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md`; do not modify the existing first five chapters or the user's unrelated working-tree changes.
- Focus on bridge and road inspection; do not introduce the Smart Construction Agent document line.
- Keep RAG responsible for citable external engineering knowledge and keep Memory responsible for project, task, and cross-step context.
- Keep detailed PostgreSQL DDL in Chapter 8, generic Prompt templates in Chapter 10, and full deployment controls in Chapter 13.
- Treat PostgreSQL as the authoritative metadata, version, permission, release-state, and audit store; Qdrant as the retrieval index; MinIO as the original-document and large-artifact store.
- Require source, document version, page, section, or clause location for factual and normative conclusions.
- Require human review for formal condition rating, treatment decisions, equipment control, and report sign-off.
- Verify time-sensitive software and engineering-standard facts against official sources current on 2026-07-29.
- Do not write complete service implementations, complete database migrations, or a reusable Prompt library in this chapter.

---

### Task 1: Establish the official source baseline and chapter skeleton

**Files:**
- Create: `docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md`
- Read: `docs/superpowers/specs/2026-07-29-chapter-6-rag-design.md`
- Read: `docs/md/BridgeAI-Agent-第一章-项目背景与建设目标-V1.0.md`
- Read: `docs/md/BridgeAI-Agent-第二章-总体架构设计-V1.0.md`
- Read: `docs/md/BridgeAI-Agent-第三章-Agent总体设计-V1.0.md`
- Read: `docs/md/BridgeAI-Agent-第四章-Tool-SDK设计规范-V1.0.md`
- Read: `docs/md/BridgeAI-Agent-第五章-Workflow与任务编排系统设计-V1.0.md`

**Interfaces:**
- Consumes: the approved chapter design, existing terminology, Tool boundary, Workflow state model, and official source URLs.
- Produces: a section-numbered Markdown skeleton with the same document-information and revision-record conventions as Chapters 3-5.

- [ ] **Step 1: Reconfirm cross-chapter terminology and constraints**

Run:

```bash
rg -n -i "RAG|知识库|Memory|Qdrant|PostgreSQL|MinIO|knowledge_result_ids|人工复核|证据" docs/md/BridgeAI-Agent-{第一章-项目背景与建设目标,第二章-总体架构设计,第三章-Agent总体设计,第四章-Tool-SDK设计规范,第五章-Workflow与任务编排系统设计}-V1.0.md
```

Expected: output confirms RAG is a Tool-layer knowledge capability, Qdrant is the selected vector database, `knowledge_result_ids` is the Workflow reference field, and long-term knowledge does not belong in LangGraph Checkpoint state.

- [ ] **Step 2: Verify the engineering-standard source set**

Review these official sources and record only facts directly supported by them:

- Ministry of Transport standard search: `https://jtst.mot.gov.cn/`
- JTG 5210-2018 announcement: `https://xxgk.mot.gov.cn/jigou/glj/202006/t20200623_3313114.html`
- JTG 5120-2021 announcement: `https://xxgk.mot.gov.cn/jigou/glj/202108/t20210825_3616530.html`
- JTG/T H21-2011 announcement: `https://xxgk.mot.gov.cn/jigou/glj/202006/t20200623_3312369.html`

Expected: each example standard has a confirmed identifier, title, issuing body, effective date, and replacement status; anything not confirmed is described as an example requiring live catalog validation at ingestion time.

- [ ] **Step 3: Verify the software-capability source set**

Review these official sources:

- Qdrant hybrid queries: `https://qdrant.tech/documentation/search/hybrid-queries/`
- Qdrant filtering: `https://qdrant.tech/documentation/search/filtering/`
- PostgreSQL row security: `https://www.postgresql.org/docs/current/ddl-rowsecurity.html`
- MinIO object versioning: `https://docs.min.io/aistor/administration/objects-and-versioning/versioning/`
- OWASP prompt injection guidance: `https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html`

Expected: the chapter can accurately state that Qdrant supports filtered hybrid and multi-stage queries, PostgreSQL supports row security policies, MinIO supports object versioning, and retrieved documents must be treated as untrusted content.

- [ ] **Step 4: Create the full chapter skeleton**

Use `apply_patch` to create the target file with:

- `# BridgeAI-Agent Architecture White Paper`
- `# 第六章 RAG 行业知识库设计`
- a document information table with V1.0, formal status, local-first deployment, PostgreSQL, Qdrant, MinIO, and compilation date 2026-07-29;
- sections 6.1 through 6.27 exactly as approved in the design;
- `参考资料` and `修订记录` at the end.

- [ ] **Step 5: Verify the skeleton**

Run:

```bash
rg -n '^#{1,3} ' docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md
```

Expected: sections 6.1 through 6.27 appear once, in numeric order, followed by references and revision history.

---

### Task 2: Write the positioning, boundary, scenarios, principles, and high-level architecture

**Files:**
- Modify: `docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md`

**Interfaces:**
- Consumes: Chapter 2's five-layer architecture, Chapter 3's Agent boundary, Chapter 4's Tool protocol, and Chapter 5's Workflow persistence boundary.
- Produces: sections 6.1-6.8, which define the scope and terminology used by all later sections.

- [ ] **Step 1: Write sections 6.1-6.4**

Cover:

- the chapter's purpose and deliverables;
- RAG as citable external knowledge rather than chat history, business data, or Workflow state;
- a responsibility matrix for Agent, Workflow, RAG Service, RAG Tool, PostgreSQL, Qdrant, MinIO, and human reviewer;
- five first-phase scenarios: disease explanation, standard-clause retrieval, treatment suggestion support, historical-case retrieval, and report citation support.

- [ ] **Step 2: Write section 6.5 design principles**

Define evidence first, authority first, permission before retrieval, structure-aware processing, version immutability, retrieval before generation, abstention under insufficient evidence, model replaceability, local-first processing, and full traceability.

- [ ] **Step 3: Write section 6.6 overall architecture**

Include one text architecture diagram that shows source ingestion, processing, storage, retrieval, evidence packaging, RAG Tool, Agent/Workflow, and human review. Explain the online query path separately from the offline ingestion path.

- [ ] **Step 4: Write sections 6.7-6.8 knowledge classification and source admission**

Define knowledge domains, source authority levels, required metadata, admission checks, publication states, and rejection conditions. Include standard documents, project documents, inspection records, historical cases, domain dictionaries, and equipment/model manuals.

- [ ] **Step 5: Check scope and terminology**

Run:

```bash
rg -n "智慧工地|BridgeAI-Site|RAG.*Memory|Memory.*RAG|Checkpoint" docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md
```

Expected: no Smart Construction scope appears; every RAG/Memory and RAG/Checkpoint comparison preserves the approved responsibility boundary.

- [ ] **Step 6: Commit the first coherent section set**

```bash
git add -- docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md
git commit -m "docs: draft chapter 6 RAG architecture"
```

Expected: the commit contains only the new Chapter 6 file.

---

### Task 3: Write the ingestion, parsing, chunking, embedding, and storage design

**Files:**
- Modify: `docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md`

**Interfaces:**
- Consumes: source classes and admission rules from sections 6.7-6.8.
- Produces: sections 6.9-6.13 and the stable metadata fields consumed by retrieval and citation sections.

- [ ] **Step 1: Write section 6.9 knowledge-ingestion pipeline**

Define the state sequence `registered → parsing → validating → indexing → review_pending → published`, plus `rejected`, `failed`, `superseded`, and `archived`. Explain idempotency by content hash, parser version, embedding model version, and index version.

- [ ] **Step 2: Write section 6.10 parsing, OCR, and structure recovery**

Cover PDF, DOCX, XLSX, HTML, image scans, tables, captions, headers, footers, page coordinates, OCR confidence, manual correction, and preservation of page and clause locators. Make clear that low-quality parsing blocks publication.

- [ ] **Step 3: Write section 6.11 chunking and metadata**

Define structure-first chunks bounded by document, chapter, section, clause, table, or figure rather than fixed-size-only splitting. Include a compact `KnowledgeChunkMetadata` Pydantic example with identifiers, scope, authority, effective dates, page, section, ACL, parser version, and embedding version.

- [ ] **Step 4: Write section 6.12 embedding and indexing**

Define separate dense and sparse representations, Chinese engineering vocabulary evaluation, dimension and model-version isolation, batch indexing, index aliases, re-embedding, and local inference through the Model Gateway. Do not mandate a model name without a measured project evaluation.

- [ ] **Step 5: Write section 6.13 storage responsibilities**

Include a responsibility table for PostgreSQL, Qdrant, MinIO, Redis cache, and Workflow State. Include only representative entities and fields; defer complete DDL to Chapter 8.

- [ ] **Step 6: Validate required metadata coverage**

Run:

```bash
rg -n "document_id|document_version_id|chunk_id|source_type|authority_level|effective_from|effective_to|page_number|section_path|acl_scope|parser_version|embedding_model_version" docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md
```

Expected: every listed field is defined and its purpose is clear.

---

### Task 4: Write retrieval, evidence, Tool contract, Workflow integration, and abstention behavior

**Files:**
- Modify: `docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md`

**Interfaces:**
- Consumes: knowledge metadata and indexes from sections 6.9-6.13 and `knowledge_result_ids: list[str]` from Chapter 5.
- Produces: sections 6.14-6.19, `RAGQueryInput`, `EvidenceItem`, `RAGQueryOutput`, error codes, and Workflow state integration.

- [ ] **Step 1: Write section 6.14 query understanding and hybrid retrieval**

Define query normalization, synonym and engineering-term expansion, asset and disease filters, temporal validity filters, ACL filters, dense and sparse retrieval, Reciprocal Rank Fusion, and configurable candidate counts.

- [ ] **Step 2: Write section 6.15 reranking and context assembly**

Define reranking, authority weighting, duplicate collapse, adjacent-chunk expansion, source diversity, token budgeting, and the rule that retrieval scores are ranking signals rather than confidence probabilities.

- [ ] **Step 3: Write section 6.16 citation and conflict handling**

Define an `EvidenceItem` example containing source identity, version, locator, excerpt, retrieval method, retrieval score, rerank score, applicability, and access scope. Define exact handling for outdated, superseded, conflicting, and insufficient evidence.

- [ ] **Step 4: Write section 6.17 RAG Tool protocol**

Define compact Pydantic examples for `RAGQueryInput` and `RAGQueryOutput`, consistent with Chapter 4's `ToolContext` and `ToolResult`. Include error codes for permission denial, no evidence, version conflict, parse-quality failure, index unavailable, timeout, and citation-validation failure.

- [ ] **Step 5: Write section 6.18 Agent and Workflow integration**

Show the sequence `Agent decision → RAG Tool → retrieval service → evidence result → Workflow state reference → report or review node`. Store only result identifiers and summaries in Workflow State; persist raw results independently.

- [ ] **Step 6: Write section 6.19 constrained generation and abstention**

Require answers to distinguish source facts, model synthesis, uncertainty, conflicts, and reviewer actions. Define deterministic abstention conditions and prohibit a RAG response from directly triggering formal ratings, treatment decisions, report sign-off, or equipment control.

- [ ] **Step 7: Validate interface consistency**

Run:

```bash
rg -n "class RAGQueryInput|class EvidenceItem|class RAGQueryOutput|knowledge_result_ids|ToolContext|ToolResult|权限不足|证据不足|引用校验" docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md
```

Expected: all three contracts, Tool SDK integration points, state reference, and core failure semantics are present.

- [ ] **Step 8: Commit the implementable RAG pipeline**

```bash
git add -- docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md
git commit -m "docs: define chapter 6 RAG pipeline and contracts"
```

Expected: the commit contains only the updated Chapter 6 file.

---

### Task 5: Write lifecycle, security, performance, evaluation, operations, rollout, and decisions

**Files:**
- Modify: `docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md`

**Interfaces:**
- Consumes: all contracts and flow definitions from sections 6.1-6.19.
- Produces: sections 6.20-6.27, references, revision record, and complete acceptance criteria.

- [ ] **Step 1: Write section 6.20 knowledge lifecycle**

Define draft, review, publication, supersession, archival, reprocessing, re-embedding, index migration, rollback, deletion markers, retention, and reproducibility of historical answers.

- [ ] **Step 2: Write section 6.21 permissions and security**

Define organization, project, role, source, and sensitivity scopes; permission-before-retrieval; PostgreSQL row policies as defense in depth; Qdrant payload filters; signed object access; encryption; audit; and indirect prompt-injection controls.

- [ ] **Step 3: Write section 6.22 cache, performance, and resource control**

Define safe cache keys including tenant, project, ACL version, query hash, knowledge version, retrieval configuration, and model version. Define invalidation conditions, concurrency limits, timeouts, graceful degradation, and separate limits for embedding, reranking, and generation.

- [ ] **Step 4: Write section 6.23 evaluation**

Define a bridge-and-road gold query set and metrics for Recall@K, MRR or nDCG, citation precision, citation coverage, faithfulness, abstention accuracy, ACL leakage rate, version correctness, latency percentiles, and human acceptance. Separate retrieval, generation, end-to-end, security, and regression evaluation.

- [ ] **Step 5: Write section 6.24 observability and recovery**

Define trace identifiers, query and filter summaries, knowledge and model versions, candidate counts, latency breakdown, citation-validation results, cache outcome, reviewer outcome, retry policy, index unavailability handling, and audit retention.

- [ ] **Step 6: Write sections 6.25-6.27**

Set the first phase to a single local knowledge service, three verified engineering standards, one project document set, one historical case set, five target scenarios, one RAG Tool, one bridge or road inspection Workflow integration, an evaluation set, and an operator publication process. Add ADRs for the three-store split, hybrid retrieval, immutable knowledge versions, evidence-first answers, and human review. Close with the chapter conclusion.

- [ ] **Step 7: Add references and revision record**

List the official sources from Task 1 with readable titles and direct URLs. Add a V1.0 revision record dated 2026-07-29 that describes the initial formal RAG knowledge-base design.

- [ ] **Step 8: Verify section completeness**

Run:

```bash
for number in $(seq 1 27); do rg -q "^## 6\.${number} " docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md || echo "missing 6.${number}"; done
```

Expected: no output.

---

### Task 6: Perform final consistency, evidence, and Markdown quality verification

**Files:**
- Modify if needed: `docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md`
- Read: `docs/superpowers/specs/2026-07-29-chapter-6-rag-design.md`
- Read: `docs/md/BridgeAI-Agent-第三章-Agent总体设计-V1.0.md`
- Read: `docs/md/BridgeAI-Agent-第四章-Tool-SDK设计规范-V1.0.md`
- Read: `docs/md/BridgeAI-Agent-第五章-Workflow与任务编排系统设计-V1.0.md`

**Interfaces:**
- Consumes: the complete Chapter 6 draft.
- Produces: a V1.0 chapter that passes structural, source, boundary, and repository-scope checks.

- [ ] **Step 1: Scan for incomplete or ambiguous content**

Run:

```bash
rg -n "待补充|待确认|占位符|以后再说|视情况处理|适当处理|相关内容" docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md
```

Expected: no placeholder language; any occurrence of “相关内容” must be a precise source description rather than an omitted requirement.

- [ ] **Step 2: Validate Markdown fences and headings**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

path = Path("docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md")
text = path.read_text(encoding="utf-8")
fences = sum(1 for line in text.splitlines() if line.startswith("```"))
assert fences % 2 == 0, f"unbalanced code fences: {fences}"
headings = [line for line in text.splitlines() if line.startswith("## 6.")]
expected = [f"## 6.{i} " for i in range(1, 28)]
for prefix in expected:
    assert sum(line.startswith(prefix) for line in headings) == 1, prefix
print(f"balanced_fences={fences}; numbered_sections={len(headings)}")
PY
```

Expected: `numbered_sections=27` and an even fence count.

- [ ] **Step 3: Validate architecture boundaries**

Run:

```bash
rg -n "RAG|Memory|Workflow State|Checkpoint|PostgreSQL|Qdrant|MinIO|人工复核" docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md
```

Expected: RAG, Memory, Workflow state, stores, and human-review responsibilities remain distinct throughout the chapter.

- [ ] **Step 4: Validate citations and official URLs**

Run:

```bash
rg -n "https://(jtst\.mot\.gov\.cn|xxgk\.mot\.gov\.cn|qdrant\.tech|www\.postgresql\.org|docs\.min\.io|cheatsheetseries\.owasp\.org)" docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md
```

Expected: direct official links exist for the engineering standards, retrieval engine, relational security, object versioning, and prompt-injection guidance used in the chapter.

- [ ] **Step 5: Check repository scope and whitespace**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only the Chapter 6 file is staged for the final chapter commit, while the user's pre-existing changes remain unstaged and untouched.

- [ ] **Step 6: Commit the verified chapter**

```bash
git add -- docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md
git diff --cached --check
git commit -m "docs: complete chapter 6 RAG knowledge base design"
```

Expected: the final commit contains only `docs/md/BridgeAI-Agent-第六章-RAG行业知识库设计-V1.0.md`.
