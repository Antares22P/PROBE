// Shared TypeScript types matching backend Pydantic models

export type TestStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export type PlatformType = 'web' | 'android' | 'ios'

export interface BoundingBox {
  x: number
  y: number
  width: number
  height: number
}

export interface InteractiveElement {
  id: string
  tag: string
  type: string
  role: string
  text: string
  label: string
  reference: string
  visible: boolean
  enabled: boolean
  bounding_box?: BoundingBox | null
}

export interface ConsoleMessage {
  id?: string
  level: string
  text: string
  location?: string | null
  timestamp?: string
}

export interface JavaScriptException {
  id?: string
  message: string
  stack?: string | null
  timestamp?: string
}

export interface FailedRequest {
  id?: string
  url: string
  method: string
  failure_text: string
  timestamp?: string
}

export interface ActionItem {
  id: string
  action_type: string
  target?: string | null
  value?: string | null
  description?: string | null
  success: boolean
  error?: string | null
  duration_ms?: number | null
  timestamp: string
}

export interface Observation {
  id: string
  url: string
  requested_url?: string
  title?: string
  visible_text?: string
  viewport?: { width: number; height: number } | null
  page_dimensions?: { width: number; height: number } | null
  status_code?: number | null
  duration_ms?: number | null
  error?: string | null
  screenshot_path?: string | null
  element_count: number
  elements_data?: InteractiveElement[]
  console_messages?: ConsoleMessage[]
  console_errors?: string[]
  js_exceptions?: JavaScriptException[]
  failed_requests?: FailedRequest[]
  fingerprint?: string | null
  timestamp: string
}

export interface Finding {
  id: string
  severity: string
  category: string
  title: string
  description: string
  timestamp: string
}

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
  current_url?: string | null
  page_title?: string | null
  duration_ms?: number | null
  status_code?: number | null
  screenshot_url?: string | null
  actions?: ActionItem[]
  observations?: Observation[]
  findings?: Finding[]
}

export interface SSEEvent {
  type:
    | 'connected'
    | 'status'
    | 'observation'
    | 'finding'
    | 'screenshot'
    | 'action_start'
    | 'action_completed'
    | 'action_failed'
    | 'error'
  status?: string
  message?: string
  url?: string
  requested_url?: string
  current_url?: string
  new_url?: string
  title?: string
  page_title?: string
  status_code?: number | null
  duration_ms?: number | null
  error?: string | null
  screenshot_url?: string | null
  path?: string | null
  element_count?: number
  elements?: InteractiveElement[]
  console_messages?: ConsoleMessage[]
  console_errors?: string[] | number
  js_exceptions?: JavaScriptException[]
  failed_requests?: FailedRequest[]
  viewport?: { width: number; height: number } | null
  page_dimensions?: { width: number; height: number } | null
  fingerprint?: string | null
  action_type?: string
  target?: string | null
  value?: string | null
  description?: string | null
  severity?: string
  category?: string
  actions_count?: number
  states_count?: number
  findings_count?: number
  ai_summary?: string
}
