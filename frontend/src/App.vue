<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

type HealthPayload = {
  service: string
  version: string
  environment: string
  status: string
  components: Record<string, string>
}

type WorkflowStep = {
  step_name: string
  output: Record<string, unknown>
}

type TaskRunPayload = {
  task_id: string
  status: string
  agent_model: {
    model_id: string
    model_version: string
    alias: string
    provider: string
    runtime: string
    api_base_url: string
    is_stub: boolean
  }
  workflow: {
    current_step: string
    history: WorkflowStep[]
  }
  tool_results: Array<{
    tool_id: string
    ok: boolean
    output: Record<string, unknown>
  }>
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1').replace(
  /\/$/,
  '',
)

const tasks = [
  {
    id: 'task_001',
    title: '桥梁无人机影像质量检查',
    objective: '检查桥梁无人机影像质量',
    taskType: 'bridge_inspection',
    artifactIds: ['art_001'],
  },
]

const health = ref<HealthPayload | null>(null)
const healthError = ref('')
const taskRun = ref<TaskRunPayload | null>(null)
const taskError = ref('')
const isRunning = ref(false)

const selectedTask = tasks[0]

const modelGatewayStatus = computed(() => health.value?.components.model_gateway)

const modelGatewayBadge = computed(() => {
  if (taskRun.value?.agent_model.is_stub === false) {
    return 'live'
  }
  if (taskRun.value?.agent_model.is_stub === true) {
    return 'stub'
  }
  if (modelGatewayStatus.value === 'configured') {
    return 'ready'
  }
  if (modelGatewayStatus.value === 'not_configured') {
    return 'missing'
  }
  return 'waiting'
})

const modelGatewayWarning = computed(() => {
  if (modelGatewayStatus.value !== 'not_configured') {
    return ''
  }
  return '模型网关未配置：请用 .env 启动后端，或临时启用本地演示模式。'
})

const isTaskDisabled = computed(() => isRunning.value || modelGatewayStatus.value === 'not_configured')

const modelResult = computed(() => {
  const firstStep = taskRun.value?.workflow.history.find((step) => step.step_name === 'task_understanding')
  return firstStep?.output.model_result as Record<string, unknown> | undefined
})

async function loadHealth() {
  healthError.value = ''
  try {
    const response = await fetch(`${apiBaseUrl}/health`)
    if (!response.ok) {
      throw new Error(`Health request failed: ${response.status}`)
    }
    health.value = await response.json()
  } catch (error) {
    health.value = null
    healthError.value = error instanceof Error ? error.message : '无法读取后端健康状态'
  }
}

