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
  bounds?: BoundingBox | null
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

export type FindingCategory =
  | 'functional'
  | 'network'
  | 'javascript'
  | 'crash'
  | 'performance'
  | 'ui'
  | 'ux'
  | 'security'
  | 'accessibility'
  | 'other'

export type FindingSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info'

export type FindingStatus =
  | 'potential'
  | 'investigating'
  | 'confirmed'
  | 'unconfirmed'
  | 'dismissed'

export type ReproductionStatus =
  | 'not_attempted'
  | 'reproducing'
  | 'reproduced'
  | 'not_reproduced'
  | 'intermittent'
  | 'failed'

export interface ReproductionResult {
  id: string
  test_id: string
  finding_id: string
  status: ReproductionStatus | string
  attempts: number
  successful_attempts: number
  steps: string[]
  fresh_evidence: Array<Record<string, any>>
  error_message?: string | null
  success?: boolean | null
  created_at: string
  completed_at?: string | null
}

export interface AIError {
  error_type: string
  message: string
  details?: string | null
  timestamp: string
}

export interface FindingAnalysisResult {
  id: string
  is_meaningful: boolean
  category: string
  severity_suggestion: string
  confidence: number
  observed_facts: string[]
  hypotheses: string[]
  uncertainty: string
  explanation: string
  possible_cause: string
  recommendation: string
  investigation_suggestion: string
  error?: AIError | null
  model_name?: string | null
  analyzed_at: string
}

export interface TestSummaryAnalysis {
  overall_health: string
  key_takeaways: string[]
  top_risks?: string[]
  recommended_actions?: string[]
  error?: AIError | null
  model_name?: string | null
  analyzed_at: string
}

export interface Finding {
  id: string
  severity: FindingSeverity | string
  category: FindingCategory | string
  status: FindingStatus | string
  confidence?: number
  title: string
  description: string
  evidence?: Array<Record<string, any>>
  reproduction?: Record<string, any> | null
  recommendation?: string | null
  ai_analysis?: FindingAnalysisResult | Record<string, any> | null
  fingerprint?: string | null
  reproductions?: ReproductionResult[]
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
  ai_summary?: TestSummaryAnalysis | Record<string, any> | null
  actions_count?: number
  states_count?: number
  findings_count?: number
  actions?: ActionItem[]
  observations?: Observation[]
  findings?: Finding[]
}

export type AgentType = 'technical' | 'ux_ui' | 'chaos' | 'user_behavior'

export type AgentState = 'exploring' | 'reviewing' | 'waiting' | 'finished'

export interface BrowserActionEvent {
  type: 'browser_action'
  inspection_id?: string
  agent: AgentType
  action: 'click' | 'type' | 'scroll' | 'navigate' | 'back' | 'wait' | 'screenshot' | string
  phase?: 'scanning' | 'deciding' | 'targeting' | 'interacting' | 'observing' | string
  target?: string | null
  selector?: string | null
  x?: number | null
  y?: number | null
  target_bounds?: { x: number; y: number; width: number; height: number } | null
  value?: string | null
  direction?: 'up' | 'down' | string | null
  amount?: number | null
  reason?: string | null
  timestamp: string
}

export interface AgentStatusEvent {
  type: 'agent_status'
  active_agent: AgentType
  agents: Record<AgentType, AgentState>
  message: string
  timestamp: string
}

export interface SSEEvent {
  type:
    | 'connected'
    | 'status'
    | 'observation'
    | 'finding'
    | 'finding_reproduced'
    | 'finding_analyzed'
    | 'test_analyzed'
    | 'screenshot'
    | 'browser_frame'
    | 'browser_action'
    | 'agent_status'
    | 'action_start'
    | 'action_completed'
    | 'action_failed'
    | 'error'
  id?: string
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
  selector?: string | null
  value?: string | null
  description?: string | null
  agent?: AgentType | string
  active_agent?: AgentType
  agents?: Record<AgentType, AgentState>
  state?: AgentState | string
  inspection_id?: string
  action?: string
  phase?: string
  x?: number | null
  y?: number | null
  target_bounds?: { x: number; y: number; width: number; height: number } | null
  direction?: string | null
  amount?: number | null
  reason?: string | null
  severity?: string
  category?: string
  confidence?: number
  evidence?: Array<Record<string, any>>
  reproduction?: Record<string, any> | null
  recommendation?: string | null
  reproduction_status?: string
  successful_attempts?: number
  attempts?: number
  finding_id?: string
  actions_count?: number
  states_count?: number
  findings_count?: number
  ai_summary?: string
  timestamp?: string
}
