<script setup lang="ts">
import { computed } from 'vue'

import type { TaskRunRecord, WorkflowStep } from '../types'

const props = defineProps<{ run: TaskRunRecord | null }>()

const workflowSteps = computed(() => props.run?.workflow.history ?? [])
const modelResult = computed(() => {
  const understanding = workflowSteps.value.find((step) => step.step_name === 'task_understanding')
  return asRecord(understanding?.output.model_result)
})

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : null
}

function stepKey(step: WorkflowStep, index: number): string {
  return `${index}-${step.step_name}`
}
</script>

<template>
  <p v-if="!run" class="empty-state">请选择一条执行历史，查看当时保存的模型、Workflow 与 Tool 快照。</p>
  <div v-else class="run-detail">
    <div class="detail-meta">
      <span>第 {{ run.run_number }} 次 · {{ run.status }}</span>
      <span>{{ run.agent_model.model_id ?? '未记录模型' }}</span>
    </div>

    <p v-if="run.error_message" class="error-text">{{ run.error_message }}</p>

    <section class="snapshot model-snapshot">
      <p class="label">Agent Model</p>
      <p v-if="typeof modelResult?.content === 'string'" class="model-content">
        {{ modelResult.content }}
      </p>
      <p v-else class="muted">本次执行没有任务理解文本。</p>
      <code v-if="modelResult?.usage">usage: {{ JSON.stringify(modelResult.usage) }}</code>
      <code>profile: {{ JSON.stringify(run.agent_model) }}</code>
    </section>

    <section class="snapshot">
      <p class="label">Workflow</p>
      <ol v-if="workflowSteps.length" class="timeline">
        <li v-for="(step, index) in workflowSteps" :key="stepKey(step, index)">
          <strong>{{ step.step_name }}</strong>
          <code>{{ JSON.stringify(step.output) }}</code>
        </li>
      </ol>
      <p v-else class="muted">没有 Workflow 快照。</p>
    </section>

    <section class="snapshot">
      <p class="label">Tool Results</p>
      <ol v-if="run.tool_results.length" class="timeline">
        <li v-for="(tool, index) in run.tool_results" :key="`${index}-${tool.tool_id ?? 'tool'}`">
          <strong>{{ tool.tool_id ?? 'unknown_tool' }} · {{ tool.ok ? 'success' : 'failed' }}</strong>
          <code>{{ JSON.stringify(tool) }}</code>
        </li>
      </ol>
      <p v-else class="muted">没有 Tool 快照。</p>
    </section>
  </div>
</template>

<style scoped>
.run-detail {
  display: grid;
  gap: 14px;
}

.detail-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: #526058;
  font-size: 0.88rem;
  font-weight: 700;
}

.snapshot {
  min-width: 0;
  border-radius: 12px;
  padding: 16px;
  background: #f7faf5;
}

.model-snapshot {
  background: #edf4ee;
}

.label {
  margin: 0 0 9px;
  color: #52715f;
  font-size: 0.76rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.model-content {
  margin: 0 0 12px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.timeline {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.timeline li,
.snapshot code {
  display: grid;
  gap: 7px;
  min-width: 0;
}

.timeline li {
  border-top: 1px solid rgba(23, 32, 26, 0.08);
  padding-top: 10px;
}

.timeline li:first-child {
  border-top: 0;
  padding-top: 0;
}

code {
  margin-top: 7px;
  overflow-wrap: anywhere;
  color: #47534c;
  white-space: pre-wrap;
}

.muted,
.empty-state {
  margin: 0;
  color: #66716a;
}

.error-text {
  margin: 0;
  border-radius: 10px;
  padding: 12px;
  color: #8a2f2f;
  background: #f8e7e5;
  font-weight: 700;
  overflow-wrap: anywhere;
}

@media (max-width: 720px) {
  .detail-meta {
    flex-direction: column;
  }
}
</style>
