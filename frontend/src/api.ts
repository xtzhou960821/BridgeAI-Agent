import type {
  ArtifactRecord,
  HealthPayload,
  TaskCreateInput,
  TaskListPayload,
  TaskRecord,
  TaskRunListPayload,
  TaskRunRecord,
} from './types'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1').replace(
  /\/$/,
  '',
)

export class ApiError extends Error {
  readonly status: number
  readonly code: string | null
  readonly runId?: string

  constructor(status: number, message: string, code: string | null = null, runId?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.runId = runId
  }
}

export function loadHealth(): Promise<HealthPayload> {
  return request('/health')
}

export function listTasks(): Promise<TaskListPayload> {
  return request('/tasks')
}

export function createTask(input: TaskCreateInput, idempotencyKey: string): Promise<TaskRecord> {
  return request('/tasks', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify(input),
  })
}

export function uploadArtifact(file: File): Promise<ArtifactRecord> {
  const body = new FormData()
  body.append('file', file)
  return request('/artifacts', { method: 'POST', body })
}

export function getArtifact(artifactId: string): Promise<ArtifactRecord> {
  return request(`/artifacts/${encodeURIComponent(artifactId)}`)
}

export function artifactContentUrl(artifactId: string): string {
  return `${apiBaseUrl}/artifacts/${encodeURIComponent(artifactId)}/content`
}

export function getTask(taskId: string): Promise<TaskRecord> {
  return request(`/tasks/${encodeURIComponent(taskId)}`)
}

export function listTaskRuns(taskId: string): Promise<TaskRunListPayload> {
  return request(`/tasks/${encodeURIComponent(taskId)}/runs`)
}

export function runTask(taskId: string): Promise<TaskRunRecord> {
  return request(`/tasks/${encodeURIComponent(taskId)}/runs`, { method: 'POST' })
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, init)
  const payload = await readJson(response)
  if (!response.ok) {
    throw toApiError(response.status, payload)
  }
  return payload as T
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    return null
  }
}

function toApiError(status: number, payload: unknown): ApiError {
  const body = asRecord(payload)
  const detail = body ? body.detail : null
  if (typeof detail === 'string') {
    return new ApiError(status, detail)
  }
  const structured = asRecord(detail)
  const message = typeof structured?.message === 'string' ? structured.message : `请求失败（${status}）`
  const code = typeof structured?.code === 'string' ? structured.code : null
  const runId = typeof structured?.run_id === 'string' ? structured.run_id : undefined
  return new ApiError(status, message, code, runId)
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : null
}
