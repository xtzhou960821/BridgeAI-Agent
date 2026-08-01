<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  createTask,
  listTaskRuns,
  listTasks,
  loadHealth,
  runTask as executeTask,
} from './api'
import TaskCreateForm from './components/TaskCreateForm.vue'
import TaskList from './components/TaskList.vue'
import TaskRunDetail from './components/TaskRunDetail.vue'
import TaskRunHistory from './components/TaskRunHistory.vue'
import type { HealthPayload, TaskCreateInput, TaskRecord, TaskRunRecord } from './types'

const health = ref<HealthPayload | null>(null)
const tasks = ref<TaskRecord[]>([])
const runs = ref<TaskRunRecord[]>([])
const selectedTaskId = ref<string | null>(null)
const selectedRunId = ref<string | null>(null)
const isCreating = ref(false)
const runningTaskId = ref<string | null>(null)
const isLoadingTasks = ref(false)
const isLoadingRuns = ref(false)

const healthError = ref('')
const taskListError = ref('')
const createError = ref('')
const runError = ref('')

const selectedTask = computed(
  () => tasks.value.find((task) => task.task_id === selectedTaskId.value) ?? null,
)
const selectedRun = computed(
  () => runs.value.find((run) => run.run_id === selectedRunId.value) ?? null,
)
const modelGatewayStatus = computed(() => health.value?.components.model_gateway)
const modelGatewayBadge = computed(() => {
  if (selectedRun.value?.agent_model.is_stub === false) return 'live'
  if (selectedRun.value?.agent_model.is_stub === true) return 'stub'
  if (modelGatewayStatus.value === 'configured') return 'ready'
  if (modelGatewayStatus.value === 'not_configured') return 'missing'
  return 'waiting'
})
const modelGatewayWarning = computed(() =>
  modelGatewayStatus.value === 'not_configured'
    ? '模型网关未配置：请用 .env 启动后端，或临时启用本地演示模式。'
    : '',
)

async function refreshHealth() {
  healthError.value = ''
  try {
    health.value = await loadHealth()
  } catch (error) {
    health.value = null
    healthError.value = messageOf(error, '无法读取后端健康状态')
  }
}

async function refreshTasks(preferredTaskId: string | null = selectedTaskId.value) {
  isLoadingTasks.value = true
  taskListError.value = ''
  try {
    tasks.value = (await listTasks()).items
    const nextTaskId =
      tasks.value.find((task) => task.task_id === preferredTaskId)?.task_id ??
      tasks.value[0]?.task_id ??
      null
    if (nextTaskId) {
      await selectTask(nextTaskId)
    } else {
      selectedTaskId.value = null
      selectedRunId.value = null
      runs.value = []
    }
  } catch (error) {
    taskListError.value = messageOf(error, '无法读取任务列表')
  } finally {
    isLoadingTasks.value = false
  }
}

async function selectTask(taskId: string) {
  selectedTaskId.value = taskId
  selectedRunId.value = null
  runs.value = []
  await refreshRuns(taskId)
}

async function refreshRuns(taskId: string) {
  isLoadingRuns.value = true
  try {
    const loaded = (await listTaskRuns(taskId)).items
    if (selectedTaskId.value !== taskId) return
    runs.value = loaded
    selectedRunId.value = loaded[0]?.run_id ?? null
  } catch (error) {
    if (selectedTaskId.value === taskId) {
      runs.value = []
      selectedRunId.value = null
      runError.value = messageOf(error, '无法读取执行历史')
    }
  } finally {
    if (selectedTaskId.value === taskId) isLoadingRuns.value = false
  }
}

function selectRun(runId: string) {
  selectedRunId.value = runId
}

async function handleCreate(input: TaskCreateInput) {
  createError.value = ''
  isCreating.value = true
  try {
    const created = await createTask(input, crypto.randomUUID())
    tasks.value = [created, ...tasks.value.filter((task) => task.task_id !== created.task_id)]
    await selectTask(created.task_id)
  } catch (error) {
    createError.value = messageOf(error, '创建任务失败')
  } finally {
    isCreating.value = false
  }
}

async function handleRun(taskId: string) {
  runError.value = ''
  runningTaskId.value = taskId
  try {
    await executeTask(taskId)
  } catch (error) {
    runError.value = messageOf(error, '任务执行失败')
  } finally {
    await refreshTasks(taskId)
    runningTaskId.value = null
  }
}

