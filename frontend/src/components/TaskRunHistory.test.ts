import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TaskRunHistory from './TaskRunHistory.vue'
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
    history: [],
  },
  tool_results: [],
  error_message: null,
  started_at: '2026-08-01T01:00:00+00:00',
  completed_at: '2026-08-01T01:05:00+00:00',
}

describe('TaskRunHistory', () => {
  it('shows the persisted LangGraph runtime and checkpoint thread when selecting a run', async () => {
    const wrapper = mount(TaskRunHistory, {
      props: { runs: [run], selectedRunId: null, loading: false },
    })

    expect(wrapper.text()).toContain('LangGraph')
    expect(wrapper.text()).toContain('run_001')
    await wrapper.get('button[data-run-id="run_001"]').trigger('click')
    expect(wrapper.emitted('select')).toEqual([['run_001']])
  })
})
