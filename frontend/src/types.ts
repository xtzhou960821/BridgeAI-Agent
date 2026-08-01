export type HealthPayload = {
  service: string
  version: string
  environment: string
  status: string
  components: Record<string, string>
}

export type TaskCreateInput = {
  title: string
  task_type: string
  objective: string
  artifact_ids: string[]
}

export type TaskRecord = TaskCreateInput & {
  task_id: string
  status: string
  created_at: string
  updated_at: string
}

export type WorkflowStep = {
  step_name: string
  output: Record<string, unknown>
}

export type AgentModelSnapshot = {
  model_id?: string
  model_version?: string
  alias?: string
  provider?: string
  runtime?: string
  api_base_url?: string
  is_stub?: boolean
  [key: string]: unknown
}

export type WorkflowSnapshot = {
  task_id?: string
  status?: string
  current_step?: string
  history?: WorkflowStep[]
  error_step?: string | null
  error_message?: string | null
  [key: string]: unknown
}

export type ToolResultSnapshot = {
  tool_id?: string
  version?: string
  ok?: boolean
  output?: Record<string, unknown>
  error_code?: string | null
  error_message?: string | null
  [key: string]: unknown
}

export type TaskRunRecord = {
  run_id: string
  task_id: string
  run_number: number
  status: string
  agent_model: AgentModelSnapshot
  workflow: WorkflowSnapshot
  tool_results: ToolResultSnapshot[]
  error_message: string | null
  started_at: string
  completed_at: string | null
}

export type TaskListPayload = {
  items: TaskRecord[]
}

export type TaskRunListPayload = {
  items: TaskRunRecord[]
}
