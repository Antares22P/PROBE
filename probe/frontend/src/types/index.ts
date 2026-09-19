// Shared TypeScript types matching backend Pydantic models

export type TestStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export type PlatformType = 'web' | 'android' | 'ios'

export interface Test {
  id: string
  url: string
  status: TestStatus
  platform: PlatformType
  created_at: string
  updated_at: string
  started_at: string | null
  completed_at: string | null
  error_message: string | null
}

export interface SSEEvent {
  type: 'connected' | 'status' | 'observation' | 'finding' | 'error'
  status?: string
  message?: string
  url?: string
  title?: string
  element_count?: number
  console_errors?: number
  severity?: string
  category?: string
  description?: string
  findings_count?: number
  ai_summary?: string
}
