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

function FindingStatusBadge({ status }: { status?: string }) {
  const s = status || 'potential'
  const color = FINDING_STATUS_COLORS[s] ?? '#94a3b8'
  return (
    <span
      className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider"
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

function FindingSeverityBadge({ severity }: { severity?: string }) {
  const sev = severity || 'medium'
  const color = SEVERITY_COLORS[sev] ?? '#6b7280'
  return (
    <span
      className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider"
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

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className="px-2.5 py-0.5 rounded text-xs font-mono font-semibold uppercase tracking-wider"
      style={{
        color: STATUS_COLORS[status] ?? '#6b7280',
        backgroundColor: `${STATUS_COLORS[status] ?? '#6b7280'}18`,
        border: `1px solid ${STATUS_COLORS[status] ?? '#6b7280'}33`,
      }}
    >
      {status}
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
      className="px-2 py-0.5 rounded text-xs font-mono font-semibold"
      style={{ color, backgroundColor: `${color}15`, border: `1px solid ${color}30` }}
    >
      HTTP {code}
    </span>
  )
}

function EventRow({ event }: { event: SSEEvent }) {
  const timeStr = new Date().toLocaleTimeString([], { hour12: false })

  if (event.type === 'connected') {
    return (
      <div className="text-xs font-mono text-slate-500 py-0.5">
        <span className="text-slate-600 mr-2">[{timeStr}]</span>
        — Connected to PROBE autonomous stream
      </div>
    )
  }

  if (event.type === 'status') {
    const color = STATUS_COLORS[event.status ?? ''] ?? '#6b7280'
    return (
      <div className="text-xs font-mono py-0.5" style={{ color }}>
        <span className="text-slate-600 mr-2">[{timeStr}]</span>
        <span className="font-semibold">[{event.status?.toUpperCase()}]</span> {event.message}
        {event.actions_count !== undefined && (
          <span className="text-slate-400 ml-2">
            ({event.actions_count} action{event.actions_count !== 1 ? 's' : ''}, {event.states_count ?? 0} states)
          </span>
        )}
      </div>
    )
  }

  if (event.type === 'action_start') {
    return (
      <div className="text-xs font-mono text-amber-300/90 py-0.5">
        <span className="text-slate-600 mr-2">[{timeStr}]</span>
        <span className="text-amber-400 font-semibold">[ACTION:START]</span>{' '}
        <span>{event.description || `Executing ${event.action_type}`}</span>
      </div>
    )
  }

  if (event.type === 'action_completed') {
    return (
      <div className="text-xs font-mono text-emerald-300 py-0.5">
        <span className="text-slate-600 mr-2">[{timeStr}]</span>
        <span className="text-emerald-400 font-semibold">[ACTION:DONE]</span>{' '}
        <span>{event.description}</span>
        {event.duration_ms !== undefined && event.duration_ms !== null && (
          <span className="text-slate-400 ml-2">({event.duration_ms}ms)</span>
        )}
        {event.new_url && (
          <span className="text-slate-400 ml-2">→ {event.new_url}</span>
        )}
      </div>
    )
  }

  if (event.type === 'action_failed') {
    return (
      <div className="text-xs font-mono text-red-400 py-0.5">
        <span className="text-slate-600 mr-2">[{timeStr}]</span>
        <span className="text-red-500 font-semibold">[ACTION:FAIL]</span>{' '}
        <span>{event.description}</span>
      </div>
    )
  }

  if (event.type === 'observation') {
    return (
      <div className="text-xs font-mono text-slate-300 py-0.5">
        <span className="text-slate-600 mr-2">[{timeStr}]</span>
        <span className="text-indigo-400 font-semibold">[OBSERVE]</span>{' '}
        <span className="text-slate-100">{event.url || event.requested_url}</span>
        {event.title && <span className="text-slate-400"> — "{event.title}"</span>}
        {event.status_code && (
          <span className="text-emerald-400 ml-2">({event.status_code})</span>
        )}
        {event.element_count !== undefined && (
          <span className="text-slate-400 ml-2">
            · Discovered {event.element_count} interactive elements
          </span>
        )}
      </div>
    )
  }

  if (event.type === 'screenshot') {
    return (
      <div className="text-xs font-mono text-emerald-400/80 py-0.5">
        <span className="text-slate-600 mr-2">[{timeStr}]</span>
        <span>[SCREENSHOT]</span> Captured state snapshot
      </div>
    )
  }

  if (event.type === 'finding') {
    const color = SEVERITY_COLORS[event.severity ?? 'info'] ?? '#6b7280'
    return (
      <div className="text-xs font-mono py-0.5">
        <span className="text-slate-600 mr-2">[{timeStr}]</span>
        <span style={{ color }}>[{event.severity?.toUpperCase()}]</span>{' '}
        <span className="text-slate-300 font-medium">{event.category}: </span>
        <span className="text-slate-200">{event.description}</span>
      </div>
    )
  }

  return null
}

const REPRO_STATUS_COLORS: Record<string, string> = {
  not_attempted: '#6b7280',
  reproducing: '#6366f1',
  reproduced: '#ef4444',
  not_reproduced: '#22c55e',
  intermittent: '#f59e0b',
  failed: '#dc2626',
}

function ReproductionStatusBadge({ status }: { status?: string }) {
  const s = status || 'not_attempted'
  const color = REPRO_STATUS_COLORS[s] ?? '#6b7280'
  return (
    <span
      className="px-2.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider"
      style={{
        color,
        backgroundColor: `${color}18`,
        border: `1px solid ${color}40`,
      }}
    >
      {s.replace('_', ' ')}
    </span>
  )
}

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
  const [reproducing, setReproducing] = useState(false)
  const [reproAttempts, setReproAttempts] = useState<number>(1)
  const [latestReproduction, setLatestReproduction] = useState<ReproductionResult | null>(null)
  const [reproHistory, setReproHistory] = useState<ReproductionResult[]>([])
  const [reproError, setReproError] = useState<string | null>(null)

  const [analyzing, setAnalyzing] = useState(false)
  const [aiAnalysis, setAiAnalysis] = useState<any>(finding.ai_analysis || null)
  const [aiAnalysisError, setAiAnalysisError] = useState<string | null>(null)

  const handleRunAnalysis = async () => {
    setAnalyzing(true)
    setAiAnalysisError(null)
    try {
      const res = await api.analyzeFinding(testId, finding.id)
      setAiAnalysis(res)
      const updated = {
        ...finding,
        ai_analysis: res,
        recommendation: res.recommendation || finding.recommendation,
      }
      onFindingUpdated(updated)
    } catch (err: any) {
      setAiAnalysisError(err.message || 'AI analysis failed')
    } finally {
      setAnalyzing(false)
    }
  }

  // Load prior reproductions on mount
  useEffect(() => {
    if (finding.ai_analysis) {
      setAiAnalysis(finding.ai_analysis)
    }
    api.getReproductions(testId, finding.id)
      .then((reps) => {
        setReproHistory(reps)
        if (reps.length > 0) setLatestReproduction(reps[0])
      })
      .catch(() => {})
  }, [testId, finding.id, finding.ai_analysis])

  // Extract structured action sequence
  const actionSequence: string[] = (() => {
    if (finding.reproduction && Array.isArray(finding.reproduction.action_sequence)) {
      return finding.reproduction.action_sequence
    }
    if (finding.reproduction && Array.isArray(finding.reproduction.steps)) {
      return finding.reproduction.steps
    }
    return []
  })()

  const handleRunReproduction = async () => {
    setReproducing(true)
    setReproError(null)
    try {
      const res = await api.reproduceFinding(testId, finding.id, reproAttempts)
      setLatestReproduction(res)
      setReproHistory((prev) => [res, ...prev])

      // Determine updated status
      let newStatus = finding.status
      if (res.status === 'reproduced') {
        newStatus = 'confirmed'
      } else if (res.status === 'not_reproduced') {
        newStatus = 'unconfirmed'
      } else if (res.status === 'intermittent') {
        newStatus = 'investigating'
      }

      const updated = {
        ...finding,
        status: newStatus,
        reproductions: [res, ...(finding.reproductions || [])],
      }
      onFindingUpdated(updated)
    } catch (err: any) {
      setReproError(err.message || 'Reproduction failed to execute')
    } finally {
      setReproducing(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div
        className="w-full max-w-3xl rounded-xl border p-6 shadow-2xl space-y-6 my-8 max-h-[90vh] overflow-y-auto font-mono"
        style={{ background: '#111118', borderColor: '#2d2d3f' }}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 pb-4 border-b border-slate-800">
          <div>
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <FindingSeverityBadge severity={finding.severity} />
              <FindingStatusBadge status={finding.status} />
              <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 uppercase tracking-wider font-semibold">
                {finding.category}
              </span>
              {finding.confidence !== undefined && (
                <span className="px-2 py-0.5 rounded text-[10px] bg-indigo-950 text-indigo-300 border border-indigo-800/40">
                  {(finding.confidence * 100).toFixed(0)}% Confidence
                </span>
              )}
            </div>
            <h2 className="text-base font-bold text-slate-100 font-sans">{finding.title}</h2>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800 transition-colors shrink-0 text-sm"
          >
            ✕
          </button>
        </div>

        {/* AI Reasoning Layer (Gemini) */}
        <div className="p-4 rounded-lg bg-gradient-to-b from-purple-950/30 to-slate-950 border border-purple-800/40 space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <h3 className="text-xs uppercase text-purple-300 font-bold flex items-center gap-1.5">
                <span>✨ AI Reasoning & Root Cause Analysis</span>
                {aiAnalysis?.model_name && (
                  <span className="px-2 py-0.5 rounded text-[10px] bg-purple-900/60 text-purple-200 border border-purple-700/50 normal-case font-mono">
                    {aiAnalysis.model_name}
                  </span>
                )}
              </h3>
              <p className="text-[11px] text-slate-400 font-sans mt-0.5">
                Gemini analyzes empirical telemetry, separates observed facts from root-cause hypotheses, and provides remediation.
              </p>
            </div>
            <button
              onClick={handleRunAnalysis}
              disabled={analyzing}
              className="px-3.5 py-1.5 rounded text-xs font-semibold bg-purple-600 hover:bg-purple-500 text-white transition-colors disabled:opacity-50 flex items-center gap-1.5 shrink-0 shadow-lg shadow-purple-950/50"
            >
              {analyzing ? (
                <>
                  <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin inline-block" />
                  <span>Reasoning with Gemini...</span>
                </>
              ) : (
                <span>✨ {aiAnalysis ? 'Re-Analyze with AI' : 'Analyze with AI'}</span>
              )}
            </button>
          </div>

          {aiAnalysisError && (
            <div className="p-2.5 rounded bg-red-950/50 border border-red-900 text-red-300 text-xs font-sans">
              {aiAnalysisError}
            </div>
          )}

          {aiAnalysis && (
            <div className="space-y-3 pt-2 border-t border-purple-900/40 text-xs">
              {/* Status Header */}
              <div className="flex items-center justify-between flex-wrap gap-2 text-[11px]">
                <div className="flex items-center gap-2">
                  <span className="text-slate-400">Meaningful Finding:</span>
                  <span className={`px-2 py-0.5 rounded font-bold uppercase ${aiAnalysis.is_meaningful ? 'bg-emerald-950 text-emerald-300 border border-emerald-800/50' : 'bg-slate-800 text-slate-400'}`}>
                    {aiAnalysis.is_meaningful ? 'YES (Genuine Defect)' : 'NO (Benign Noise)'}
                  </span>
                </div>
                {aiAnalysis.severity_suggestion && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-400">AI Suggested Severity:</span>
                    <FindingSeverityBadge severity={aiAnalysis.severity_suggestion} />
                  </div>
                )}
                {aiAnalysis.confidence !== undefined && (
                  <span className="text-purple-300 font-semibold">
                    {(aiAnalysis.confidence * 100).toFixed(0)}% AI Confidence
                  </span>
                )}
              </div>

              {/* Error Warning if any */}
              {aiAnalysis.error && (
                <div className="p-2.5 rounded bg-amber-950/40 border border-amber-800/50 text-amber-300 text-[11px] font-sans">
                  <span className="font-bold">[{aiAnalysis.error.error_type}]:</span> {aiAnalysis.error.message}
                </div>
              )}

              {/* Explanation & Root Cause */}
              {aiAnalysis.explanation && (
                <div className="p-3 rounded bg-slate-900/80 border border-slate-800 space-y-1">
                  <span className="text-[10px] uppercase font-bold text-purple-300 block">AI Explanation & Mechanism</span>
                  <p className="text-slate-200 font-sans leading-relaxed text-xs">{aiAnalysis.explanation}</p>
                </div>
              )}

              {aiAnalysis.possible_cause && (
                <div className="p-3 rounded bg-slate-900/80 border border-slate-800 space-y-1">
                  <span className="text-[10px] uppercase font-bold text-indigo-300 block">Likely Technical Root Cause</span>
                  <p className="text-slate-200 font-sans leading-relaxed text-xs">{aiAnalysis.possible_cause}</p>
                </div>
              )}

              {/* Fact vs Hypothesis Breakdown Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                {/* Observed Facts */}
                <div className="p-3 rounded bg-slate-900/90 border border-emerald-900/40 space-y-2">
                  <span className="text-[10px] uppercase font-bold text-emerald-400 flex items-center gap-1">
                    <span>✓ Observed Empirical Facts</span>
                  </span>
                  <ul className="space-y-1.5 text-[11px] font-sans text-slate-300">
                    {(aiAnalysis.observed_facts && aiAnalysis.observed_facts.length > 0) ? (
                      aiAnalysis.observed_facts.map((fact: string, idx: number) => (
                        <li key={idx} className="flex items-start gap-1.5">
                          <span className="text-emerald-400 font-bold shrink-0">•</span>
                          <span>{fact}</span>
                        </li>
                      ))
                    ) : (
                      <li className="text-slate-500 italic">No specific facts isolated.</li>
                    )}
                  </ul>
                </div>

                {/* Hypotheses */}
                <div className="p-3 rounded bg-slate-900/90 border border-purple-900/40 space-y-2">
                  <span className="text-[10px] uppercase font-bold text-purple-400 flex items-center gap-1">
                    <span>💡 Root Cause Hypotheses</span>
                  </span>
                  <ul className="space-y-1.5 text-[11px] font-sans text-slate-300">
                    {(aiAnalysis.hypotheses && aiAnalysis.hypotheses.length > 0) ? (
                      aiAnalysis.hypotheses.map((hyp: string, idx: number) => (
                        <li key={idx} className="flex items-start gap-1.5">
                          <span className="text-purple-400 font-bold shrink-0">?</span>
                          <span>{hyp}</span>
                        </li>
                      ))
                    ) : (
                      <li className="text-slate-500 italic">No hypotheses generated.</li>
                    )}
                  </ul>
                </div>
              </div>

              {/* Uncertainty Callout */}
              {aiAnalysis.uncertainty && (
                <div className="p-2.5 rounded bg-amber-950/20 border border-amber-900/40 text-amber-200 text-[11px] font-sans flex items-start gap-2">
                  <span className="shrink-0 text-amber-400">⚠️</span>
                  <div>
                    <span className="font-bold text-amber-300 block mb-0.5">Uncertainty & Unknowns:</span>
                    <span>{aiAnalysis.uncertainty}</span>
                  </div>
                </div>
              )}

              {/* Actionable Recommendation */}
              {aiAnalysis.recommendation && (
                <div className="p-3 rounded bg-emerald-950/20 border border-emerald-900/40 space-y-1">
                  <span className="text-[10px] uppercase font-bold text-emerald-300 block">🛠 Remediation Guidance</span>
                  <p className="text-emerald-100 font-sans leading-relaxed text-xs">{aiAnalysis.recommendation}</p>
                </div>
              )}

              {/* Investigation Suggestions */}
              {aiAnalysis.investigation_suggestion && (
                <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-[11px] font-sans text-slate-300">
                  <span className="font-bold text-slate-400 block mb-0.5">🔍 Next Investigation Steps:</span>
                  <span>{aiAnalysis.investigation_suggestion}</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Deterministic Reproduction Section */}
        <div className="p-4 rounded-lg bg-indigo-950/20 border border-indigo-900/40 space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <h3 className="text-xs uppercase text-indigo-300 font-bold flex items-center gap-1.5">
                <span>🔄 Deterministic Issue Reproduction</span>
              </h3>
              <p className="text-[11px] text-slate-400 font-sans mt-0.5">
                Replays the exact structured action sequence in an isolated context to verify if the issue recurs.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <select
                value={reproAttempts}
                onChange={(e) => setReproAttempts(Number(e.target.value))}
                disabled={reproducing}
                className="bg-slate-900 border border-slate-700 text-slate-300 text-xs rounded px-2 py-1"
              >
                <option value={1}>1 Attempt (Quick)</option>
                <option value={3}>3 Attempts (Intermittency)</option>
              </select>
              <button
                onClick={handleRunReproduction}
                disabled={reproducing}
                className="px-3.5 py-1.5 rounded text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition-colors disabled:opacity-50 flex items-center gap-1.5"
              >
                {reproducing ? (
                  <>
                    <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin inline-block" />
                    <span>Replaying Actions...</span>
                  </>
                ) : (
                  <span>▶ Run Reproduction</span>
                )}
              </button>
            </div>
          </div>

          {reproError && (
            <div className="p-2.5 rounded bg-red-950/50 border border-red-900 text-red-300 text-xs">
              {reproError}
            </div>
          )}

          {/* Latest Reproduction Result */}
          {latestReproduction && (
            <div className="p-3 rounded bg-slate-950 border border-slate-800/90 space-y-2">
              <div className="flex items-center justify-between text-xs flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-slate-400">Reproduction Result:</span>
                  <ReproductionStatusBadge status={latestReproduction.status} />
                  <span className="text-slate-500 text-[11px]">
                    ({latestReproduction.successful_attempts}/{latestReproduction.attempts} attempts reproduced)
                  </span>
                </div>
                <span className="text-[10px] text-slate-500">
                  {new Date(latestReproduction.created_at).toLocaleTimeString()}
                </span>
              </div>

              {latestReproduction.error_message && (
                <p className="text-xs text-red-400 font-sans">{latestReproduction.error_message}</p>
              )}

              {latestReproduction.fresh_evidence && latestReproduction.fresh_evidence.length > 0 && (
                <div className="pt-2 border-t border-slate-800/60">
                  <span className="text-[10px] text-emerald-400 uppercase font-semibold block mb-1">
                    Fresh Telemetry Captured During Replay ({latestReproduction.fresh_evidence.length} items)
                  </span>
                  <div className="space-y-1 max-h-24 overflow-y-auto">
                    {latestReproduction.fresh_evidence.map((ev: Record<string, any>, idx: number) => (
                      <div key={idx} className="text-[11px] text-slate-300 p-1.5 rounded bg-slate-900/60 flex items-center justify-between">
                        <span>{ev.type || 'Signal'}: {ev.message || ev.error || ev.url || `Status ${ev.status_code}`}</span>
                        <span className="text-emerald-400 text-[10px] font-bold">MATCHED</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Action Sequence Section */}
        <div>
          <h3 className="text-xs uppercase text-slate-400 font-semibold mb-2">
            Structured Action Replay Sequence ({actionSequence.length || 1} steps)
          </h3>
          {actionSequence.length === 0 ? (
            <div className="p-2.5 rounded bg-slate-950 border border-slate-800 text-xs text-slate-400">
              <code>NAVIGATE("{finding.evidence?.[0]?.url || 'TARGET_URL'}")</code>
            </div>
          ) : (
            <div className="space-y-1.5 p-3 rounded bg-slate-950 border border-slate-800 max-h-36 overflow-y-auto">
              {actionSequence.map((step, idx) => (
                <div key={idx} className="flex items-center gap-2 text-xs">
                  <span className="text-slate-600 text-[10px] w-5 text-right">{idx + 1}.</span>
                  <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-indigo-300 font-mono text-[11px]">
                    {step}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Description */}
        <div>
          <h3 className="text-xs uppercase text-slate-500 font-semibold mb-1">Description</h3>
          <p className="text-xs text-slate-300 font-sans whitespace-pre-wrap leading-relaxed bg-slate-950/60 p-3 rounded border border-slate-800/80">
            {finding.description || 'No description provided.'}
          </p>
        </div>

        {/* Recommendation */}
        {finding.recommendation && (
          <div>
            <h3 className="text-xs uppercase text-amber-400 font-semibold mb-1 flex items-center gap-1.5">
              <span>💡 Actionable Recommendation</span>
            </h3>
            <div className="text-xs text-amber-200/90 font-sans leading-relaxed bg-amber-950/20 p-3 rounded border border-amber-800/30">
              {finding.recommendation}
            </div>
          </div>
        )}

        {/* Fingerprint */}
        {finding.fingerprint && (
          <div>
            <h3 className="text-xs uppercase text-slate-500 font-semibold mb-1">Stable Fingerprint (SHA-256)</h3>
            <div className="text-[11px] text-indigo-300/90 bg-slate-950 p-2.5 rounded border border-slate-800 break-all">
              {finding.fingerprint}
            </div>
          </div>
        )}

        {/* Evidence Timeline */}
        <div>
          <h3 className="text-xs uppercase text-slate-400 font-semibold mb-2">
            Evidence Timeline ({finding.evidence?.length || 0} occurrence{finding.evidence?.length !== 1 ? 's' : ''})
          </h3>
          {(!finding.evidence || finding.evidence.length === 0) ? (
            <p className="text-xs text-slate-600">No raw evidence items attached.</p>
          ) : (
            <div className="space-y-3">
              {finding.evidence.map((ev, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-lg border bg-slate-950/80 border-slate-800/90 space-y-2 text-xs"
                >
                  <div className="flex items-center justify-between text-slate-400 border-b border-slate-800/50 pb-1.5">
                    <span className="font-semibold text-indigo-400 uppercase text-[10px]">
                      Evidence #{idx + 1} — {ev.type || 'Signal'}
                    </span>
                    {ev.timestamp && <span className="text-[10px] text-slate-500">{ev.timestamp}</span>}
                  </div>

                  {ev.url && (
                    <div className="flex items-baseline gap-2">
                      <span className="text-slate-500 text-[10px] shrink-0">URL:</span>
                      <span className="text-slate-200 break-all">{ev.url}</span>
                    </div>
                  )}

                  {ev.status_code && (
                    <div className="flex items-center gap-2">
                      <span className="text-slate-500 text-[10px]">Status:</span>
                      <StatusCodeBadge code={ev.status_code} />
                    </div>
                  )}

                  {ev.failure_text && (
                    <div className="flex items-baseline gap-2">
                      <span className="text-red-400 text-[10px] shrink-0">Error:</span>
                      <span className="text-red-300">{ev.failure_text}</span>
                    </div>
                  )}

                  {ev.message && (
                    <div className="flex items-baseline gap-2">
                      <span className="text-amber-400 text-[10px] shrink-0">Message:</span>
                      <span className="text-amber-200 break-all">{ev.message}</span>
                    </div>
                  )}

                  {ev.stack && (
                    <div>
                      <span className="text-slate-500 text-[10px] block mb-1">Stack Trace:</span>
                      <pre className="p-2 rounded bg-black/60 text-red-300 text-[10px] overflow-x-auto whitespace-pre-wrap border border-red-950/60">
                        {ev.stack}
                      </pre>
                    </div>
                  )}

                  {ev.text && (
                    <div className="text-slate-300 bg-slate-900/50 p-2 rounded">
                      {ev.text}
                    </div>
                  )}

                  {ev.screenshot_path && (
                    <div className="text-[10px] text-emerald-400/80">
                      📸 Viewport snapshot recorded at time of discovery
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="pt-3 border-t border-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

export function Test() {
  const { id } = useParams<{ id: string }>()
  const [test, setTest] = useState<Test | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [liveScreenshotUrl, setLiveScreenshotUrl] = useState<string | null>(null)
  const [liveCurrentUrl, setLiveCurrentUrl] = useState<string | null>(null)
  const [liveTitle, setLiveTitle] = useState<string | null>(null)
  const [liveStatusCode, setLiveStatusCode] = useState<number | null>(null)
  const [liveDurationMs, setLiveDurationMs] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState<'telemetry' | 'findings' | 'actions' | 'elements' | 'signals' | 'state'>('telemetry')
  const [elementFilter, setElementFilter] = useState<string>('all')
  const [findingCategoryFilter, setFindingCategoryFilter] = useState<string>('all')

  const [liveActions, setLiveActions] = useState<ActionItem[]>([])
  const [liveFindings, setLiveFindings] = useState<Finding[]>([])
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null)
  const [liveElements, setLiveElements] = useState<InteractiveElement[]>([])
  const [liveConsoleMessages, setLiveConsoleMessages] = useState<ConsoleMessage[]>([])
  const [liveJsExceptions, setLiveJsExceptions] = useState<JavaScriptException[]>([])
  const [liveFailedRequests, setLiveFailedRequests] = useState<FailedRequest[]>([])
  const [liveFingerprint, setLiveFingerprint] = useState<string | null>(null)
  const [liveViewport, setLiveViewport] = useState<{ width: number; height: number } | null>(null)
  const [liveDimensions, setLiveDimensions] = useState<{ width: number; height: number } | null>(null)
  const [discoveredStatesCount, setDiscoveredStatesCount] = useState<number>(0)

  const { events } = useTestEvents(id ?? null)
  const logRef = useRef<HTMLDivElement>(null)

  // Initial fetch
  useEffect(() => {
    if (!id) return
    api.getTest(id)
      .then((data) => {
        setTest(data)
        if (data.screenshot_url) setLiveScreenshotUrl(data.screenshot_url)
        if (data.current_url) setLiveCurrentUrl(data.current_url)
        if (data.page_title) setLiveTitle(data.page_title)
        if (data.status_code) setLiveStatusCode(data.status_code)
        if (data.duration_ms) setLiveDurationMs(data.duration_ms)
        if (data.actions) setLiveActions(data.actions)
        if (data.findings) setLiveFindings(data.findings)

        if (data.observations && data.observations.length > 0) {
          setDiscoveredStatesCount(data.observations.length)
          const latest = data.observations[data.observations.length - 1]
          if (latest.elements_data) setLiveElements(latest.elements_data)
          if (latest.console_messages) setLiveConsoleMessages(latest.console_messages)
          if (latest.js_exceptions) setLiveJsExceptions(latest.js_exceptions)
          if (latest.failed_requests) setLiveFailedRequests(latest.failed_requests)
          if (latest.fingerprint) setLiveFingerprint(latest.fingerprint)
          if (latest.viewport) setLiveViewport(latest.viewport)
          if (latest.page_dimensions) setLiveDimensions(latest.page_dimensions)
        }
      })
      .catch((e) => setLoadError(e.message))
  }, [id])

  // Auto-scroll log to bottom
  useEffect(() => {
    const el = logRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [events])

  // Process live events from SSE
  useEffect(() => {
    if (!events.length) return
    const last = events[events.length - 1]

    if (last.type === 'action_completed' || last.type === 'action_failed') {
      const newAction: ActionItem = {
        id: `act-${Date.now()}`,
        action_type: last.action_type || 'UNKNOWN',
        target: last.target,
        value: last.value,
        description: last.description,
        success: last.type === 'action_completed',
        error: last.error,
        duration_ms: last.duration_ms,
        timestamp: new Date().toISOString(),
      }
      setLiveActions((prev) => [...prev, newAction])
      if (last.new_url) setLiveCurrentUrl(last.new_url)
    } else if (last.type === 'observation') {
      if (last.url) setLiveCurrentUrl(last.url)
      if (last.title) setLiveTitle(last.title)
      if (last.status_code) setLiveStatusCode(last.status_code)
      if (last.duration_ms) setLiveDurationMs(last.duration_ms)
      if (last.screenshot_url) setLiveScreenshotUrl(`${last.screenshot_url}?t=${Date.now()}`)
      if (last.elements) setLiveElements(last.elements)
      if (last.console_messages) setLiveConsoleMessages(last.console_messages)
      if (last.js_exceptions) setLiveJsExceptions(last.js_exceptions)
      if (last.failed_requests) setLiveFailedRequests(last.failed_requests)
      if (last.fingerprint) setLiveFingerprint(last.fingerprint)
      if (last.viewport) setLiveViewport(last.viewport)
      if (last.page_dimensions) setLiveDimensions(last.page_dimensions)
      setDiscoveredStatesCount((prev) => prev + 1)
    } else if (last.type === 'finding') {
      const findingId = last.id || `find-${Date.now()}`
      const incomingFinding: Finding = {
        id: findingId,
        severity: last.severity || 'medium',
        category: last.category || 'other',
        status: last.status || 'potential',
        confidence: last.confidence ?? 0.85,
        title: last.title || 'Detected Finding',
        description: last.description || '',
        evidence: last.evidence || [],
        reproduction: last.reproduction,
        recommendation: last.recommendation,
        fingerprint: last.fingerprint,
        timestamp: new Date().toISOString(),
      }
      setLiveFindings((prev) => {
        const matchIdx = prev.findIndex(
          (f) => (incomingFinding.fingerprint && f.fingerprint === incomingFinding.fingerprint) || f.id === incomingFinding.id
        )
        if (matchIdx >= 0) {
          const updated = [...prev]
          const existing = updated[matchIdx]
          updated[matchIdx] = {
            ...existing,
            ...incomingFinding,
            evidence: [...(existing.evidence || []), ...(incomingFinding.evidence || [])],
          }
          return updated
        }
        return [...prev, incomingFinding]
      })
    } else if (last.type === 'finding_reproduced' && last.finding_id) {
      setLiveFindings((prev) =>
        prev.map((f) => {
          if (f.id === last.finding_id) {
            return {
              ...f,
              status: last.status || f.status,
            }
          }
          return f
        })
      )
    } else if (last.type === 'finding_analyzed' && last.finding_id) {
      setLiveFindings((prev) =>
        prev.map((f) => {
          if (f.id === last.finding_id) {
            return {
              ...f,
              ai_analysis: (last as any).ai_analysis || f.ai_analysis,
            }
          }
          return f
        })
      )
    } else if (last.type === 'test_analyzed' && (last as any).ai_summary) {
      setTest((prev) => (prev ? { ...prev, ai_summary: (last as any).ai_summary } : prev))
    } else if (last.type === 'screenshot' && last.url) {
      setLiveScreenshotUrl(`${last.url}?t=${Date.now()}`)
    } else if (last.type === 'status') {
      if (last.current_url) setLiveCurrentUrl(last.current_url)
      if (last.page_title) setLiveTitle(last.page_title)
      if (last.status_code) setLiveStatusCode(last.status_code)
      if (last.duration_ms) setLiveDurationMs(last.duration_ms)
      if (last.screenshot_url) setLiveScreenshotUrl(`${last.screenshot_url}?t=${Date.now()}`)
      if (last.states_count !== undefined) setDiscoveredStatesCount(last.states_count)

      if (id) {
        api.getTest(id).then(setTest).catch(() => {})
      }
    }
  }, [events, id])

  const handleCancel = async () => {
    if (!id) return
    try {
      await api.cancelTest(id)
      const updated = await api.getTest(id)
      setTest(updated)
    } catch (e) {
      console.error(e)
    }
  }

  if (loadError) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <p className="text-red-400 font-mono text-sm mb-3">{loadError}</p>
          <Link to="/" className="text-xs font-mono text-indigo-400 hover:underline">← Back to Home</Link>
        </div>
      </div>
    )
  }

  if (!test) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <span className="text-xs font-mono text-slate-500 animate-pulse">Loading PROBE session...</span>
      </div>
    )
  }

  const isActive = test.status === 'running'
  const displayUrl = liveCurrentUrl || test.current_url || test.url
  const displayTitle = liveTitle || test.page_title || '—'
  const displayStatusCode = liveStatusCode ?? test.status_code
  const displayDuration = liveDurationMs !== null && liveDurationMs !== undefined
    ? `${(liveDurationMs / 1000).toFixed(2)}s (${liveDurationMs}ms)`
    : test.completed_at && test.started_at
    ? `${((new Date(test.completed_at).getTime() - new Date(test.started_at).getTime()) / 1000).toFixed(2)}s`
    : '—'

  const screenshotSrc = liveScreenshotUrl || test.screenshot_url

  // Filter elements
  const filteredElements = liveElements.filter((el) => {
    if (elementFilter === 'all') return true
    if (elementFilter === 'links') return el.type === 'link'
    if (elementFilter === 'buttons') return el.type === 'button'
    if (elementFilter === 'inputs') return el.type.startsWith('input') || el.type === 'textarea' || el.type === 'select'
    return true
  })

  // Filter findings
  const filteredFindings = liveFindings.filter((f) => {
    if (findingCategoryFilter === 'all') return true
    return f.category === findingCategoryFilter
  })

  const uniqueCategories = Array.from(new Set(liveFindings.map((f) => f.category))).filter(Boolean)

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 mb-6">
        <Link to="/history" className="text-xs font-mono text-slate-500 hover:text-slate-300">
          Tests
        </Link>
        <span className="text-slate-700 text-xs">/</span>
        <span className="text-xs font-mono text-slate-400 truncate max-w-xs">{test.id}</span>
      </div>

      {/* Main Test Details Card */}
      <div
        className="rounded-lg border p-6 mb-6 shadow-lg"
        style={{ background: '#111118', borderColor: '#1e1e2e' }}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3 mb-3">
              <StatusBadge status={test.status} />
              <StatusCodeBadge code={displayStatusCode} />
              <span className="text-xs font-mono text-slate-500">
                {test.platform.toUpperCase()} · {new Date(test.created_at).toLocaleTimeString()}
              </span>
            </div>

            {/* Target & Current URL */}
            <div className="space-y-1">
              <div className="flex items-baseline gap-2">
                <span className="text-xs font-mono text-slate-500 shrink-0">TARGET:</span>
                <span className="text-sm font-mono text-indigo-300 break-all">{test.url}</span>
              </div>
              {displayUrl && displayUrl !== test.url && (
                <div className="flex items-baseline gap-2">
                  <span className="text-xs font-mono text-slate-500 shrink-0">CURRENT:</span>
                  <span className="text-sm font-mono text-emerald-400 break-all">{displayUrl}</span>
                </div>
              )}
              <div className="flex items-baseline gap-2">
                <span className="text-xs font-mono text-slate-500 shrink-0">TITLE:</span>
                <span className="text-sm font-medium text-slate-200">{displayTitle}</span>
              </div>
            </div>

            {test.error_message && (
              <div className="mt-3 p-3 rounded bg-red-950/40 border border-red-900/50">
                <p className="text-xs font-mono text-red-400">{test.error_message}</p>
              </div>
            )}
          </div>

          {isActive && (
            <button
              onClick={handleCancel}
              className="shrink-0 px-3.5 py-1.5 rounded text-xs font-mono border transition-colors hover:bg-red-950 hover:border-red-800"
              style={{ borderColor: '#2d1f1f', color: '#ef4444' }}
            >
              Cancel Test
            </button>
          )}
        </div>

        {/* Telemetry Stats Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 mt-6 pt-5 border-t" style={{ borderColor: '#1e1e2e' }}>
          <Stat label="Status" value={test.status.toUpperCase()} />
          <Stat label="Actions Executed" value={liveActions.length} />
          <Stat label="States Discovered" value={discoveredStatesCount || 1} />
          <Stat label="Elements in State" value={liveElements.length} />
          <Stat label="Findings Detected" value={liveFindings.length} />
        </div>
      </div>

      {/* Observation Tabs Bar */}
      <div className="flex items-center gap-2 border-b mb-6 pb-2 overflow-x-auto" style={{ borderColor: '#1e1e2e' }}>
        <button
          onClick={() => setActiveTab('telemetry')}
          className={`px-3 py-1.5 rounded text-xs font-mono transition-colors shrink-0 ${
            activeTab === 'telemetry'
              ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Viewport & Live Stream
        </button>
        <button
          onClick={() => setActiveTab('findings')}
          className={`px-3 py-1.5 rounded text-xs font-mono transition-colors shrink-0 ${
            activeTab === 'findings'
              ? 'bg-red-600/20 text-red-400 border border-red-500/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Detected Findings ({liveFindings.length})
        </button>
        <button
          onClick={() => setActiveTab('actions')}
          className={`px-3 py-1.5 rounded text-xs font-mono transition-colors shrink-0 ${
            activeTab === 'actions'
              ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Executed Actions ({liveActions.length})
        </button>
        <button
          onClick={() => setActiveTab('elements')}
          className={`px-3 py-1.5 rounded text-xs font-mono transition-colors shrink-0 ${
            activeTab === 'elements'
              ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Interactive Elements ({liveElements.length})
        </button>
        <button
          onClick={() => setActiveTab('signals')}
          className={`px-3 py-1.5 rounded text-xs font-mono transition-colors shrink-0 ${
            activeTab === 'signals'
              ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Browser Signals ({liveConsoleMessages.length + liveJsExceptions.length + liveFailedRequests.length})
        </button>
        <button
          onClick={() => setActiveTab('state')}
          className={`px-3 py-1.5 rounded text-xs font-mono transition-colors shrink-0 ${
            activeTab === 'state'
              ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          State & Fingerprint
        </button>
      </div>

      {/* TAB 1: Viewport & Live Stream */}
      {activeTab === 'telemetry' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Screenshot Viewer */}
          <div
            className="rounded-lg border flex flex-col overflow-hidden"
            style={{ background: '#0d0d15', borderColor: '#1e1e2e' }}
          >
            <div
              className="px-4 py-2.5 border-b flex items-center justify-between"
              style={{ borderColor: '#1e1e2e', background: '#111118' }}
            >
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500/80 inline-block"></span>
                <span className="w-2.5 h-2.5 rounded-full bg-yellow-500/80 inline-block"></span>
                <span className="w-2.5 h-2.5 rounded-full bg-green-500/80 inline-block"></span>
                <span className="text-xs font-mono text-slate-400 font-semibold ml-1">
                  Chromium Viewport {liveViewport ? `(${liveViewport.width}×${liveViewport.height})` : ''}
                </span>
              </div>
              {screenshotSrc && (
                <a
                  href={screenshotSrc}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs font-mono text-indigo-400 hover:underline"
                >
                  Open Fullscreen ↗
                </a>
              )}
            </div>

            <div className="p-4 flex-1 flex items-center justify-center min-h-[280px] bg-slate-950/60">
              {screenshotSrc ? (
                <div className="relative group w-full rounded border border-slate-800/80 overflow-hidden shadow-md">
                  <img
                    src={screenshotSrc}
                    alt="Captured Chromium Viewport"
                    className="w-full h-auto object-cover max-h-[380px]"
                  />
                </div>
              ) : isActive ? (
                <div className="text-center py-12">
                  <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
                  <p className="text-xs font-mono text-slate-400">Autonomous exploration in progress...</p>
                </div>
              ) : (
                <div className="text-center py-12">
                  <p className="text-xs font-mono text-slate-600">No viewport screenshot captured</p>
                </div>
              )}
            </div>
          </div>

          {/* Live Event Stream */}
          <div
            className="rounded-lg border flex flex-col"
            style={{ background: '#0d0d15', borderColor: '#1e1e2e' }}
          >
            <div
              className="px-4 py-2.5 border-b flex items-center justify-between"
              style={{ borderColor: '#1e1e2e', background: '#111118' }}
            >
              <span className="text-xs font-mono text-slate-400 font-semibold uppercase tracking-wider">
                Autonomous Action Stream
              </span>
              {isActive && (
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
                  <span className="text-xs font-mono text-indigo-400">exploring</span>
                </span>
              )}
            </div>
            <div
              ref={logRef}
              className="p-4 max-h-[380px] min-h-[280px] overflow-y-auto font-mono space-y-1.5"
            >
              {events.length === 0 ? (
                <p className="text-xs font-mono text-slate-600">Connecting to autonomous test execution...</p>
              ) : (
                events.map((e, i) => <EventRow key={i} event={e} />)
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: Detected Findings */}
      {activeTab === 'findings' && (
        <div className="rounded-lg border mb-6 overflow-hidden" style={{ background: '#111118', borderColor: '#1e1e2e' }}>
          <div className="px-4 py-3 border-b flex items-center justify-between flex-wrap gap-2" style={{ borderColor: '#1e1e2e' }}>
            <span className="text-xs font-mono text-slate-400 uppercase tracking-wider font-semibold">
              Detected Issues & Findings ({filteredFindings.length})
            </span>
            <div className="flex gap-1.5 flex-wrap">
              <button
                onClick={() => setFindingCategoryFilter('all')}
                className={`px-2.5 py-1 rounded text-xs font-mono capitalize transition-colors ${
                  findingCategoryFilter === 'all'
                    ? 'bg-red-600 text-white font-semibold'
                    : 'bg-slate-800/60 text-slate-400 hover:text-slate-200'
                }`}
              >
                All
              </button>
              {uniqueCategories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setFindingCategoryFilter(cat)}
                  className={`px-2.5 py-1 rounded text-xs font-mono capitalize transition-colors ${
                    findingCategoryFilter === cat
                      ? 'bg-red-600 text-white font-semibold'
                      : 'bg-slate-800/60 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          <div className="max-h-[550px] overflow-y-auto">
            {filteredFindings.length === 0 ? (
              <div className="p-8 text-center text-xs font-mono text-slate-500">
                No issues detected matching the selected filter.
              </div>
            ) : (
              <div className="divide-y divide-slate-800/60">
                {filteredFindings.map((f, i) => (
                  <div
                    key={f.id || i}
                    onClick={() => setSelectedFinding(f)}
                    className="p-4 hover:bg-slate-900/50 cursor-pointer transition-colors space-y-2 group"
                  >
                    <div className="flex items-center justify-between gap-3 flex-wrap">
                      <div className="flex items-center gap-2 flex-wrap">
                        <FindingSeverityBadge severity={f.severity} />
                        <FindingStatusBadge status={f.status} />
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-400 uppercase">
                          {f.category}
                        </span>
                        {f.ai_analysis && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-purple-950 text-purple-300 border border-purple-800/40">
                            ✨ AI Analyzed
                          </span>
                        )}
                        {f.confidence !== undefined && (
                          <span className="text-[10px] font-mono text-indigo-400">
                            {(f.confidence * 100).toFixed(0)}% conf
                          </span>
                        )}
                        <span className="text-xs font-mono text-slate-100 font-semibold group-hover:text-indigo-300 transition-colors">
                          {f.title}
                        </span>
                      </div>
                      <span className="text-[11px] font-mono text-slate-500 group-hover:text-slate-300">
                        Inspect Evidence ({f.evidence?.length || 0}) ↗
                      </span>
                    </div>

                    <p className="text-xs text-slate-400 font-sans line-clamp-2">{f.description}</p>

                    {f.recommendation && (
                      <p className="text-[11px] text-amber-300/80 font-mono line-clamp-1">
                        💡 {f.recommendation}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: Executed Actions */}
      {activeTab === 'actions' && (
        <div className="rounded-lg border mb-6 overflow-hidden" style={{ background: '#111118', borderColor: '#1e1e2e' }}>
          <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: '#1e1e2e' }}>
            <span className="text-xs font-mono text-slate-400 uppercase tracking-wider font-semibold">
              Executed Action History ({liveActions.length})
            </span>
          </div>
          <div className="max-h-[500px] overflow-y-auto">
            {liveActions.length === 0 ? (
              <div className="p-8 text-center text-xs font-mono text-slate-500">
                No actions executed yet.
              </div>
            ) : (
              <table className="w-full text-left text-xs font-mono">
                <thead className="sticky top-0 bg-[#0d0d15] border-b" style={{ borderColor: '#1e1e2e' }}>
                  <tr className="text-slate-400">
                    <th className="px-4 py-2.5">#</th>
                    <th className="px-4 py-2.5">Type</th>
                    <th className="px-4 py-2.5">Description</th>
                    <th className="px-4 py-2.5">Target / Selector</th>
                    <th className="px-4 py-2.5">Duration</th>
                    <th className="px-4 py-2.5">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: '#1a1a28' }}>
                  {liveActions.map((act, i) => (
                    <tr key={i} className="hover:bg-slate-900/40 transition-colors">
                      <td className="px-4 py-2.5 text-slate-500">{i + 1}</td>
                      <td className="px-4 py-2.5">
                        <span className="px-2 py-0.5 rounded bg-indigo-950/80 text-indigo-300 border border-indigo-800/40">
                          {act.action_type}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-slate-200 font-medium">
                        {act.description || act.value || '—'}
                      </td>
                      <td className="px-4 py-2.5 text-slate-400 max-w-xs truncate" title={act.target || ''}>
                        {act.target || '—'}
                      </td>
                      <td className="px-4 py-2.5 text-slate-400">
                        {act.duration_ms !== null && act.duration_ms !== undefined ? `${act.duration_ms}ms` : '—'}
                      </td>
                      <td className="px-4 py-2.5">
                        {act.success ? (
                          <span className="text-emerald-400 font-semibold">SUCCESS</span>
                        ) : (
                          <span className="text-red-400 font-semibold" title={act.error || ''}>
                            FAILED
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: Interactive Elements */}
      {activeTab === 'elements' && (
        <div className="rounded-lg border mb-6 overflow-hidden" style={{ background: '#111118', borderColor: '#1e1e2e' }}>
          <div className="px-4 py-3 border-b flex items-center justify-between flex-wrap gap-2" style={{ borderColor: '#1e1e2e' }}>
            <span className="text-xs font-mono text-slate-400 uppercase tracking-wider font-semibold">
              Discovered UI Elements in Current State ({filteredElements.length})
            </span>
            <div className="flex gap-2">
              {['all', 'links', 'buttons', 'inputs'].map((filter) => (
                <button
                  key={filter}
                  onClick={() => setElementFilter(filter)}
                  className={`px-2.5 py-1 rounded text-xs font-mono capitalize transition-colors ${
                    elementFilter === filter
                      ? 'bg-indigo-600 text-white font-semibold'
                      : 'bg-slate-800/60 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {filter}
                </button>
              ))}
            </div>
          </div>
          <div className="max-h-[500px] overflow-y-auto">
            {filteredElements.length === 0 ? (
              <div className="p-8 text-center text-xs font-mono text-slate-500">
                No interactive elements discovered on this page yet.
              </div>
            ) : (
              <table className="w-full text-left text-xs font-mono">
                <thead className="sticky top-0 bg-[#0d0d15] border-b" style={{ borderColor: '#1e1e2e' }}>
                  <tr className="text-slate-400">
                    <th className="px-4 py-2.5">Type</th>
                    <th className="px-4 py-2.5">Role</th>
                    <th className="px-4 py-2.5">Text / Label</th>
                    <th className="px-4 py-2.5">Selector / Reference</th>
                    <th className="px-4 py-2.5">State</th>
                    <th className="px-4 py-2.5">Bounds</th>
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: '#1a1a28' }}>
                  {filteredElements.map((el, i) => (
                    <tr key={i} className="hover:bg-slate-900/40 transition-colors">
                      <td className="px-4 py-2.5">
                        <span className="px-2 py-0.5 rounded bg-indigo-950/80 text-indigo-300 border border-indigo-800/40">
                          {el.type}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-slate-400">{el.role || '—'}</td>
                      <td className="px-4 py-2.5 text-slate-200 max-w-xs truncate">
                        {el.text || el.label || <span className="text-slate-600">—</span>}
                      </td>
                      <td className="px-4 py-2.5 text-slate-400 max-w-xs truncate font-mono" title={el.reference}>
                        {el.reference || el.tag}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`inline-block w-2 h-2 rounded-full mr-1.5 ${el.visible ? 'bg-emerald-400' : 'bg-slate-600'}`} />
                        <span className={el.visible ? 'text-emerald-400' : 'text-slate-500'}>
                          {el.visible ? 'Visible' : 'Hidden'}
                        </span>
                        {!el.enabled && <span className="ml-1.5 text-amber-400">(Disabled)</span>}
                      </td>
                      <td className="px-4 py-2.5 text-slate-500">
                        {el.bounding_box ? `${el.bounding_box.width}×${el.bounding_box.height}` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* TAB 5: Browser Signals */}
      {activeTab === 'signals' && (
        <div className="space-y-6 mb-6">
          {/* Console Messages */}
          <div className="rounded-lg border p-4" style={{ background: '#111118', borderColor: '#1e1e2e' }}>
            <h3 className="text-xs font-mono text-slate-400 uppercase tracking-wider font-semibold mb-3">
              Console Messages ({liveConsoleMessages.length})
            </h3>
            {liveConsoleMessages.length === 0 ? (
              <p className="text-xs font-mono text-slate-600">No console output recorded.</p>
            ) : (
              <div className="space-y-1.5 max-h-[220px] overflow-y-auto font-mono text-xs">
                {liveConsoleMessages.map((msg, i) => {
                  const isErr = msg.level === 'error'
                  const isWarn = msg.level === 'warn' || msg.level === 'warning'
                  const color = isErr ? 'text-red-400 bg-red-950/30 border-red-900/40' : isWarn ? 'text-amber-400 bg-amber-950/30 border-amber-900/40' : 'text-slate-300 bg-slate-900/40 border-slate-800/40'
                  return (
                    <div key={i} className={`p-2 rounded border ${color} flex items-start justify-between gap-2`}>
                      <div>
                        <span className="font-semibold uppercase mr-2">[{msg.level}]</span>
                        <span>{msg.text}</span>
                      </div>
                      {msg.location && <span className="text-slate-500 shrink-0 text-[10px]">{msg.location}</span>}
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Uncaught JS Exceptions */}
          <div className="rounded-lg border p-4" style={{ background: '#111118', borderColor: '#1e1e2e' }}>
            <h3 className="text-xs font-mono text-slate-400 uppercase tracking-wider font-semibold mb-3">
              Uncaught JavaScript Exceptions ({liveJsExceptions.length})
            </h3>
            {liveJsExceptions.length === 0 ? (
              <p className="text-xs font-mono text-slate-600">No uncaught JavaScript exceptions.</p>
            ) : (
              <div className="space-y-2 max-h-[200px] overflow-y-auto font-mono text-xs">
                {liveJsExceptions.map((ex, i) => (
                  <div key={i} className="p-3 rounded bg-red-950/40 border border-red-900/60">
                    <p className="text-red-400 font-semibold">{ex.message}</p>
                    {ex.stack && <pre className="text-[10px] text-red-300/80 mt-1 whitespace-pre-wrap">{ex.stack}</pre>}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Failed Network Requests */}
          <div className="rounded-lg border p-4" style={{ background: '#111118', borderColor: '#1e1e2e' }}>
            <h3 className="text-xs font-mono text-slate-400 uppercase tracking-wider font-semibold mb-3">
              Failed Network Requests ({liveFailedRequests.length})
            </h3>
            {liveFailedRequests.length === 0 ? (
              <p className="text-xs font-mono text-slate-600">No failed network requests.</p>
            ) : (
              <div className="space-y-1.5 max-h-[200px] overflow-y-auto font-mono text-xs">
                {liveFailedRequests.map((req, i) => (
                  <div key={i} className="p-2.5 rounded bg-amber-950/30 border border-amber-900/40 flex items-center justify-between">
                    <div>
                      <span className="font-semibold text-amber-400 mr-2">{req.method}</span>
                      <span className="text-slate-200">{req.url}</span>
                    </div>
                    <span className="text-red-400 text-xs shrink-0 ml-2">{req.failure_text}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 6: State & Fingerprint */}
      {activeTab === 'state' && (
        <div className="rounded-lg border p-6 mb-6 space-y-4" style={{ background: '#111118', borderColor: '#1e1e2e' }}>
          <div>
            <h3 className="text-xs font-mono text-slate-500 uppercase mb-1">State Fingerprint (SHA-256)</h3>
            <div className="p-2.5 rounded bg-slate-950 border border-slate-800 font-mono text-xs text-indigo-300 break-all">
              {liveFingerprint || '—'}
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <div>
              <h4 className="text-xs font-mono text-slate-500 uppercase mb-1">Viewport Dimensions</h4>
              <p className="text-sm font-mono text-slate-200">
                {liveViewport ? `${liveViewport.width}px × ${liveViewport.height}px` : '1280px × 720px'}
              </p>
            </div>
            <div>
              <h4 className="text-xs font-mono text-slate-500 uppercase mb-1">Total Page Dimensions</h4>
              <p className="text-sm font-mono text-slate-200">
                {liveDimensions ? `${liveDimensions.width}px × ${liveDimensions.height}px` : '—'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Overview Findings Section (always visible summary below tabs) */}
      {liveFindings.length > 0 && activeTab !== 'findings' && (
        <div className="mt-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-mono text-slate-400 uppercase tracking-wider font-semibold">
              Detected Findings ({liveFindings.length})
            </h2>
            <button
              onClick={() => setActiveTab('findings')}
              className="text-xs font-mono text-indigo-400 hover:underline"
            >
              View All in Findings Tab →
            </button>
          </div>
          <div className="space-y-2">
            {liveFindings.slice(0, 5).map((f, i) => (
              <div
                key={f.id || i}
                onClick={() => setSelectedFinding(f)}
                className="rounded border px-4 py-3 cursor-pointer hover:border-slate-700 transition-colors"
                style={{ background: '#111118', borderColor: '#1e1e2e' }}
              >
                <div className="flex items-center justify-between gap-2 mb-1 flex-wrap">
                  <div className="flex items-center gap-2">
                    <FindingSeverityBadge severity={f.severity} />
                    <FindingStatusBadge status={f.status} />
                    <span className="text-xs font-mono text-slate-400">{f.category}</span>
                    <span className="text-xs font-mono text-slate-200 font-semibold">— {f.title}</span>
                  </div>
                  <span className="text-[10px] font-mono text-indigo-400">Click to inspect ↗</span>
                </div>
                <p className="text-xs text-slate-300 font-sans line-clamp-1">{f.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Interactive Modal Drawer */}
      {selectedFinding && test && (
        <FindingDetailModal
          finding={selectedFinding}
          testId={test.id}
          onClose={() => setSelectedFinding(null)}
          onFindingUpdated={(updated) => {
            setSelectedFinding(updated)
            setLiveFindings((prev) =>
              prev.map((f) => (f.id === updated.id ? updated : f))
            )
          }}
        />
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div>
      <p className="text-xs font-mono text-slate-500 mb-1">{label}</p>
      <p className="text-sm font-mono font-semibold text-slate-200">{value}</p>
    </div>
  )
}
