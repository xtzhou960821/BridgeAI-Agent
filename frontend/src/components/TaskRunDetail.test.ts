import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TaskRunDetail from './TaskRunDetail.vue'
import type { TaskRunRecord } from '../types'

const run: TaskRunRecord = {
  run_id: 'run_001',
  task_id: 'task_001',
  run_number: 1,
  status: 'completed',
  workflow_runtime: 'langgraph',
  checkpoint_thread_id: 'run_001',
  agent_model: {
    model_id: 'DeepSeek-V4-Flash-4bit',
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
    const wrapper = mount(TaskRunDetail, { props: { run } })

    expect(wrapper.text()).toContain('LangGraph')
    expect(wrapper.text()).toContain('run_001')
    expect(wrapper.text()).toContain('task_understanding')
    expect(wrapper.text()).toContain('image_quality_check')
  })

  it('marks a missing checkpoint thread as unrecorded', () => {
    const wrapper = mount(TaskRunDetail, {
      props: { run: { ...run, checkpoint_thread_id: null } },
    })

    expect(wrapper.text()).toContain('未记录')
  })
})