async function runTask() {
  taskError.value = ''
  isRunning.value = true
  try {
    const response = await fetch(`${apiBaseUrl}/tasks/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task_id: selectedTask.id,
        task_type: selectedTask.taskType,
        objective: selectedTask.objective,
        artifact_ids: selectedTask.artifactIds,
      }),
    })
    if (!response.ok) {
      throw new Error(await readTaskRunError(response))
    }
    taskRun.value = await response.json()
  } catch (error) {
    taskError.value = error instanceof Error ? error.message : '任务执行失败'
  } finally {
    isRunning.value = false
  }
}

async function readTaskRunError(response: Response) {
  const fallback = `Task run failed: ${response.status}`
  try {
    const payload = await response.json()
    const detail = payload?.detail
    if (typeof detail === 'string') {
      return detail
    }
    if (detail && typeof detail.message === 'string') {
      return detail.message
    }
  } catch {
    return fallback
  }
  return fallback
}

function statusTone(value: string | boolean | undefined) {
  if (value === true || value === 'ready' || value === 'configured' || value === 'completed' || value === 'live') {
    return 'good'
  }
  if (value === 'not_configured' || value === 'missing' || value === false) {
    return 'warn'
  }
  return 'neutral'
}

onMounted(loadHealth)
</script>

<template>
  <main class="shell">
    <section class="hero">
      <div>
        <p class="eyebrow">BridgeAI-Agent V0.2</p>
        <h1>桥梁与道路巡检 AI Agent 工作台</h1>
        <p>
          当前版本已接入后端健康检查和 oMLX Model Gateway，可在任务理解阶段调用
          DeepSeek-V4-Flash-4bit。
        </p>
      </div>
      <button class="ghost-button" type="button" @click="loadHealth">刷新状态</button>
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
            <dd>
              <span class="badge" :data-tone="statusTone(value)">{{ value }}</span>
            </dd>
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
            <dd>{{ taskRun?.agent_model.model_id ?? 'DeepSeek-V4-Flash-4bit' }}</dd>
          </div>
          <div>
            <dt>Runtime</dt>
            <dd>{{ taskRun?.agent_model.runtime ?? 'openai-compatible' }}</dd>
          </div>
          <div>
            <dt>Base URL</dt>
            <dd>{{ taskRun?.agent_model.api_base_url ?? 'https://omlx.cpolar.cn/v1' }}</dd>
          </div>
        </dl>
      </article>
    </section>

    <section class="panel" aria-labelledby="task-list-title">
      <div class="section-head">
        <div>
          <p class="label">Task</p>
          <h2 id="task-list-title">任务列表</h2>
        </div>
        <button class="primary-button" type="button" :disabled="isTaskDisabled" @click="runTask">
          {{ isRunning ? '执行中...' : '执行示例任务' }}
        </button>
      </div>

      <article v-for="task in tasks" :key="task.id" class="task-card">
        <div>
          <h3>{{ task.title }}</h3>
          <p>{{ task.id }} · {{ task.artifactIds.length }} 个 Artifact · {{ task.taskType }}</p>
        </div>
        <span>{{ taskRun?.status ?? '等待执行' }}</span>
      </article>
      <p v-if="modelGatewayWarning" class="warning-text">{{ modelGatewayWarning }}</p>
      <p v-if="taskError" class="error-text">{{ taskError }}</p>
    </section>

    <section class="panel result-panel" aria-labelledby="task-detail-title">
      <div class="section-head">
        <div>
          <p class="label">Workflow</p>
          <h2 id="task-detail-title">任务理解与执行结果</h2>
        </div>
        <span class="badge" :data-tone="statusTone(taskRun?.workflow.current_step)">
          {{ taskRun?.workflow.current_step ?? 'not_started' }}
        </span>
      </div>

      <div v-if="modelResult" class="model-result">
        <p class="label">DeepSeek 任务理解</p>
        <p>{{ modelResult.content }}</p>
        <small>usage: {{ JSON.stringify(modelResult.usage) }}</small>
      </div>
      <p v-else class="muted">点击“执行示例任务”后，这里会显示 oMLX 返回的任务理解内容。</p>

      <ol v-if="taskRun" class="timeline">
        <li v-for="step in taskRun.workflow.history" :key="step.step_name">
          <span>{{ step.step_name }}</span>
          <code>{{ JSON.stringify(step.output) }}</code>
        </li>
      </ol>
    </section>
  </main>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  box-sizing: border-box;
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
  background: rgba(255, 255, 255, 0.78);
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

.status-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 20px;
  max-width: 1120px;
  margin: 0 auto;
}

.status-grid .status-panel {
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
h3,
p {
  margin-top: 0;
}

h1 {
  max-width: 940px;
  margin-bottom: 22px;
  font-size: clamp(2.4rem, 5.6vw, 5.1rem);
  line-height: 1.03;
}

h2 {
  margin-bottom: 0;
  font-size: 1.55rem;
}

h3 {
  margin-bottom: 10px;
  font-size: 1.15rem;
}

.hero p:not(.eyebrow),
.muted {
  color: #46534b;
}

.task-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 18px;
  border-radius: 12px;
  background: #f7faf5;
}

.task-card span,
.badge {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  color: #315b45;
  background: #ddebe1;
  font-size: 0.84rem;
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

.badge[data-tone='neutral'] {
  color: #45524b;
  background: #e7ece7;
}

.primary-button,
.ghost-button {
  min-height: 40px;
  padding: 0 16px;
  border: 0;
  border-radius: 8px;
  font: inherit;
  font-size: 0.95rem;
  font-weight: 700;
  cursor: pointer;
}

.primary-button {
  color: #ffffff;
  background: #244f3c;
}

.primary-button:disabled {
  color: rgba(255, 255, 255, 0.78);
  background: #6e8276;
  cursor: not-allowed;
}

.ghost-button {
  color: #244f3c;
  background: #e3eee6;
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
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(23, 32, 26, 0.08);
}

.meta-list div:last-child {
  padding-bottom: 0;
  border-bottom: 0;
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

.result-panel {
  margin-bottom: 0;
}

.model-result {
  margin-bottom: 18px;
  padding: 18px;
  border-radius: 12px;
  background: #f7faf5;
}

.model-result p:not(.label) {
  margin-bottom: 12px;
  color: #17201a;
  line-height: 1.7;
  white-space: pre-wrap;
}

.model-result small {
  color: #66716a;
  word-break: break-word;
}

.timeline {
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.timeline li {
  display: grid;
  gap: 8px;
  padding: 14px;
  border-radius: 12px;
  background: rgba(247, 250, 245, 0.8);
}

.timeline span {
  font-weight: 800;
}

code {
  overflow-wrap: anywhere;
  color: #334039;
  white-space: pre-wrap;
}

.error-text {
  margin-bottom: 0;
  color: #8a2f2f;
  font-weight: 700;
}

.warning-text {
  margin: 12px 0 0;
  color: #72521a;
  font-weight: 700;
}

@media (max-width: 800px) {
  .shell {
    padding: 20px;
  }

  .hero,
  .section-head,
  .task-card,
  .meta-list div {
    flex-direction: column;
    align-items: stretch;
  }

  .status-grid {
    grid-template-columns: 1fr;
  }

  h1 {
    font-size: 2.45rem;
  }

  dd {
    text-align: left;
  }
}
</style>
