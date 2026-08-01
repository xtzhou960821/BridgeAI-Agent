<script setup lang="ts">
import { computed } from 'vue'

import { artifactContentUrl } from '../api'
import type {
  ArtifactRecord,
  ImageQualityOutput,
  QualityStatus,
  TaskRunRecord,
  ToolResultSnapshot,
  WorkflowStep,
} from '../types'

const props = defineProps<{
  run: TaskRunRecord | null
  artifact: ArtifactRecord | null
  artifactLoading: boolean
  artifactError: string
}>()

const workflowSteps = computed(() => props.run?.workflow.history ?? [])
const modelResult = computed(() => {
  const understanding = workflowSteps.value.find((step) => step.step_name === 'task_understanding')
  return asRecord(understanding?.output.model_result)
})
const qualityTool = computed(() =>
  props.run?.tool_results.find(
    (tool) => tool.tool_id === 'image_quality_check' && tool.ok === true && isImageQualityOutput(tool.output),
  ),
)
const qualityOutput = computed<ImageQualityOutput | null>(() => {
  const output = qualityTool.value?.output
  return isImageQualityOutput(output) ? output : null
})
const qualityRows = computed(() => {
  const output = qualityOutput.value
  if (!output) return []
  return [
    {
      key: 'resolution',
      label: '分辨率',
      status: output.checks.resolution,
      metrics: `短边 ${metric(output, 'short_side_px')} px · 总像素 ${metric(output, 'total_pixels')}`,
    },
    {
      key: 'exposure',
      label: '曝光',
      status: output.checks.exposure,
      metrics: `平均亮度 ${metric(output, 'mean_luminance')}`,
    },
    {
      key: 'dark_clipping',
      label: '暗部裁剪',
      status: output.checks.dark_clipping,
      metrics: `裁剪比例 ${metric(output, 'dark_clip_ratio')}`,
    },
    {
      key: 'bright_clipping',
      label: '亮部裁剪',
      status: output.checks.bright_clipping,
      metrics: `裁剪比例 ${metric(output, 'bright_clip_ratio')}`,
    },
    {
      key: 'sharpness',
      label: '清晰度',
      status: output.checks.sharpness,
      metrics: `RMS ${metric(output, 'sharpness_rms')}`,
    },
  ]
})

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function isQualityStatus(value: unknown): value is QualityStatus {
  return value === 'pass' || value === 'warn' || value === 'fail'
}

function hasExactKeys(record: Record<string, unknown>, expected: readonly string[]): boolean {
  return Object.keys(record).length === expected.length && expected.every((key) => key in record)
}

function hasExactFiniteNumberKeys(
  value: unknown,
  expected: readonly string[],
): value is Record<string, number> {
  const record = asRecord(value)
  return (
    record !== null &&
    hasExactKeys(record, expected) &&
    expected.every((key) => typeof record[key] === 'number' && Number.isFinite(record[key]))
  )
}

function hasExactQualityStatusKeys(value: unknown, expected: readonly string[]): boolean {
  const record = asRecord(value)
  return record !== null && hasExactKeys(record, expected) && expected.every((key) => isQualityStatus(record[key]))
}

function hasExactThresholds(value: unknown): boolean {
  const thresholds = asRecord(value)
  return (
    thresholds !== null &&
    hasExactKeys(thresholds, [
      'resolution',
      'exposure',
      'dark_clipping',
      'bright_clipping',
      'sharpness',
    ]) &&
    hasExactFiniteNumberKeys(thresholds.resolution, ['min_short_side_px', 'min_total_pixels']) &&
    hasExactFiniteNumberKeys(thresholds.exposure, [
      'fail_low',
      'warn_low',
      'warn_high',
      'fail_high',
    ]) &&
    hasExactFiniteNumberKeys(thresholds.dark_clipping, ['pixel_max', 'warn_ratio', 'fail_ratio']) &&
    hasExactFiniteNumberKeys(thresholds.bright_clipping, ['pixel_min', 'warn_ratio', 'fail_ratio']) &&
    hasExactFiniteNumberKeys(thresholds.sharpness, ['fail_below', 'warn_below'])
  )
}

