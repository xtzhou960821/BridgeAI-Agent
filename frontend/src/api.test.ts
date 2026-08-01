import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ApiError,
  createTask,
  artifactContentUrl,
  getArtifact,
  getTask,
  listTaskRuns,
  listTasks,
  loadHealth,
  runTask,
  uploadArtifact,
} from './api'
import type { ArtifactRecord, TaskCreateInput } from './types'

const input: TaskCreateInput = {
  title: '桥梁巡检',
  task_type: 'bridge_inspection',
  objective: '检查无人机影像',
  artifact_ids: ['art_001'],
}

const artifact: ArtifactRecord = {
  artifact_id: 'art bridge/001',
  original_filename: 'bridge.jpg',
  sha256: 'a'.repeat(64),
  size_bytes: 1_572_864,
  mime_type: 'image/jpeg',
  width_px: 1920,
  height_px: 1080,
  status: 'ready',
  content_url: '/api/v1/artifacts/art bridge/001/content',
  created_at: '2026-08-02T01:00:00+00:00',
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

  it('uploads one file as multipart form data', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(response(artifact, 201))
    const file = new File(['jpeg-bytes'], 'bridge.jpg', { type: 'image/jpeg' })

    await uploadArtifact(file)

    const [, init] = fetchMock.mock.calls[0] ?? []
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/api/v1/artifacts')
    expect(init?.method).toBe('POST')
    expect(init?.body).toBeInstanceOf(FormData)
    expect(init?.headers).toBeUndefined()
  })

  it('loads artifact metadata and encodes artifact content URLs', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(response(artifact))

    await expect(getArtifact('art bridge/001')).resolves.toEqual(artifact)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/artifacts/art%20bridge%2F001',
      undefined,
    )
    expect(artifactContentUrl('art bridge/001')).toBe(
      'http://127.0.0.1:8000/api/v1/artifacts/art%20bridge%2F001/content',
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

  it('preserves structured upload errors', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      response(
        { detail: { code: 'ARTIFACT_INVALID_IMAGE', message: '仅支持 JPEG 或 PNG 图片。' } },
        422,
      ),
    )

    const failure = await uploadArtifact(
      new File(['not-an-image'], 'bridge.txt', { type: 'text/plain' }),
    ).catch((error: unknown) => error)

    expect(failure).toMatchObject({
      status: 422,
      code: 'ARTIFACT_INVALID_IMAGE',
      message: '仅支持 JPEG 或 PNG 图片。',
    })
  })
})

function response(payload: object, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}
