import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App.vue'
import type { HealthPayload, TaskRecord, TaskRunRecord } from './types'

const api = vi.hoisted(() => ({
  createTask: vi.fn(),
  getTask: vi.fn(),
  listTaskRuns: vi.fn(),
  listTasks: vi.fn(),
  loadHealth: vi.fn(),
  runTask: vi.fn(),
}))

vi.mock('./api', () => api)

const health: HealthPayload = {
  service: 'bridgeai-api',
  version: '0.2.0',
  environment: 'local_dev',
  status: 'ready',
  components: {
    database: 'ready',
    model_gateway: 'configured',
    tool_registry: 'ready',
    workflow: 'ready',
  },
}

const taskOne = task('task_001', '桥梁无人机影像质量检查', 'completed')
const taskTwo = task('task_002', '桥面病害检查', 'pending')
const runOne = run('run_001', 1, '第一次任务理解')
const runTwo = run('run_002', 2, '第二次任务理解')
const newRun = run('run_003', 1, '新任务理解', 'task_002')

describe('persistent task workbench', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(globalThis.crypto, 'randomUUID').mockReturnValue(
      'create-001' as `${string}-${string}-${string}-${string}-${string}`,
    )
    api.loadHealth.mockResolvedValue(health)
    api.listTasks
      .mockResolvedValueOnce({ items: [taskOne] })
      .mockResolvedValue({ items: [{ ...taskTwo, status: 'completed' }, taskOne] })
    let taskTwoHistoryLoads = 0
    api.listTaskRuns.mockImplementation(async (taskId: string) => {
      if (taskId === 'task_001') return { items: [runTwo, runOne] }
      taskTwoHistoryLoads += 1
      return { items: taskTwoHistoryLoads === 1 ? [] : [newRun] }
    })
    api.createTask.mockResolvedValue(taskTwo)
    api.runTask.mockResolvedValue(newRun)
  })

  it('restores, creates, runs, and switches persisted task history', async () => {
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('桥梁无人机影像质量检查')
    expect(wrapper.text()).toContain('第二次任务理解')
    expect(api.listTaskRuns).toHaveBeenCalledWith('task_001')

    await wrapper.get('[data-run-id="run_001"]').trigger('click')
    expect(wrapper.text()).toContain('第一次任务理解')
    expect(wrapper.text()).not.toContain('第二次任务理解')
    expect(api.runTask).not.toHaveBeenCalled()

    await wrapper.get('input[name="title"]').setValue('桥面病害检查')
    await wrapper.get('textarea[name="objective"]').setValue('检查桥面裂缝')
    await wrapper.get('textarea[name="artifact_ids"]').setValue('art_002')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(api.createTask).toHaveBeenCalledWith(
      {
        title: '桥面病害检查',
        task_type: 'bridge_inspection',
        objective: '检查桥面裂缝',
        artifact_ids: ['art_002'],
      },
      'create-001',
    )
    expect(wrapper.get('[data-task-id="task_002"]').attributes('aria-current')).toBe('true')

    await wrapper.get('[data-run-task-id="task_002"]').trigger('click')
    await flushPromises()

    expect(api.runTask).toHaveBeenCalledWith('task_002')
    expect(api.listTasks).toHaveBeenCalledTimes(2)
    expect(api.listTaskRuns).toHaveBeenLastCalledWith('task_002')
    expect(wrapper.text()).toContain('新任务理解')
  })

  it('explains how to initialize LangGraph checkpoints when the tables are not ready', async () => {
    api.loadHealth.mockResolvedValue({
      ...health,
      components: { ...health.components, langgraph_checkpointer: 'not_initialized' },
    })

    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('LangGraph 检查点表尚未初始化')
  })

  it('explains how to repair unavailable LangGraph checkpoint storage', async () => {
    api.loadHealth.mockResolvedValue({
      ...health,
      components: { ...health.components, langgraph_checkpointer: 'unavailable' },
    })

    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('LangGraph 检查点存储不可用，请检查 PostgreSQL 连接。')
  })
})

function task(taskId: string, title: string, status: string): TaskRecord {
  return {
    task_id: taskId,
    title,
    task_type: 'bridge_inspection',
    objective: title,
    artifact_ids: ['art_001'],
    status,
    created_at: '2026-08-01T01:00:00+00:00',
    updated_at: '2026-08-01T01:05:00+00:00',
  }
}

function run(
  runId: string,
  runNumber: number,
  content: string,
  taskId = 'task_001',
): TaskRunRecord {
  return {
    run_id: runId,
    task_id: taskId,
    run_number: runNumber,
    status: 'completed',
    workflow_runtime: 'langgraph',
    checkpoint_thread_id: runId,
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
          output: {
            model_result: {
              content,
              usage: { total_tokens: runNumber * 100 },
            },
          },
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
    started_at: `2026-08-01T01:0${runNumber}:00+00:00`,
    completed_at: `2026-08-01T01:0${runNumber}:05+00:00`,
  }
}
