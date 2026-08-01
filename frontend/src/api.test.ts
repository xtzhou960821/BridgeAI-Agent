import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ApiError,
  createTask,
  getTask,
  listTaskRuns,
  listTasks,
  loadHealth,
  runTask,
} from './api'
import type { TaskCreateInput } from './types'

const input: TaskCreateInput = {
  title: '桥梁巡检',
  task_type: 'bridge_inspection',
  objective: '检查无人机影像',
  artifact_ids: ['art_001'],
}

describe('persistent task API', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('creates a task with JSON and an idempotency key', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(response({ task_id: 'task_001' }, 201))

    await createTask(input, 'create-001')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/tasks',
      expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': 'create-001',
        },
        body: JSON.stringify(input),
      }),
    )
  })

  it('loads health, task records, task detail, a new run, and run history', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const path = String(url)
      if (path.endsWith('/health')) return response({ status: 'ready' })
      if (path.endsWith('/tasks/task_001/runs')) return response({ items: [] })
      if (path.endsWith('/tasks/task_001')) return response({ task_id: 'task_001' })
      return response({ items: [] })
    })

    await loadHealth()
    await listTasks()
    await getTask('task_001')
    await runTask('task_001')
    await listTaskRuns('task_001')

    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      'http://127.0.0.1:8000/api/v1/health',
      'http://127.0.0.1:8000/api/v1/tasks',
      'http://127.0.0.1:8000/api/v1/tasks/task_001',
      'http://127.0.0.1:8000/api/v1/tasks/task_001/runs',
      'http://127.0.0.1:8000/api/v1/tasks/task_001/runs',
    ])
    expect(fetchMock.mock.calls[3]?.[1]).toEqual({ method: 'POST' })
  })

  it('parses a structured backend detail into ApiError', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      response(
        {
          detail: {
            code: 'TASK_EXECUTION_FAILED',
            message: '任务执行失败，可在执行历史中查看失败记录。',
            run_id: 'run_failed',
          },
        },
        502,
      ),
    )

    const failure = await runTask('task_001').catch((error: unknown) => error)

    expect(failure).toBeInstanceOf(ApiError)
    expect(failure).toMatchObject({
      status: 502,
      code: 'TASK_EXECUTION_FAILED',
      message: '任务执行失败，可在执行历史中查看失败记录。',
      runId: 'run_failed',
    })
  })
})

function response(payload: object, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}