function statusTone(value: string | boolean | undefined) {
  if (
    value === true ||
    value === 'ready' ||
    value === 'configured' ||
    value === 'completed' ||
    value === 'live'
  ) {
    return 'good'
  }
  if (
    value === 'not_configured' ||
    value === 'unavailable' ||
    value === 'missing' ||
    value === 'failed' ||
    value === false
  ) {
    return 'warn'
  }
  return 'neutral'
}

function messageOf(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

onMounted(() => {
  void Promise.all([refreshHealth(), refreshTasks()])
})
</script>

<template>
  <main class="shell">
    <section class="hero">
      <div>
        <p class="eyebrow">BridgeAI-Agent V0.2</p>
        <h1>桥梁与道路巡检 AI Agent 工作台</h1>
        <p>
          任务与每次 Agent 执行快照均持久化到 PostgreSQL；可创建巡检任务、重复执行并回看历史结果。
        </p>
      </div>
      <button class="ghost-button" type="button" @click="refreshHealth">刷新状态</button>
    </section>

    <section class="status-grid" aria-label="服务状态">
      <article class="status-panel">
        <div class="section-head">
          <div>
            <p class="label">Backend</p>
            <h2>后端服务</h2>
          </div>
          <span v-if="health" class="badge" :data-tone="statusTone(health.status)">
            {{ health.status }}
          </span>
        </div>
        <p v-if="healthError" class="error-text">{{ healthError }}</p>
        <dl v-else-if="health" class="meta-list">
          <div>
            <dt>Service</dt>
            <dd>{{ health.service }} · {{ health.version }}</dd>
          </div>
          <div>
            <dt>Environment</dt>
            <dd>{{ health.environment }}</dd>
          </div>
          <div v-for="[name, value] in Object.entries(health.components)" :key="name">
            <dt>{{ name }}</dt>
            <dd><span class="badge" :data-tone="statusTone(value)">{{ value }}</span></dd>
          </div>
        </dl>
        <p v-else class="muted">正在读取后端健康状态...</p>
      </article>

      <article class="status-panel">
        <div class="section-head">
          <div>
            <p class="label">Model Gateway</p>
            <h2>Agent 模型</h2>
          </div>
          <span class="badge" :data-tone="statusTone(modelGatewayBadge)">
            {{ modelGatewayBadge }}
          </span>
        </div>
        <dl class="meta-list">
          <div>
            <dt>Model</dt>
            <dd>{{ selectedRun?.agent_model.model_id ?? 'DeepSeek-V4-Flash-4bit' }}</dd>
          </div>
          <div>
            <dt>Runtime</dt>
            <dd>{{ selectedRun?.agent_model.runtime ?? 'openai-compatible' }}</dd>
          </div>
          <div>
            <dt>Persistence</dt>
            <dd>PostgreSQL · task + run snapshots</dd>
          </div>
        </dl>
        <p v-if="modelGatewayWarning" class="warning-text">{{ modelGatewayWarning }}</p>
      </article>
    </section>

    <section class="panel" aria-labelledby="create-task-title">
      <div class="section-head">
        <div>
          <p class="label">Create</p>
          <h2 id="create-task-title">创建巡检任务</h2>
        </div>
      </div>
      <TaskCreateForm :busy="isCreating" @create="handleCreate" />
      <p v-if="createError" class="error-text">{{ createError }}</p>
    </section>

    <section class="panel" aria-labelledby="task-list-title">
      <div class="section-head">
        <div>
          <p class="label">Tasks</p>
          <h2 id="task-list-title">持久化任务</h2>
        </div>
        <span v-if="selectedTask" class="selection-note">当前：{{ selectedTask.title }}</span>
      </div>
      <TaskList
        :tasks="tasks"
        :selected-task-id="selectedTaskId"
        :loading="isLoadingTasks"
        :running-task-id="runningTaskId"
        @select="selectTask"
        @run="handleRun"
      />
      <p v-if="taskListError" class="error-text">{{ taskListError }}</p>
      <p v-if="runError" class="error-text">{{ runError }}</p>
    </section>

    <section class="history-grid" aria-label="执行历史与结果">
      <article class="panel history-panel">
        <div class="section-head">
          <div>
            <p class="label">History</p>
            <h2>执行历史</h2>
          </div>
          <span class="badge" :data-tone="statusTone(selectedRun?.status)">
            {{ runs.length }} records
          </span>
        </div>
        <TaskRunHistory
          :runs="runs"
          :selected-run-id="selectedRunId"
          :loading="isLoadingRuns"
          @select="selectRun"
        />
      </article>

      <article class="panel detail-panel">
        <div class="section-head">
          <div>
            <p class="label">Snapshot</p>
            <h2>执行结果快照</h2>
          </div>
          <span class="badge" :data-tone="statusTone(selectedRun?.status)">
            {{ selectedRun?.status ?? 'not_selected' }}
          </span>
        </div>
        <TaskRunDetail :run="selectedRun" />
      </article>
    </section>
  </main>
</template>

<style scoped>
:global(body) {
  margin: 0;
}

:global(*) {
  box-sizing: border-box;
}

.shell {
  min-height: 100vh;
  padding: 40px;
  color: #17201a;
  background:
    radial-gradient(circle at top left, rgba(52, 99, 77, 0.14), transparent 28rem),
    linear-gradient(135deg, #f7f4ec 0%, #eef3ec 100%);
  font-family:
    Inter, "PingFang SC", "Microsoft YaHei", system-ui, -apple-system, BlinkMacSystemFont,
    sans-serif;
}

.hero,
.panel,
.status-panel {
  max-width: 1120px;
  margin: 0 auto 20px;
  border: 1px solid rgba(23, 32, 26, 0.1);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 24px 60px rgba(23, 32, 26, 0.08);
}

.hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 32px;
}

.panel,
.status-panel {
  padding: 24px;
}

.status-grid,
.history-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 20px;
  max-width: 1120px;
  margin: 0 auto;
}

