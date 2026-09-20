import { useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useTestEvents } from '../lib/sse'
import type {
  Test,
  SSEEvent,
  InteractiveElement,
  ConsoleMessage,
  JavaScriptException,
  FailedRequest,
  ActionItem,
  Finding,
  ReproductionResult,
  FindingAnalysisResult,
  TestSummaryAnalysis,
} from '../types'

const STATUS_COLORS: Record<string, string> = {
  pending: '#6b7280',
  running: '#6366f1',
  completed: '#22c55e',
  failed: '#ef4444',
  cancelled: '#f59e0b',
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#f59e0b',
  low: '#6366f1',
  info: '#6b7280',
}

const FINDING_STATUS_COLORS: Record<string, string> = {
  potential: '#38bdf8',
  investigating: '#c084fc',
  confirmed: '#ef4444',
  unconfirmed: '#94a3b8',
  dismissed: '#64748b',
}

const REPRO_STATUS_COLORS: Record<string, string> = {
  not_attempted: '#6b7280',
  reproducing: '#6366f1',
  reproduced: '#ef4444',
  not_reproduced: '#22c55e',
  intermittent: '#f59e0b',
  failed: '#dc2626',
}

function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] ?? '#6b7280'
  return (
    <span
      className="px-2.5 py-1 rounded text-xs font-mono font-bold uppercase tracking-wider inline-flex items-center gap-1.5"
      style={{
        color,
        backgroundColor: `${color}18`,
        border: `1px solid ${color}35`,
      }}
    >
      <span
        className={`w-2 h-2 rounded-full ${status === 'running' ? 'animate-pulse' : ''}`}
        style={{ background: color }}
      />
      {status}
    </span>
  )
}

function FindingSeverityBadge({ severity }: { severity?: string }) {
  const sev = severity || 'medium'
  const color = SEVERITY_COLORS[sev] ?? '#6b7280'
  return (
    <span
      className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider inline-block"
      style={{
        color,
        backgroundColor: `${color}18`,
        border: `1px solid ${color}35`,
      }}
    >
      {sev}
    </span>
  )
}

function FindingStatusBadge({ status }: { status?: string }) {
  const s = status || 'potential'
  const color = FINDING_STATUS_COLORS[s] ?? '#94a3b8'
  return (
    <span
      className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider inline-block"
      style={{
        color,
        backgroundColor: `${color}18`,
        border: `1px solid ${color}35`,
      }}
    >
      {s}
    </span>
  )
}

function ReproductionStatusBadge({ status }: { status?: string }) {
  const s = status || 'not_attempted'
  const color = REPRO_STATUS_COLORS[s] ?? '#6b7280'
  return (
    <span
      className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider inline-block"
      style={{
        color,
        backgroundColor: `${color}18`,
        border: `1px solid ${color}35`,
      }}
    >
      {s.replace('_', ' ')}
    </span>
  )
}