function isImageQualityOutput(value: unknown): value is ImageQualityOutput {
  const record = asRecord(value)
  if (
    record === null ||
    typeof record.artifact_id !== 'string' ||
    record.artifact_id.length === 0 ||
    !isQualityStatus(record.quality_status) ||
    typeof record.analyzer_version !== 'string' ||
    record.analyzer_version.length === 0 ||
    !hasExactFiniteNumberKeys(record.metrics, [
      'short_side_px',
      'total_pixels',
      'mean_luminance',
      'dark_clip_ratio',
      'bright_clip_ratio',
      'sharpness_rms',
    ]) ||
    !hasExactThresholds(record.thresholds) ||
    !hasExactQualityStatusKeys(record.checks, [
      'resolution',
      'exposure',
      'dark_clipping',
      'bright_clipping',
      'sharpness',
    ]) ||
    !Array.isArray(record.reasons) ||
    !record.reasons.every((reason) => typeof reason === 'string')
  ) {
    return false
  }

  return true
}

function metric(output: ImageQualityOutput, key: string): string {
  const value = output.metrics[key]
  return typeof value === 'number' ? String(value) : '未记录'
}

function qualityLabel(status: QualityStatus | undefined): string {
  if (status === 'pass') return '通过'
  if (status === 'warn') return '注意'
  if (status === 'fail') return '不合格'
  return '未记录'
}

function qualitySummary(status: QualityStatus): string {
  if (status === 'pass') return '质量通过'
  if (status === 'warn') return '需要注意'
  return '质量不合格'
}

function stepKey(step: WorkflowStep, index: number): string {
  return `${index}-${step.step_name}`
}

function toolKey(tool: ToolResultSnapshot, index: number): string {
  return `${index}-${tool.tool_id ?? 'tool'}`
}
</script>

<template>
  <p v-if="!run" class="empty-state">请选择一条执行历史，查看当时保存的模型、Workflow 与 Tool 快照。</p>
  <div v-else class="run-detail">
    <div class="detail-meta">
      <span>第 {{ run.run_number }} 次 · {{ run.status }}</span>
      <span>{{ run.agent_model.model_id ?? '未记录模型' }}</span>
    </div>

    <dl class="runtime-meta">
      <div>
        <dt>Workflow Runtime</dt>
        <dd>{{ run.workflow_runtime === 'langgraph' ? 'LangGraph' : 'Legacy' }}</dd>
      </div>
      <div>
        <dt>Checkpoint Thread</dt>
        <dd>{{ run.checkpoint_thread_id ?? '未记录' }}</dd>
      </div>
    </dl>

    <p v-if="run.error_message" class="error-text">{{ run.error_message }}</p>

    <section class="snapshot artifact-snapshot">
      <p class="label">巡检图片</p>
      <p v-if="artifactLoading" class="muted">正在读取关联图片...</p>
      <div v-else-if="artifact" class="artifact-preview">
        <img :src="artifactContentUrl(artifact.artifact_id)" :alt="`${artifact.original_filename} 预览`" />
        <dl class="artifact-meta">
          <div><dt>文件</dt><dd>{{ artifact.original_filename }}</dd></div>
          <div><dt>尺寸</dt><dd>{{ artifact.width_px }} × {{ artifact.height_px }} px</dd></div>
          <div><dt>格式</dt><dd>{{ artifact.mime_type }}</dd></div>
          <div><dt>状态</dt><dd>{{ artifact.status }}</dd></div>
        </dl>
      </div>
      <p v-else class="muted" :title="artifactError || undefined">历史任务未关联真实图片</p>
    </section>

    <section v-if="qualityOutput" class="snapshot quality-snapshot">
      <div class="quality-head">
        <p class="label">图像质量</p>
        <span class="quality-badge" :data-status="qualityOutput.quality_status">
          {{ qualitySummary(qualityOutput.quality_status) }}
        </span>
      </div>
      <p class="analyzer">分析器 {{ qualityOutput.analyzer_version }}</p>
      <dl class="quality-checks">
        <div v-for="row in qualityRows" :key="row.key">
          <dt>
            {{ row.label }}
            <span class="check-status" :data-status="row.status">{{ qualityLabel(row.status) }}</span>
          </dt>
          <dd>指标：{{ row.metrics }}</dd>
          <dd>阈值：{{ JSON.stringify(qualityOutput.thresholds[row.key] ?? {}) }}</dd>
        </div>
      </dl>
      <div class="quality-reasons">
        <strong>结论依据</strong>
        <p v-if="qualityOutput.reasons.length === 0" class="muted">未发现需要说明的质量问题。</p>
        <ul v-else>
          <li v-for="reason in qualityOutput.reasons" :key="reason">{{ reason }}</li>
        </ul>
      </div>
      <details class="audit-details">
        <summary>审计详情</summary>
        <code>{{ JSON.stringify(qualityTool) }}</code>
      </details>
    </section>

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

    <section v-if="!qualityOutput" class="snapshot">
      <p class="label">Tool Results</p>
      <ol v-if="run.tool_results.length" class="timeline">
        <li v-for="(tool, index) in run.tool_results" :key="toolKey(tool, index)">
          <strong>{{ tool.tool_id ?? 'unknown_tool' }} · {{ tool.ok ? 'success' : 'failed' }}</strong>
          <code>{{ JSON.stringify(tool) }}</code>
        </li>
      </ol>
      <p v-else class="muted">没有 Tool 快照。</p>
    </section>
  </div>
