<script setup lang="ts">
import { computed } from 'vue'

import type { TaskRunRecord } from '../types'

const props = defineProps<{
  runs: TaskRunRecord[]
  selectedRunId: string | null
  loading: boolean
}>()

defineEmits<{
  select: [runId: string]
}>()

const orderedRuns = computed(() => [...props.runs].sort((left, right) => right.run_number - left.run_number))

function formatTime(value: string | null): string {
  if (!value) return '未结束'
  const date = new Date(value)
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}
</script>

<template>
  <p v-if="loading" class="muted">正在读取执行历史...</p>
  <p v-else-if="orderedRuns.length === 0" class="empty-state">当前任务还没有执行记录。</p>
  <ol v-else class="run-list">
    <li v-for="run in orderedRuns" :key="run.run_id">
      <button
        type="button"
        :data-run-id="run.run_id"
        :class="{ selected: selectedRunId === run.run_id }"
        :aria-current="selectedRunId === run.run_id ? 'true' : undefined"
        @click="$emit('select', run.run_id)"
      >
        <span class="run-head">
          <strong>第 {{ run.run_number }} 次</strong>
          <em :data-status="run.status">{{ run.status }}</em>
        </span>
        <span>{{ run.agent_model.model_id ?? '未记录模型' }}</span>
        <small>开始：{{ formatTime(run.started_at) }}</small>
        <small>结束：{{ formatTime(run.completed_at) }}</small>
        <small v-if="run.error_message" class="failure">{{ run.error_message }}</small>
      </button>
    </li>
  </ol>
</template>

<style scoped>
.run-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.run-list button {
  display: grid;
  gap: 7px;
  width: 100%;
  border: 1px solid #d5ddd7;
  border-radius: 10px;
  padding: 13px;
  color: #26322b;
  background: #f9fbf8;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.run-list button.selected {
  border-color: #668574;
  background: #eaf2eb;
}

.run-list button:focus-visible {
  outline: 3px solid rgba(36, 79, 60, 0.3);
  outline-offset: 2px;
}

.run-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.run-head em {
  border-radius: 999px;
  padding: 4px 8px;
  color: #45524b;
  background: #e7ece7;
  font-size: 0.75rem;
  font-style: normal;
  font-weight: 800;
}

.run-head em[data-status='completed'] {
  color: #215640;
  background: #d8eadc;
}

.run-head em[data-status='failed'] {
  color: #7d3030;
  background: #f1dada;
}

.run-list span:not(.run-head),
.run-list small,
.muted {
  color: #66716a;
}

.failure {
  color: #8a2f2f !important;
  overflow-wrap: anywhere;
}

.empty-state {
  margin: 0;
  color: #66716a;
}
</style>
