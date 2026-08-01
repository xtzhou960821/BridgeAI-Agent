<script setup lang="ts">
import type { TaskRecord } from '../types'

defineProps<{
  tasks: TaskRecord[]
  selectedTaskId: string | null
  loading: boolean
  runningTaskId: string | null
}>()

defineEmits<{
  select: [taskId: string]
  run: [taskId: string]
}>()
</script>

<template>
  <p v-if="loading && tasks.length === 0" class="muted">正在读取 PostgreSQL 中的任务...</p>
  <p v-else-if="tasks.length === 0" class="empty-state">暂无任务，请先创建一个巡检任务。</p>
  <div v-else class="task-list">
    <article
      v-for="task in tasks"
      :key="task.task_id"
      class="task-card"
      :class="{ selected: selectedTaskId === task.task_id }"
      :data-task-id="task.task_id"
      :aria-current="selectedTaskId === task.task_id ? 'true' : undefined"
    >
      <button class="task-select" type="button" @click="$emit('select', task.task_id)">
        <strong>{{ task.title }}</strong>
        <span>{{ task.task_id }} · {{ task.artifact_ids.length }} 个 Artifact · {{ task.task_type }}</span>
      </button>
      <div class="task-actions">
        <span class="status" :data-status="task.status">{{ task.status }}</span>
        <button
          class="run-button"
          type="button"
          :data-run-task-id="task.task_id"
          :disabled="runningTaskId !== null"
          @click="$emit('run', task.task_id)"
        >
          {{ runningTaskId === task.task_id ? '执行中...' : '执行任务' }}
        </button>
      </div>
    </article>
  </div>
</template>

<style scoped>
.task-list {
  display: grid;
  gap: 12px;
}

.task-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  border: 1px solid transparent;
  border-radius: 12px;
  padding: 14px;
  background: #f7faf5;
}

.task-card.selected {
  border-color: #739181;
  background: #edf4ee;
}

.task-select {
  display: grid;
  flex: 1;
  gap: 7px;
  min-width: 0;
  border: 0;
  padding: 3px;
  color: inherit;
  background: transparent;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.task-select strong {
  font-size: 1.05rem;
}

.task-select span,
.muted {
  color: #66716a;
  font-size: 0.9rem;
}

.task-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status {
  border-radius: 999px;
  padding: 6px 10px;
  color: #45524b;
  background: #e7ece7;
  font-size: 0.8rem;
  font-weight: 800;
}

.status[data-status='completed'] {
  color: #215640;
  background: #d8eadc;
}

.status[data-status='failed'] {
  color: #7d3030;
  background: #f1dada;
}

.run-button {
  min-height: 38px;
  border: 0;
  border-radius: 8px;
  padding: 0 14px;
  color: #fff;
  background: #244f3c;
  font: inherit;
  font-size: 0.88rem;
  font-weight: 700;
  cursor: pointer;
}

.run-button:disabled {
  background: #6e8276;
  cursor: not-allowed;
}

.task-select:focus-visible,
.run-button:focus-visible {
  outline: 3px solid rgba(36, 79, 60, 0.3);
  outline-offset: 2px;
}

.empty-state {
  margin: 0;
  border: 1px dashed #bac8be;
  border-radius: 10px;
  padding: 20px;
  color: #526058;
  text-align: center;
}

@media (max-width: 720px) {
  .task-card,
  .task-actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