.history-grid {
  grid-template-columns: minmax(280px, 0.72fr) minmax(0, 1.28fr);
}

.status-grid .status-panel,
.history-grid .panel {
  margin: 0 0 20px;
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.eyebrow,
.label {
  margin: 0 0 8px;
  color: #52715f;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

h1,
h2,
p {
  margin-top: 0;
}

h1 {
  max-width: 940px;
  margin-bottom: 22px;
  font-size: clamp(2.35rem, 5.2vw, 4.8rem);
  line-height: 1.03;
}

h2 {
  margin-bottom: 0;
  font-size: 1.5rem;
}

.hero p:not(.eyebrow),
.muted {
  color: #46534b;
}

.badge {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  border-radius: 999px;
  padding: 0 10px;
  color: #45524b;
  background: #e7ece7;
  font-size: 0.82rem;
  font-weight: 700;
  white-space: nowrap;
}

.badge[data-tone='good'] {
  color: #215640;
  background: #d8eadc;
}

.badge[data-tone='warn'] {
  color: #72521a;
  background: #f4e4bf;
}

.meta-list {
  display: grid;
  gap: 12px;
  margin: 0;
}

.meta-list div {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid rgba(23, 32, 26, 0.08);
  padding-bottom: 10px;
}

.meta-list div:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}

dt {
  color: #66716a;
  font-weight: 700;
}

dd {
  margin: 0;
  color: #17201a;
  text-align: right;
  word-break: break-word;
}

.ghost-button {
  flex: 0 0 auto;
  min-height: 40px;
  border: 0;
  border-radius: 8px;
  padding: 0 16px;
  color: #244f3c;
  background: #e3eee6;
  font: inherit;
  font-size: 0.95rem;
  font-weight: 700;
  white-space: nowrap;
  cursor: pointer;
}

.ghost-button:focus-visible {
  outline: 3px solid rgba(36, 79, 60, 0.3);
  outline-offset: 2px;
}

.selection-note {
  max-width: 45%;
  color: #526058;
  font-size: 0.88rem;
  text-align: right;
}

.error-text,
.warning-text {
  margin: 12px 0 0;
  font-weight: 700;
}

.error-text {
  color: #8a2f2f;
}

.warning-text {
  color: #72521a;
}

@media (max-width: 800px) {
  .shell {
    padding: 20px;
  }

  .hero,
  .section-head,
  .meta-list div {
    align-items: stretch;
    flex-direction: column;
  }

  .status-grid,
  .history-grid {
    grid-template-columns: 1fr;
  }

  h1 {
    font-size: 2.45rem;
  }

  dd,
  .selection-note {
    max-width: none;
    text-align: left;
  }
}
</style>
