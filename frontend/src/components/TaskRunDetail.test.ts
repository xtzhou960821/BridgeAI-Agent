import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TaskRunDetail from './TaskRunDetail.vue'
import type { ArtifactRecord, TaskRunRecord } from '../types'

const artifact: ArtifactRecord = {
  artifact_id: 'art_001',
  original_filename: 'bridge-inspection.jpg',
  sha256: 'a'.repeat(64),
  size_bytes: 1_572_864,
  mime_type: 'image/jpeg',
  width_px: 1920,
  height_px: 1080,
  status: 'ready',
  content_url: '/api/v1/artifacts/art_001/content',
  created_at: '2026-08-01T01:00:00+00:00',
}

const run: TaskRunRecord = {
  run_id: 'run_001',
  task_id: 'task_001',
  run_number: 1,
  status: 'completed',
  workflow_runtime: 'langgraph',
  checkpoint_thread_id: 'run_001',
  agent_model: {
    model_id: 'Vontra-DeepSeek-V4-Flash-0731-MXFP4-MLX',
    runtime: 'openai-compatible',
    is_stub: false,
  },
  workflow: {
    current_step: 'completed',
    history: [
      {
        step_name: 'task_understanding',
        output: { model_result: { content: '巡检任务理解结果' } },
      },
    ],
  },
  tool_results: [
    {
      tool_id: 'image_quality_check',
      ok: true,
      output: { quality_status: 'pass' },
    },
  ],
  error_message: null,
  started_at: '2026-08-01T01:00:00+00:00',
  completed_at: '2026-08-01T01:05:00+00:00',
}

describe('TaskRunDetail', () => {
  it('shows LangGraph runtime, its persisted checkpoint thread, and snapshots', () => {
    const wrapper = mount(TaskRunDetail, {
      props: { run, artifact: null, artifactLoading: false, artifactError: '' },
    })

    expect(wrapper.text()).toContain('LangGraph')
    expect(wrapper.text()).toContain('run_001')
    expect(wrapper.text()).toContain('task_understanding')
    expect(wrapper.text()).toContain('image_quality_check')
  })

  it('marks a missing checkpoint thread as unrecorded', () => {
    const wrapper = mount(TaskRunDetail, {
      props: {
        run: { ...run, checkpoint_thread_id: null },
        artifact: null,
        artifactLoading: false,
        artifactError: '',
      },
    })

    expect(wrapper.text()).toContain('未记录')
  })

  it.each([
    ['pass', '质量通过'],
    ['warn', '需要注意'],
    ['fail', '质量不合格'],
  ] as const)('renders the %s quality badge', (qualityStatus, expectedLabel) => {
    const wrapper = mount(TaskRunDetail, {
      props: {
        run: qualityRun(qualityStatus),
        artifact,
        artifactLoading: false,
        artifactError: '',
      },
    })

    expect(wrapper.text()).toContain(expectedLabel)
  })

  it('renders persisted artifact preview and explainable quality evidence', () => {
    const wrapper = mount(TaskRunDetail, {
      props: {
        run: qualityRun('warn'),
        artifact,
        artifactLoading: false,
        artifactError: '',
      },
    })

    expect(wrapper.get('img').attributes('alt')).toBe('bridge-inspection.jpg 预览')
    expect(wrapper.text()).toContain('1920 × 1080 px')
    expect(wrapper.text()).toContain('分辨率')
    expect(wrapper.text()).toContain('曝光')
    expect(wrapper.text()).toContain('暗部裁剪')
    expect(wrapper.text()).toContain('亮部裁剪')
    expect(wrapper.text()).toContain('清晰度')
    expect(wrapper.text()).toContain('128')
    expect(wrapper.text()).toContain('warn_below')
    expect(wrapper.text()).toContain('清晰度低于 5')
    expect(wrapper.text()).toContain('分析器 0.1.0')
    expect(wrapper.get('details').text()).toContain('quality_status')
  })

  it('renders a failed quality finding without calling the run a system failure', () => {
    const wrapper = mount(TaskRunDetail, {
      props: {
        run: qualityRun('fail', ['图像整体偏暗']),
        artifact,
        artifactLoading: false,
        artifactError: '',
      },
    })

    expect(wrapper.text()).toContain('质量不合格')
    expect(wrapper.text()).toContain('图像整体偏暗')
    expect(wrapper.text()).toContain('分析器 0.1.0')
    expect(wrapper.text()).not.toContain('任务执行失败')
  })

  it('keeps a missing artifact as display state and preserves old tool snapshots', () => {
    const wrapper = mount(TaskRunDetail, {
      props: {
        run,
        artifact: null,
        artifactLoading: false,
        artifactError: '请求失败（404）',
      },
    })

    expect(wrapper.text()).toContain('历史任务未关联真实图片')
    expect(wrapper.text()).toContain('image_quality_check')
    expect(wrapper.text()).toContain('quality_status')
    expect(wrapper.text()).not.toContain('质量通过')
  })

  it.each([
    [
      'empty quality containers',
      (output: Record<string, unknown>) => {
        output.metrics = {}
        output.thresholds = {}
        output.checks = {}
      },
    ],
    [
      'missing row metrics, threshold group, and check',
      (output: Record<string, unknown>) => {
        delete (output.metrics as Record<string, number>).sharpness_rms
        delete (output.thresholds as Record<string, Record<string, number>>).bright_clipping
        delete (output.checks as Record<string, string>).exposure
      },
    ],
    [
      'a non-finite metric',
      (output: Record<string, unknown>) => {
        ;(output.metrics as Record<string, number>).mean_luminance = Number.NaN
      },
    ],
  ])('falls back to the legacy tool snapshot for %s', (_caseName, corrupt) => {
    const malformedRun = qualityRun('pass')
    const output = malformedRun.tool_results[0]?.output as Record<string, unknown>
    corrupt(output)

    const wrapper = mount(TaskRunDetail, {
      props: {
        run: malformedRun,
        artifact,
        artifactLoading: false,
        artifactError: '',
      },
    })

    expect(wrapper.text()).toContain('image_quality_check')
    expect(wrapper.text()).toContain('quality_status')
    expect(wrapper.find('.quality-snapshot').exists()).toBe(false)
    expect(wrapper.find('details').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('质量通过')
  })
})

function qualityRun(
  qualityStatus: 'pass' | 'warn' | 'fail',
  reasons = ['清晰度低于 5'],
): TaskRunRecord {
  return {
    ...run,
    tool_results: [
      {
        tool_id: 'image_quality_check',
        ok: true,
        output: {
          artifact_id: artifact.artifact_id,
          quality_status: qualityStatus,
          analyzer_version: '0.1.0',
          metrics: {
            short_side_px: 1080,
            total_pixels: 2_073_600,
            mean_luminance: 128,
            dark_clip_ratio: 0.01,
            bright_clip_ratio: 0.02,
            sharpness_rms: 4.5,
          },
          thresholds: {
            resolution: { min_short_side_px: 720, min_total_pixels: 1_000_000 },
            exposure: { fail_low: 20, warn_low: 40, warn_high: 215, fail_high: 235 },
            dark_clipping: { pixel_max: 10, warn_ratio: 0.5, fail_ratio: 0.8 },
            bright_clipping: { pixel_min: 245, warn_ratio: 0.5, fail_ratio: 0.8 },
            sharpness: { fail_below: 2, warn_below: 5 },
          },
          checks: {
            resolution: 'pass',
            exposure: qualityStatus,
            dark_clipping: 'pass',
            bright_clipping: 'pass',
            sharpness: qualityStatus,
          },
          reasons,
        },
      },
    ],
  }
}