function StatusCodeBadge({ code }: { code?: number | null }) {
  if (!code) return null
  const is2xx = code >= 200 && code < 300
  const is3xx = code >= 300 && code < 400
  const is4xx = code >= 400 && code < 500
  const is5xx = code >= 500

  const color = is2xx ? '#22c55e' : is3xx ? '#38bdf8' : is4xx ? '#f59e0b' : is5xx ? '#ef4444' : '#94a3b8'

  return (
    <span
      className="px-2 py-0.5 rounded text-[11px] font-mono font-bold"
      style={{ color, backgroundColor: `${color}15`, border: `1px solid ${color}30` }}
    >
      HTTP {code}
    </span>
  )
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}m ${secs.toString().padStart(2, '0')}s`
}

function formatTime(isoStr?: string | null): string {
  if (!isoStr) return ''
  try {
    const d = new Date(isoStr)
    return d.toLocaleTimeString([], { hour12: false })
  } catch {
    return ''
  }
}

// ---------------------------------------------------------------------------
// Finding Detail Modal
// ---------------------------------------------------------------------------

function FindingDetailModal({
  finding,
  testId,
  onClose,
  onFindingUpdated,
}: {
  finding: Finding
  testId: string
  onClose: () => void
  onFindingUpdated: (updatedFinding: Finding) => void
}) {
  const [activeTab, setActiveTab] = useState<'overview' | 'evidence' | 'reproduction' | 'ai'>('overview')
  const [reproducing, setReproducing] = useState(false)
  const [reproAttempts, setReproAttempts] = useState(1)
  const [reproResult, setReproResult] = useState<ReproductionResult | null>(null)
  const [reproHistory, setReproHistory] = useState<ReproductionResult[]>([])
  const [analyzingAI, setAnalyzingAI] = useState(false)
  const [aiAnalysis, setAiAnalysis] = useState<FindingAnalysisResult | null>(
    (finding.ai_analysis as FindingAnalysisResult) || null
  )
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getReproductions(testId, finding.id)
      .then((history) => {
        setReproHistory(history)
        if (history.length > 0) {
          setReproResult(history[0])
        }
      })
      .catch(() => {})
  }, [testId, finding.id])

  const handleReproduce = async () => {
    setReproducing(true)
    setError(null)
    try {
      const res = await api.reproduceFinding(testId, finding.id, reproAttempts)
      setReproResult(res)
      setReproHistory((prev) => [res, ...prev])

      const freshFinding = await api.getFinding(testId, finding.id)
      onFindingUpdated(freshFinding)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reproduction request failed')
    } finally {
      setReproducing(false)
    }
  }

  const handleAnalyzeAI = async () => {
    setAnalyzingAI(true)
    setError(null)
    try {
      const res = await api.analyzeFinding(testId, finding.id)
      setAiAnalysis(res)
      const freshFinding = await api.getFinding(testId, finding.id)
      onFindingUpdated(freshFinding)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI analysis request failed')
    } finally {
      setAnalyzingAI(false)
    }
  }

  const evidenceList = finding.evidence || []
  const screenshotEv = evidenceList.find((e) => e.screenshot_path || e.type === 'screenshot')
  const networkEvList = evidenceList.filter((e) => e.type === 'network' || e.url || e.status_code)
  const consoleEvList = evidenceList.filter((e) => e.type === 'console' || e.level || e.text || e.message)
  const actionSequence = (finding.reproduction?.action_sequence as string[]) || []

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className="w-full max-w-4xl max-h-[90vh] rounded-xl border flex flex-col shadow-2xl overflow-hidden"
        style={{ background: '#0e0e17', borderColor: '#26263b' }}
      >
        {/* Modal Header */}
        <div
          className="px-6 py-4 border-b flex items-start justify-between gap-4"
          style={{ background: '#090910', borderColor: '#1e1e2e' }}
        >
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <FindingSeverityBadge severity={String(finding.severity)} />
              <FindingStatusBadge status={String(finding.status)} />
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300 border border-slate-700 uppercase">
                {finding.category}
              </span>
              {finding.confidence !== undefined && (
                <span className="text-[11px] font-mono text-slate-400">
                  Confidence: {Math.round(finding.confidence * 100)}%
                </span>
              )}
            </div>
            <h2 className="text-base font-mono font-bold text-slate-100 break-words">
              {finding.title}
            </h2>
            <div className="text-xs font-mono text-slate-500 mt-1">
              Finding ID: {finding.id} · Detected: {new Date(finding.timestamp).toLocaleString()}
            </div>
          </div>

          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-100 text-lg font-mono px-2 py-1 rounded transition-colors cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Modal Tabs */}
        <div
          className="flex border-b px-6 gap-6 text-xs font-mono"
          style={{ background: '#0b0b14', borderColor: '#1e1e2e' }}
        >
          {[
            { id: 'overview', label: 'Overview & Telemetry' },
            { id: 'evidence', label: `Evidence (${evidenceList.length})` },
            { id: 'reproduction', label: `Reproduction (${actionSequence.length} Steps)` },
            { id: 'ai', label: 'AI Root Cause Reasoning' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className="py-3 font-semibold transition-colors border-b-2 cursor-pointer"
              style={{
                borderColor: activeTab === tab.id ? '#6366f1' : 'transparent',
                color: activeTab === tab.id ? '#a5b4fc' : '#94a3b8',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {error && (
            <div
              className="p-3 rounded-lg text-xs font-mono border"
              style={{ background: '#1a0a0a', borderColor: '#7f1d1d', color: '#fca5a5' }}
            >
              ⚠ {error}
            </div>
          )}

          {/* TAB 1: OVERVIEW */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-xs font-mono font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Issue Description & Observed Facts
                </h3>
                <div
                  className="p-4 rounded-lg border text-xs font-mono text-slate-200 leading-relaxed"
                  style={{ background: '#080811', borderColor: '#1c1c2b' }}
                >
                  {finding.description || 'No extended description recorded.'}
                </div>
              </div>

              {finding.recommendation && (
                <div>
                  <h3 className="text-xs font-mono font-semibold text-slate-400 uppercase tracking-wider mb-2">
                    Deterministic Recommendation
                  </h3>
                  <div
                    className="p-4 rounded-lg border text-xs font-mono text-emerald-300 leading-relaxed"
                    style={{ background: '#061a11', borderColor: '#0f3d27' }}
                  >
                    💡 {finding.recommendation}
                  </div>
                </div>
              )}

              {/* Quick Status Bar */}
              <div
                className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 rounded-lg border"
                style={{ background: '#080811', borderColor: '#1c1c2b' }}
              >
                <div>
                  <div className="text-[10px] font-mono text-slate-500 uppercase">Category</div>
                  <div className="text-xs font-mono font-semibold text-slate-200 uppercase mt-0.5">{finding.category}</div>
                </div>
                <div>
                  <div className="text-[10px] font-mono text-slate-500 uppercase">Severity</div>
                  <div className="text-xs font-mono font-semibold text-slate-200 uppercase mt-0.5">{finding.severity}</div>
                </div>
                <div>
                  <div className="text-[10px] font-mono text-slate-500 uppercase">Status</div>
                  <div className="text-xs font-mono font-semibold text-slate-200 uppercase mt-0.5">{finding.status}</div>
                </div>
                <div>
                  <div className="text-[10px] font-mono text-slate-500 uppercase">Reproduction</div>
                  <div className="text-xs font-mono font-semibold text-slate-200 uppercase mt-0.5">
                    {reproResult?.status || finding.reproduction?.status || 'not_attempted'}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: EVIDENCE */}
          {activeTab === 'evidence' && (
            <div className="space-y-6">
              {/* Screenshots */}
              {screenshotEv && (
                <div>
                  <h3 className="text-xs font-mono font-semibold text-slate-400 uppercase tracking-wider mb-2">
                    Visual Screenshot Evidence
                  </h3>
                  <div
                    className="rounded-lg border overflow-hidden p-2"
                    style={{ background: '#080811', borderColor: '#1c1c2b' }}
                  >
                    <img
                      src={`/api/tests/${testId}/screenshot?t=${Date.now()}`}
                      alt="Finding Screenshot"
                      className="w-full max-h-80 object-contain rounded bg-black"
                    />
                  </div>
                </div>
              )}

              {/* Console & Exceptions */}
              <div>
                <h3 className="text-xs font-mono font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Console & Exception Evidence ({consoleEvList.length})
                </h3>
                {consoleEvList.length === 0 ? (
                  <p className="text-xs font-mono text-slate-600">No console errors attached.</p>
                ) : (
                  <div className="space-y-2">
                    {consoleEvList.map((ev, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-lg border text-xs font-mono text-red-300"
                        style={{ background: '#180a0a', borderColor: '#3b1616' }}
                      >
                        <div className="font-semibold">{ev.message || ev.text || JSON.stringify(ev)}</div>
                        {ev.stack && (
                          <pre className="text-[10px] text-slate-400 mt-2 whitespace-pre-wrap overflow-x-auto">
                            {ev.stack}
                          </pre>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Network Requests */}
              <div>
                <h3 className="text-xs font-mono font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Network Evidence ({networkEvList.length})
                </h3>
                {networkEvList.length === 0 ? (
                  <p className="text-xs font-mono text-slate-600">No failed network requests attached.</p>
                ) : (
                  <div className="space-y-2">
                    {networkEvList.map((ev, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-lg border text-xs font-mono flex items-start justify-between gap-3"
                        style={{ background: '#080811', borderColor: '#1c1c2b' }}
                      >
                        <div className="min-w-0">
                          <span className="text-amber-400 font-bold mr-2">[{ev.method || 'GET'}]</span>
                          <span className="text-slate-200 break-all">{ev.url}</span>
                          {ev.failure_text && (
                            <div className="text-red-400 text-[11px] mt-1">{ev.failure_text}</div>
                          )}
                        </div>
                        {ev.status_code && <StatusCodeBadge code={ev.status_code} />}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 3: REPRODUCTION */}
          {activeTab === 'reproduction' && (
            <div className="space-y-6">
              {/* Reproduction Control Card */}
              <div
                className="p-4 rounded-lg border flex flex-wrap items-center justify-between gap-4"
                style={{ background: '#080811', borderColor: '#1c1c2b' }}
              >
                <div>
                  <div className="text-xs font-mono font-semibold text-slate-200">
                    Deterministic Replay Engine
                  </div>
                  <div className="text-[11px] font-mono text-slate-500 mt-0.5">
                    Replays the exact structured action sequence in a clean browser session
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    <label className="text-xs font-mono text-slate-400">Attempts:</label>
                    <input
                      type="number"
                      min={1}
                      max={5}
                      value={reproAttempts}
                      onChange={(e) => setReproAttempts(Number(e.target.value))}
                      className="w-14 px-2 py-1 rounded text-xs font-mono text-slate-200 border outline-none"
                      style={{ background: '#11111d', borderColor: '#26263b' }}
                    />
                  </div>

                  <button
                    onClick={handleReproduce}
                    disabled={reproducing || actionSequence.length === 0}
                    className="px-4 py-2 rounded-lg text-xs font-mono font-bold text-white transition-all shadow-md
                               disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2 cursor-pointer"
                    style={{ background: '#6366f1' }}
                  >
                    {reproducing ? (
                      <>
                        <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        <span>Replaying...</span>
                      </>
                    ) : (
                      <>
                        <span>↻ Reproduce Issue</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Action Replay Sequence */}
              <div>
                <h3 className="text-xs font-mono font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Action Replay Sequence ({actionSequence.length} steps)
                </h3>
                {actionSequence.length === 0 ? (
                  <div className="p-4 rounded-lg border text-xs font-mono text-slate-600" style={{ background: '#080811', borderColor: '#1c1c2b' }}>
                    No recorded action sequence available for this finding.
                  </div>
                ) : (
                  <div className="space-y-1.5 font-mono text-xs">
                    {actionSequence.map((act, i) => (
                      <div
                        key={i}
                        className="px-3 py-2 rounded border flex items-center gap-3"
                        style={{ background: '#090912', borderColor: '#1c1c2b' }}
                      >
                        <span className="text-slate-600 font-bold text-[10px]">#{i + 1}</span>
                        <span className="text-indigo-400 font-semibold">{act}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Reproduction Results */}
              {reproResult && (
                <div>
                  <h3 className="text-xs font-mono font-semibold text-slate-400 uppercase tracking-wider mb-2">
                    Latest Reproduction Outcome
                  </h3>
                  <div
                    className="p-4 rounded-lg border space-y-2 text-xs font-mono"
                    style={{ background: '#080811', borderColor: '#1c1c2b' }}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Status:</span>
                      <ReproductionStatusBadge status={reproResult.status} />
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Success Rate:</span>
                      <span className="text-slate-200">
                        {reproResult.successful_attempts} / {reproResult.attempts} attempts
                      </span>
                    </div>
                    {reproResult.error_message && (
                      <div className="text-red-400 text-[11px] pt-1 border-t border-slate-800">
                        Error: {reproResult.error_message}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 4: AI ROOT CAUSE REASONING */}
          {activeTab === 'ai' && (
            <div className="space-y-6">
              {/* Trigger button */}
              <div
                className="p-4 rounded-lg border flex items-center justify-between gap-4"
                style={{ background: '#080811', borderColor: '#1c1c2b' }}
              >
                <div>
                  <div className="text-xs font-mono font-semibold text-slate-200 flex items-center gap-2">
                    <span>✨ Gemini AI Root Cause Analysis</span>
                    {aiAnalysis?.model_name && (
                      <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
                        {aiAnalysis.model_name}
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] font-mono text-slate-500 mt-0.5">
                    Analyzes finding telemetry, categorizes root causes, and generates remediation advice
                  </div>
                </div>

                <button
                  onClick={handleAnalyzeAI}
                  disabled={analyzingAI}
                  className="px-4 py-2 rounded-lg text-xs font-mono font-bold text-white transition-all shadow-md
                             disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2 cursor-pointer"
                  style={{ background: '#6366f1' }}
                >
                  {analyzingAI ? (
                    <>
                      <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      <span>Reasoning...</span>
                    </>
                  ) : (
                    <>
                      <span>✨ Analyze with Gemini</span>
                    </>
                  )}
                </button>
              </div>

              {!aiAnalysis ? (
                <div
                  className="p-8 rounded-lg border text-center text-xs font-mono text-slate-500"
                  style={{ background: '#080811', borderColor: '#1c1c2b' }}
                >
                  Click "Analyze with Gemini" to run structured AI reasoning over this finding's telemetry.
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Facts vs Hypotheses vs Uncertainty Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* Observed Facts */}
                    <div
                      className="p-4 rounded-lg border"
                      style={{ background: '#07131e', borderColor: '#0e3a5a' }}
                    >
                      <div className="text-xs font-mono font-bold text-sky-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                        <span>🔍</span> Observed Facts
                      </div>
                      <ul className="text-xs font-mono text-slate-300 space-y-1.5 list-disc list-inside">
                        {aiAnalysis.observed_facts?.map((fact, i) => (
                          <li key={i}>{fact}</li>
                        ))}
                      </ul>
                    </div>

                    {/* AI Hypotheses */}
                    <div
                      className="p-4 rounded-lg border"
                      style={{ background: '#120b1f', borderColor: '#351c5e' }}
                    >
                      <div className="text-xs font-mono font-bold text-purple-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                        <span>🧠</span> AI Hypotheses
                      </div>
                      <ul className="text-xs font-mono text-slate-300 space-y-1.5 list-disc list-inside">
                        {aiAnalysis.hypotheses?.map((hyp, i) => (
                          <li key={i}>{hyp}</li>
                        ))}
                      </ul>
                    </div>

                    {/* Uncertainty & Telemetry Gaps */}
                    <div
                      className="p-4 rounded-lg border"
                      style={{ background: '#181206', borderColor: '#4a340e' }}
                    >
                      <div className="text-xs font-mono font-bold text-amber-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                        <span>⚠️</span> Uncertainty / Gaps
                      </div>
                      <p className="text-xs font-mono text-slate-300 leading-relaxed">
                        {aiAnalysis.uncertainty || 'No telemetry ambiguity identified.'}
                      </p>
                    </div>
                  </div>

                  {/* Remediation & Possible Cause */}
                  <div
                    className="p-4 rounded-lg border space-y-3"
                    style={{ background: '#080811', borderColor: '#1c1c2b' }}
                  >
                    <div>
                      <div className="text-xs font-mono font-bold text-slate-400 uppercase">Possible Cause:</div>
                      <p className="text-xs font-mono text-slate-200 mt-1">{aiAnalysis.possible_cause}</p>
                    </div>
                    <div>
                      <div className="text-xs font-mono font-bold text-slate-400 uppercase">Recommendation:</div>
                      <p className="text-xs font-mono text-emerald-300 mt-1">💡 {aiAnalysis.recommendation}</p>
                    </div>
                    {aiAnalysis.investigation_suggestion && (
                      <div>
                        <div className="text-xs font-mono font-bold text-slate-400 uppercase">Suggested Next Step:</div>
                        <p className="text-xs font-mono text-indigo-300 mt-1">🔬 {aiAnalysis.investigation_suggestion}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Live Test View
// ---------------------------------------------------------------------------

export function Test() {
  const { id } = useParams<{ id: string }>()
  const [test, setTest] = useState<Test | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState(false)

  // Live state
  const [liveUrl, setLiveUrl] = useState<string>('')
  const [liveTitle, setLiveTitle] = useState<string>('')
  const [liveStatusCode, setLiveStatusCode] = useState<number | null>(null)
  const [liveDurationMs, setLiveDurationMs] = useState<number | null>(null)
  const [liveFingerprint, setLiveFingerprint] = useState<string | null>(null)
  const [liveElements, setLiveElements] = useState<InteractiveElement[]>([])
  const [liveConsoleMsgs, setLiveConsoleMsgs] = useState<ConsoleMessage[]>([])
  const [liveConsoleErrors, setLiveConsoleErrors] = useState<string[]>([])
  const [liveJsExceptions, setLiveJsExceptions] = useState<JavaScriptException[]>([])
  const [liveFailedRequests, setLiveFailedRequests] = useState<FailedRequest[]>([])
  const [screenshotTimestamp, setScreenshotTimestamp] = useState<number>(Date.now())
  const [fullImageModal, setFullImageModal] = useState(false)

  // Metrics counters
  const [statesCount, setStatesCount] = useState<number>(0)
  const [actionsCount, setActionsCount] = useState<number>(0)
  const [findings, setFindings] = useState<Finding[]>([])
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null)

  // Timeline events
  const [timelineEvents, setTimelineEvents] = useState<
    Array<{ id: string; time: string; type: string; label: string; detail?: string; success?: boolean; color?: string }>
  >([])
  const [timelineFilter, setTimelineFilter] = useState<'all' | 'actions' | 'observations' | 'findings'>('all')
  const [autoScroll, setAutoScroll] = useState(true)
  const timelineEndRef = useRef<HTMLDivElement>(null)

  // Findings filters
  const [findingSearch, setFindingSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [severityFilter, setSeverityFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  // Elements drawer
  const [showElementsDrawer, setShowElementsDrawer] = useState(false)
  const [elementSearch, setElementSearch] = useState('')

  // AI Summary
  const [analyzingSummary, setAnalyzingSummary] = useState(false)
  const [aiSummary, setAiSummary] = useState<TestSummaryAnalysis | null>(null)

  // Timer
  const [elapsedSeconds, setElapsedSeconds] = useState(0)

  // Load initial data
  useEffect(() => {
    if (!id) return
    api.getTest(id)
      .then((t) => {
        setTest(t)
        setLiveUrl(t.current_url || t.url)
        setLiveTitle(t.page_title || '')
        setLiveStatusCode(t.status_code ?? null)
        setLiveDurationMs(t.duration_ms ?? null)
        setFindings(t.findings || [])
        setActionsCount(t.actions?.length || 0)
        setStatesCount(t.observations?.length || 0)
        setAiSummary((t.ai_summary as TestSummaryAnalysis) || null)

        // Populate historical events
        const historical: typeof timelineEvents = []
        if (t.started_at) {
          historical.push({
            id: 'start',
            time: formatTime(t.started_at),
            type: 'status',
            label: `Test Started: ${t.url}`,
            color: '#6366f1',
          })
        }
        for (const act of t.actions || []) {
          historical.push({
            id: act.id,
            time: formatTime(act.timestamp),
            type: 'action',
            label: `${act.action_type.toUpperCase()} ${act.target || ''}`,
            detail: act.description || act.value || undefined,
            success: act.success,
            color: act.success ? '#22c55e' : '#ef4444',
          })
        }
        for (const obs of t.observations || []) {
          historical.push({
            id: obs.id,
            time: formatTime(obs.timestamp),
            type: 'observation',
            label: `Observe ${obs.url}`,
            detail: obs.title ? `"${obs.title}" (${obs.element_count} elements)` : undefined,
            color: '#818cf8',
          })
        }
        for (const f of t.findings || []) {
          historical.push({
            id: f.id,
            time: formatTime(f.timestamp),
            type: 'finding',
            label: `Finding: [${f.severity.toUpperCase()}] ${f.title}`,
            detail: f.category,
            color: SEVERITY_COLORS[f.severity] || '#f59e0b',
          })
        }
        setTimelineEvents(historical)

        if (t.observations && t.observations.length > 0) {
          const latestObs = t.observations[t.observations.length - 1]
          setLiveElements(latestObs.elements_data || [])
          setLiveConsoleMsgs(latestObs.console_messages || [])
          setLiveConsoleErrors(latestObs.console_errors || [])
          setLiveJsExceptions(latestObs.js_exceptions || [])
          setLiveFailedRequests(latestObs.failed_requests || [])
          setLiveFingerprint(latestObs.fingerprint || null)
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  // Live timer
  useEffect(() => {
    if (!test || test.status !== 'running') return
    const interval = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1)
    }, 1000)
    return () => clearInterval(interval)
  }, [test?.status])

  // SSE Stream
  useTestEvents(id ?? '', {
    onEvent: (event: SSEEvent) => {
      const timeStr = new Date().toLocaleTimeString([], { hour12: false })

      if (event.type === 'status') {
        if (event.status) {
          setTest((prev) => (prev ? { ...prev, status: event.status as any } : null))
        }
        setTimelineEvents((prev) => [
          ...prev,
          {
            id: `${Date.now()}-${Math.random()}`,
            time: timeStr,
            type: 'status',
            label: event.message || `Status changed to ${event.status}`,
            color: STATUS_COLORS[event.status || ''] || '#6b7280',
          },
        ])
        if (event.actions_count !== undefined) setActionsCount(event.actions_count)
        if (event.states_count !== undefined) setStatesCount(event.states_count)
      }

      if (event.type === 'observation') {
        setLiveUrl(event.url || event.requested_url || '')
        if (event.title) setLiveTitle(event.title)
        if (event.status_code !== undefined) setLiveStatusCode(event.status_code)
        if (event.duration_ms !== undefined) setLiveDurationMs(event.duration_ms)
        if (event.elements) setLiveElements(event.elements)
        if (event.fingerprint) setLiveFingerprint(event.fingerprint)
        if (event.console_messages) setLiveConsoleMsgs(event.console_messages)
        if (event.console_errors) {
          setLiveConsoleErrors(Array.isArray(event.console_errors) ? event.console_errors : [])
        }
        if (event.js_exceptions) setLiveJsExceptions(event.js_exceptions)
        if (event.failed_requests) setLiveFailedRequests(event.failed_requests)

        setStatesCount((prev) => prev + 1)
        setScreenshotTimestamp(Date.now())

        setTimelineEvents((prev) => [
          ...prev,
          {
            id: `${Date.now()}-${Math.random()}`,
            time: timeStr,
            type: 'observation',
            label: `Observe ${event.url || event.requested_url}`,
            detail: event.title ? `"${event.title}"` : undefined,
            color: '#818cf8',
          },
        ])
      }

      if (event.type === 'action_completed') {
        setActionsCount((prev) => prev + 1)
        setTimelineEvents((prev) => [
          ...prev,
          {
            id: `${Date.now()}-${Math.random()}`,
            time: timeStr,
            type: 'action',
            label: event.description || `Action ${event.action_type}`,
            detail: event.new_url ? `→ ${event.new_url}` : undefined,
            success: true,
            color: '#22c55e',
          },
        ])
      }

      if (event.type === 'action_failed') {
        setActionsCount((prev) => prev + 1)
        setTimelineEvents((prev) => [
          ...prev,
          {
            id: `${Date.now()}-${Math.random()}`,
            time: timeStr,
            type: 'action',
            label: event.description || `Action Failed`,
            success: false,
            color: '#ef4444',
          },
        ])
      }

      if (event.type === 'finding') {
        const newFinding: Finding = {
          id: event.finding_id || event.id || `${Date.now()}`,
          title: event.title || event.description || 'Discovered Signal',
          description: event.description || '',
          category: event.category || 'functional',
          severity: event.severity || 'medium',
          status: event.status || 'potential',
          confidence: event.confidence ?? 0.8,
          evidence: event.evidence || [],
          reproduction: event.reproduction || null,
          recommendation: event.recommendation || null,
          timestamp: new Date().toISOString(),
        }
        setFindings((prev) => {
          const exists = prev.some((f) => f.id === newFinding.id)
          return exists ? prev : [newFinding, ...prev]
        })
        setTimelineEvents((prev) => [
          ...prev,
          {
            id: `${Date.now()}-${Math.random()}`,
            time: timeStr,
            type: 'finding',
            label: `Finding: [${newFinding.severity.toUpperCase()}] ${newFinding.title}`,
            detail: newFinding.category,
            color: SEVERITY_COLORS[newFinding.severity] || '#f59e0b',
          },
        ])
      }

      if (event.type === 'screenshot') {
        setScreenshotTimestamp(Date.now())
      }

      if (event.type === 'test_analyzed' && event.ai_summary) {
        setAiSummary(event.ai_summary as any)
      }
    },
  })

  // Auto-scroll timeline
  useEffect(() => {
    if (autoScroll && timelineEndRef.current) {
      timelineEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [timelineEvents, autoScroll])

  const handleCancel = async () => {
    if (!id || cancelling) return
    setCancelling(true)
    try {
      await api.cancelTest(id)
      setTest((prev) => (prev ? { ...prev, status: 'cancelled' } : null))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel test')
    } finally {
      setCancelling(false)
    }
  }

  const handleGenerateSummary = async () => {
    if (!id || analyzingSummary) return
    setAnalyzingSummary(true)
    setError(null)
    try {
      const summary = await api.analyzeTest(id)
      setAiSummary(summary)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate AI summary')
    } finally {
      setAnalyzingSummary(false)
    }
  }

  // Filtered Findings
  const potentialCount = findings.filter((f) => String(f.status) === 'potential').length
  const confirmedCount = findings.filter((f) => String(f.status) === 'confirmed').length

  const filteredFindings = findings.filter((f) => {
    const matchesSearch =
      !findingSearch ||
      f.title.toLowerCase().includes(findingSearch.toLowerCase()) ||
      f.description.toLowerCase().includes(findingSearch.toLowerCase()) ||
      f.category.toLowerCase().includes(findingSearch.toLowerCase())
    const matchesCategory = categoryFilter === 'all' || f.category === categoryFilter
    const matchesSeverity = severityFilter === 'all' || f.severity === severityFilter
    const matchesStatus = statusFilter === 'all' || f.status === statusFilter
    return matchesSearch && matchesCategory && matchesSeverity && matchesStatus
  })

  // Filtered Timeline
  const filteredTimeline = timelineEvents.filter((ev) => {
    if (timelineFilter === 'all') return true
    if (timelineFilter === 'actions') return ev.type === 'action'
    if (timelineFilter === 'observations') return ev.type === 'observation'
    if (timelineFilter === 'findings') return ev.type === 'finding'
    return true
  })

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-52px)]">
        <div className="text-center">
          <div className="inline-block w-8 h-8 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin mb-3" />
          <p className="text-xs font-mono text-slate-400">Loading PROBE test session...</p>
        </div>
      </div>
    )
  }

  if (error && !test) {
    return (
      <div className="max-w-xl mx-auto px-4 py-16 text-center">
        <div className="p-6 rounded-xl border" style={{ background: '#1a0a0a', borderColor: '#7f1d1d' }}>
          <p className="text-sm font-mono text-red-300 font-semibold mb-2">Error Loading Test</p>
          <p className="text-xs font-mono text-slate-400 mb-4">{error}</p>
          <Link to="/" className="text-xs font-mono text-indigo-400 hover:underline">
            ← Return to Home
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* ------------------------------------------------------------------- */}
      {/* 1. TOP HEADER & METRICS BAR                                         */}
      {/* ------------------------------------------------------------------- */}
      <div
        className="rounded-xl border p-5 shadow-xl backdrop-blur-sm"
        style={{ background: '#0e0e17', borderColor: '#1e1e2e' }}
      >
        <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800/80">
          <div className="flex flex-wrap items-center gap-3 min-w-0">
            <Link
              to="/history"
              className="text-xs font-mono text-slate-400 hover:text-slate-200 transition-colors flex items-center gap-1"
            >
              ← History
            </Link>
            <span className="text-slate-700">|</span>
            <StatusBadge status={test?.status || 'pending'} />
            <div className="min-w-0">
              <span className="text-xs font-mono text-slate-500 mr-2">Target:</span>
              <span className="text-sm font-mono font-bold text-slate-100 truncate">{test?.url}</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {test?.status === 'running' && (
              <button
                onClick={handleCancel}
                disabled={cancelling}
                className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold text-amber-300 bg-amber-950/40 border border-amber-800/60 hover:bg-amber-900/50 transition-colors cursor-pointer"
              >
                {cancelling ? 'Cancelling...' : '■ Cancel Test'}
              </button>
            )}
            <button
              onClick={handleGenerateSummary}
              disabled={analyzingSummary}
              className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold text-indigo-200 bg-indigo-950/60 border border-indigo-700/60 hover:bg-indigo-900/60 transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              {analyzingSummary ? 'Summarizing...' : '✨ Executive Summary'}
            </button>
          </div>
        </div>

        {/* Live Metrics Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 pt-4">
          {/* Current URL */}
          <div className="col-span-2 p-3 rounded-lg border" style={{ background: '#080811', borderColor: '#1c1c2b' }}>
            <div className="text-[10px] font-mono text-slate-500 uppercase">Live URL</div>
            <div className="text-xs font-mono font-semibold text-slate-200 truncate mt-0.5" title={liveUrl}>
              {liveUrl || '—'}
            </div>
          </div>

          {/* Elapsed Time */}
          <div className="p-3 rounded-lg border" style={{ background: '#080811', borderColor: '#1c1c2b' }}>
            <div className="text-[10px] font-mono text-slate-500 uppercase">Elapsed Time</div>
            <div className="text-xs font-mono font-bold text-indigo-400 mt-0.5">
              {test?.status === 'running' ? formatElapsed(elapsedSeconds) : liveDurationMs ? `${(liveDurationMs / 1000).toFixed(1)}s` : 'Completed'}
            </div>
          </div>

          {/* States Explored */}
          <div className="p-3 rounded-lg border" style={{ background: '#080811', borderColor: '#1c1c2b' }}>
            <div className="text-[10px] font-mono text-slate-500 uppercase">States Explored</div>
            <div className="text-base font-mono font-bold text-slate-100 mt-0.5">{statesCount}</div>
          </div>

          {/* Actions Performed */}
          <div className="p-3 rounded-lg border" style={{ background: '#080811', borderColor: '#1c1c2b' }}>
            <div className="text-[10px] font-mono text-slate-500 uppercase">Actions Performed</div>
            <div className="text-base font-mono font-bold text-slate-100 mt-0.5">{actionsCount}</div>
          </div>

          {/* Potential / Confirmed Findings */}
          <div className="p-3 rounded-lg border" style={{ background: '#080811', borderColor: '#1c1c2b' }}>
            <div className="text-[10px] font-mono text-slate-500 uppercase">Findings</div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs font-mono font-bold text-sky-400" title="Potential">
                {potentialCount} pot.
              </span>
              <span className="text-slate-600">/</span>
              <span className="text-xs font-mono font-bold text-red-400" title="Confirmed">
                {confirmedCount} conf.
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* 2. MAIN 2-COLUMN GRID: Current State & Latest Screenshot            */}
      {/* ------------------------------------------------------------------- */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Current Application State */}
        <div
          className="rounded-xl border p-5 shadow-xl flex flex-col justify-between space-y-4"
          style={{ background: '#0e0e17', borderColor: '#1e1e2e' }}
        >
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h2 className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <span>🌐</span> Current Application State
              </h2>
              {liveStatusCode && <StatusCodeBadge code={liveStatusCode} />}
            </div>

            <div className="mt-3 space-y-3">
              <div>
                <span className="text-[10px] font-mono text-slate-500 uppercase">Page Title</span>
                <p className="text-xs font-mono text-slate-200 font-semibold truncate mt-0.5">
                  {liveTitle || 'No Title Recorded'}
                </p>
              </div>

              <div>
                <span className="text-[10px] font-mono text-slate-500 uppercase">State Fingerprint</span>
                <p className="text-[11px] font-mono text-indigo-300 font-mono break-all mt-0.5">
                  {liveFingerprint || '—'}
                </p>
              </div>

              {/* Discovered Elements Counter */}
              <div
                className="p-3 rounded-lg border flex items-center justify-between"
                style={{ background: '#080811', borderColor: '#1c1c2b' }}
              >
                <div>
                  <div className="text-xs font-mono font-semibold text-slate-200">
                    Discovered Interactive Elements ({liveElements.length})
                  </div>
                  <div className="text-[10px] font-mono text-slate-500">
                    Links, buttons, inputs, selects extracted by Playwright
                  </div>
                </div>
                <button
                  onClick={() => setShowElementsDrawer(!showElementsDrawer)}
                  className="px-2.5 py-1 rounded text-[11px] font-mono font-semibold text-indigo-300 border border-indigo-800 bg-indigo-950/50 hover:bg-indigo-900/50 transition-colors cursor-pointer"
                >
                  {showElementsDrawer ? 'Hide Elements' : 'View Elements →'}
                </button>
              </div>

              {/* Signals Counter Badges */}
              <div className="grid grid-cols-3 gap-2 pt-1">
                <div
                  className="p-2.5 rounded border text-center"
                  style={{
                    background: liveConsoleErrors.length > 0 ? '#1f0d0d' : '#080811',
                    borderColor: liveConsoleErrors.length > 0 ? '#5a1d1d' : '#1c1c2b',
                  }}
                >
                  <div className="text-[10px] font-mono text-slate-500">Console Errors</div>
                  <div className={`text-xs font-mono font-bold mt-0.5 ${liveConsoleErrors.length > 0 ? 'text-red-400' : 'text-slate-400'}`}>
                    {liveConsoleErrors.length}
                  </div>
                </div>

                <div
                  className="p-2.5 rounded border text-center"
                  style={{
                    background: liveJsExceptions.length > 0 ? '#1f0d0d' : '#080811',
                    borderColor: liveJsExceptions.length > 0 ? '#5a1d1d' : '#1c1c2b',
                  }}
                >
                  <div className="text-[10px] font-mono text-slate-500">JS Exceptions</div>
                  <div className={`text-xs font-mono font-bold mt-0.5 ${liveJsExceptions.length > 0 ? 'text-red-400' : 'text-slate-400'}`}>
                    {liveJsExceptions.length}
                  </div>
                </div>

                <div
                  className="p-2.5 rounded border text-center"
                  style={{
                    background: liveFailedRequests.length > 0 ? '#1f1406' : '#080811',
                    borderColor: liveFailedRequests.length > 0 ? '#5e380f' : '#1c1c2b',
                  }}
                >
                  <div className="text-[10px] font-mono text-slate-500">Failed HTTP</div>
                  <div className={`text-xs font-mono font-bold mt-0.5 ${liveFailedRequests.length > 0 ? 'text-amber-400' : 'text-slate-400'}`}>
                    {liveFailedRequests.length}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Interactive Elements Drawer Modal */}
          {showElementsDrawer && (
            <div className="pt-2 border-t border-slate-800">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-mono text-slate-400 font-semibold uppercase">Discovered DOM Elements:</span>
                <input
                  type="text"
                  placeholder="Filter elements..."
                  value={elementSearch}
                  onChange={(e) => setElementSearch(e.target.value)}
                  className="px-2 py-0.5 rounded text-[11px] font-mono text-slate-200 border outline-none"
                  style={{ background: '#080811', borderColor: '#26263b' }}
                />
              </div>
              <div className="max-h-48 overflow-y-auto space-y-1 font-mono text-[11px]">
                {liveElements
                  .filter((el) => !elementSearch || el.text.toLowerCase().includes(elementSearch.toLowerCase()) || el.reference.includes(elementSearch) || el.tag.includes(elementSearch))
                  .map((el, i) => (
                    <div key={i} className="p-1.5 rounded border flex items-center justify-between gap-2" style={{ background: '#080811', borderColor: '#1c1c2b' }}>
                      <div className="truncate">
                        <span className="text-indigo-400 font-semibold mr-1.5">&lt;{el.tag}&gt;</span>
                        <span className="text-slate-300 font-medium">{el.text || el.label || el.reference}</span>
                      </div>
                      <span className="text-[10px] text-slate-500 shrink-0">{el.role || el.type}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Latest Screenshot */}
        <div
          className="rounded-xl border p-5 shadow-xl flex flex-col justify-between space-y-3"
          style={{ background: '#0e0e17', borderColor: '#1e1e2e' }}
        >
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <h2 className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <span>📷</span> Latest Screenshot Snapshot
            </h2>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setScreenshotTimestamp(Date.now())}
                className="text-[10px] font-mono text-slate-400 hover:text-slate-200 transition-colors px-2 py-0.5 rounded border border-slate-700"
              >
                ↻ Refresh
              </button>
              <button
                onClick={() => setFullImageModal(true)}
                className="text-[10px] font-mono text-indigo-400 hover:text-indigo-200 transition-colors px-2 py-0.5 rounded border border-indigo-800"
              >
                🔍 Fullscreen
              </button>
            </div>
          </div>

          <div
            className="flex-1 min-h-[220px] rounded-lg border overflow-hidden flex items-center justify-center relative group"
            style={{ background: '#07070d', borderColor: '#1c1c2b' }}
          >
            <img
              key={screenshotTimestamp}
              src={`/api/tests/${id}/screenshot?t=${screenshotTimestamp}`}
              alt="Test Screenshot"
              className="max-h-[240px] w-auto max-w-full object-contain cursor-pointer transition-transform group-hover:scale-[1.01]"
              onClick={() => setFullImageModal(true)}
              onError={(e) => {
                const target = e.target as HTMLImageElement
                target.style.display = 'none'
              }}
            />
          </div>
          <div className="text-[10px] font-mono text-slate-500 text-center">
            Updated on every deterministic state navigation
          </div>
        </div>
      </div>

      {/* Fullscreen Image Preview Modal */}
      {fullImageModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-md"
          onClick={() => setFullImageModal(false)}
        >
          <div className="relative max-w-6xl max-h-[90vh] overflow-hidden rounded-lg border border-slate-700">
            <button
              onClick={() => setFullImageModal(false)}
              className="absolute top-3 right-3 text-white bg-black/70 hover:bg-black p-2 rounded-full font-mono text-xs cursor-pointer z-10"
            >
              ✕ Close
            </button>
            <img
              src={`/api/tests/${id}/screenshot?t=${screenshotTimestamp}`}
              alt="Full Resolution Screenshot"
              className="max-h-[85vh] w-auto object-contain bg-black"
            />
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* 3. ACTION / EVENT TIMELINE                                          */}
      {/* ------------------------------------------------------------------- */}
      <div
        className="rounded-xl border p-5 shadow-xl space-y-4"
        style={{ background: '#0e0e17', borderColor: '#1e1e2e' }}
      >
        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <h2 className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <span>⚡</span> Action & Event Timeline
            </h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
              {filteredTimeline.length} events
            </span>
          </div>

          <div className="flex items-center gap-3">
            {/* Filter pills */}
            <div className="flex items-center gap-1">
              {(['all', 'actions', 'observations', 'findings'] as const).map((flt) => (
                <button
                  key={flt}
                  onClick={() => setTimelineFilter(flt)}
                  className="px-2 py-0.5 rounded text-[10px] font-mono capitalize transition-colors cursor-pointer"
                  style={{
                    background: timelineFilter === flt ? '#6366f125' : '#11111d',
                    color: timelineFilter === flt ? '#a5b4fc' : '#94a3b8',
                    border: `1px solid ${timelineFilter === flt ? '#6366f1' : '#1e1e2e'}`,
                  }}
                >
                  {flt}
                </button>
              ))}
            </div>

            <label className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400 cursor-pointer">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                className="rounded accent-indigo-500"
              />
              Auto-scroll
            </label>
          </div>
        </div>

        {/* Timeline Log Window */}
        <div
          className="h-64 overflow-y-auto p-4 rounded-lg border font-mono text-xs space-y-1.5"
          style={{ background: '#07070d', borderColor: '#1c1c2b' }}
        >
          {filteredTimeline.length === 0 ? (
            <div className="h-full flex items-center justify-center text-slate-600 text-xs">
              Awaiting actions and telemetry events...
            </div>
          ) : (
            filteredTimeline.map((ev) => (
              <div key={ev.id} className="flex items-start gap-2.5 py-0.5">
                <span className="text-slate-600 text-[11px] shrink-0">[{ev.time}]</span>
                <span className="font-semibold shrink-0" style={{ color: ev.color || '#94a3b8' }}>
                  {ev.label}
                </span>
                {ev.detail && <span className="text-slate-400 truncate">{ev.detail}</span>}
              </div>
            ))
          )}
          <div ref={timelineEndRef} />
        </div>
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* 4. FINDINGS INTERFACE                                               */}
      {/* ------------------------------------------------------------------- */}
      <div
        className="rounded-xl border p-5 shadow-xl space-y-5"
        style={{ background: '#0e0e17', borderColor: '#1e1e2e' }}
      >
        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <h2 className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <span>🛡️</span> Discovered Findings ({findings.length})
            </h2>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Search */}
            <input
              type="text"
              placeholder="Search findings..."
              value={findingSearch}
              onChange={(e) => setFindingSearch(e.target.value)}
              className="px-3 py-1 rounded-lg text-xs font-mono text-slate-200 placeholder-slate-600 border outline-none"
              style={{ background: '#080811', borderColor: '#1c1c2b' }}
            />

            {/* Severity Filter */}
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="px-2.5 py-1 rounded text-xs font-mono text-slate-300 border outline-none capitalize"
              style={{ background: '#080811', borderColor: '#1c1c2b' }}
            >
              <option value="all">All Severities</option>
              {['critical', 'high', 'medium', 'low', 'info'].map((sev) => (
                <option key={sev} value={sev}>{sev}</option>
              ))}
            </select>

            {/* Category Filter */}
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="px-2.5 py-1 rounded text-xs font-mono text-slate-300 border outline-none capitalize"
              style={{ background: '#080811', borderColor: '#1c1c2b' }}
            >
              <option value="all">All Categories</option>
              {['functional', 'network', 'javascript', 'crash', 'performance', 'ui', 'ux', 'security', 'accessibility'].map((cat) => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-2.5 py-1 rounded text-xs font-mono text-slate-300 border outline-none capitalize"
              style={{ background: '#080811', borderColor: '#1c1c2b' }}
            >
              <option value="all">All Statuses</option>
              {['potential', 'investigating', 'confirmed', 'unconfirmed', 'dismissed'].map((st) => (
                <option key={st} value={st}>{st}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Findings List */}
        {filteredFindings.length === 0 ? (
          <div
            className="p-12 rounded-lg border text-center"
            style={{ background: '#080811', borderColor: '#1c1c2b' }}
          >
            <div className="text-2xl mb-2">🎉</div>
            <p className="text-sm font-mono text-slate-300 font-semibold">
              {findings.length === 0 ? 'No Findings Detected Yet' : 'No findings match current filter criteria'}
            </p>
            <p className="text-xs font-mono text-slate-500 mt-1">
              PROBE evaluates network errors, JavaScript exceptions, and broken UI states deterministically.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredFindings.map((f) => (
              <div
                key={f.id}
                onClick={() => setSelectedFinding(f)}
                className="p-4 rounded-lg border hover:border-indigo-500/60 transition-all cursor-pointer space-y-3 group shadow-md"
                style={{ background: '#090912', borderColor: '#1c1c2b' }}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <FindingSeverityBadge severity={String(f.severity)} />
                    <FindingStatusBadge status={String(f.status)} />
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800/80 text-slate-400 uppercase">
                      {f.category}
                    </span>
                  </div>
                  {f.ai_analysis && (
                    <span className="text-[10px] font-mono text-indigo-400 font-semibold flex items-center gap-1">
                      ✨ AI Analyzed
                    </span>
                  )}
                </div>

                <div>
                  <h3 className="text-xs font-mono font-bold text-slate-100 group-hover:text-indigo-300 transition-colors line-clamp-2">
                    {f.title}
                  </h3>
                  <p className="text-[11px] font-mono text-slate-400 line-clamp-2 mt-1">
                    {f.description}
                  </p>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-[10px] font-mono text-slate-500">
                  <span>Confidence: {Math.round((f.confidence ?? 0.8) * 100)}%</span>
                  <span className="text-indigo-400 group-hover:underline">Inspect Details →</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* 5. AI EXECUTIVE TEST SUMMARY (If available)                         */}
      {/* ------------------------------------------------------------------- */}
      {aiSummary && (
        <div
          className="rounded-xl border p-5 shadow-xl space-y-4"
          style={{ background: '#0e0e17', borderColor: '#1e1e2e' }}
        >
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <h2 className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <span>✨</span> Gemini Executive Test Run Summary
            </h2>
            <span
              className="px-2.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider"
              style={{
                color: aiSummary.overall_health === 'healthy' ? '#22c55e' : aiSummary.overall_health === 'degraded' ? '#f59e0b' : '#ef4444',
                background: `${aiSummary.overall_health === 'healthy' ? '#22c55e' : aiSummary.overall_health === 'degraded' ? '#f59e0b' : '#ef4444'}18`,
                border: `1px solid ${aiSummary.overall_health === 'healthy' ? '#22c55e' : aiSummary.overall_health === 'degraded' ? '#f59e0b' : '#ef4444'}35`,
              }}
            >
              {aiSummary.overall_health?.replace('_', ' ')}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg border" style={{ background: '#080811', borderColor: '#1c1c2b' }}>
              <div className="text-xs font-mono font-bold text-slate-400 uppercase mb-2">Key Takeaways</div>
              <ul className="text-xs font-mono text-slate-300 space-y-1.5 list-disc list-inside">
                {aiSummary.key_takeaways?.map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            </div>

            <div className="p-4 rounded-lg border" style={{ background: '#080811', borderColor: '#1c1c2b' }}>
              <div className="text-xs font-mono font-bold text-red-400 uppercase mb-2">Top Identified Risks</div>
              <ul className="text-xs font-mono text-slate-300 space-y-1.5 list-disc list-inside">
                {aiSummary.top_risks?.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>

            <div className="p-4 rounded-lg border" style={{ background: '#080811', borderColor: '#1c1c2b' }}>
              <div className="text-xs font-mono font-bold text-emerald-400 uppercase mb-2">Recommended Actions</div>
              <ul className="text-xs font-mono text-slate-300 space-y-1.5 list-disc list-inside">
                {aiSummary.recommended_actions?.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Finding Detail Modal */}
      {selectedFinding && id && (
        <FindingDetailModal
          finding={selectedFinding}
          testId={id}
          onClose={() => setSelectedFinding(null)}
          onFindingUpdated={(updated) => {
            setSelectedFinding(updated)
            setFindings((prev) => prev.map((f) => (f.id === updated.id ? updated : f)))
          }}
        />
      )}
    </div>
  )
}