</template>

<style scoped>
.run-detail { display: grid; gap: 14px; }
.detail-meta { display: flex; justify-content: space-between; gap: 12px; color: #526058; font-size: 0.88rem; font-weight: 700; }
.runtime-meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 0; }
.runtime-meta div { min-width: 0; border-radius: 10px; padding: 10px 12px; background: #f1f5ef; }
.runtime-meta dt, .artifact-meta dt { color: #66716a; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.05em; text-transform: uppercase; }
.runtime-meta dd { margin: 5px 0 0; overflow-wrap: anywhere; color: #26322b; font-size: 0.9rem; font-weight: 700; }
.snapshot { min-width: 0; border-radius: 12px; padding: 16px; background: #f7faf5; }
.model-snapshot { background: #edf4ee; }
.artifact-snapshot { background: #f2f6f0; }
.quality-snapshot { background: #f4f7f1; }
.label { margin: 0 0 9px; color: #52715f; font-size: 0.76rem; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }
.artifact-preview { display: grid; grid-template-columns: minmax(130px, 190px) minmax(0, 1fr); gap: 14px; align-items: start; }
.artifact-preview img { display: block; width: 100%; max-height: 150px; border-radius: 8px; object-fit: cover; }
.artifact-meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px 12px; margin: 0; }
.artifact-meta dd { margin: 4px 0 0; overflow-wrap: anywhere; color: #26322b; font-size: 0.86rem; font-weight: 700; }
.quality-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.quality-badge, .check-status { display: inline-flex; align-items: center; border-radius: 999px; font-weight: 800; }
.quality-badge { padding: 5px 9px; font-size: 0.8rem; }
.quality-badge[data-status='pass'], .check-status[data-status='pass'] { color: #215640; background: #d8eadc; }
.quality-badge[data-status='warn'], .check-status[data-status='warn'] { color: #76530d; background: #f4e6bf; }
.quality-badge[data-status='fail'], .check-status[data-status='fail'] { color: #7d3030; background: #f1dada; }
.analyzer { margin: 0 0 11px; color: #526058; font-size: 0.86rem; }
.quality-checks { display: grid; gap: 9px; margin: 0; }
.quality-checks > div { border-top: 1px solid rgba(23, 32, 26, 0.08); padding-top: 9px; }
.quality-checks dt { display: flex; align-items: center; justify-content: space-between; gap: 12px; color: #26322b; font-weight: 800; }
.quality-checks dd { margin: 5px 0 0; color: #526058; font-size: 0.84rem; overflow-wrap: anywhere; }
.check-status { padding: 3px 7px; font-size: 0.72rem; }
.quality-reasons { margin-top: 14px; color: #26322b; font-size: 0.88rem; }
.quality-reasons p { margin: 6px 0 0; }
.quality-reasons ul { margin: 6px 0 0; padding-left: 20px; }
.audit-details { margin-top: 14px; color: #47534c; }
.audit-details summary { cursor: pointer; font-weight: 700; }
.audit-details code { display: block; margin-top: 8px; }
.model-content { margin: 0 0 12px; line-height: 1.7; white-space: pre-wrap; }
.timeline { display: grid; gap: 10px; margin: 0; padding: 0; list-style: none; }
.timeline li, .snapshot code { display: grid; gap: 7px; min-width: 0; }
.timeline li { border-top: 1px solid rgba(23, 32, 26, 0.08); padding-top: 10px; }
.timeline li:first-child { border-top: 0; padding-top: 0; }
code { margin-top: 7px; overflow-wrap: anywhere; color: #47534c; white-space: pre-wrap; }
.muted, .empty-state { margin: 0; color: #66716a; }
.error-text { margin: 0; border-radius: 10px; padding: 12px; color: #8a2f2f; background: #f8e7e5; font-weight: 700; overflow-wrap: anywhere; }
@media (max-width: 720px) { .detail-meta { flex-direction: column; } .runtime-meta, .artifact-meta { grid-template-columns: 1fr; } .artifact-preview { grid-template-columns: 1fr; } .artifact-preview img { max-width: 260px; } }
</style>
