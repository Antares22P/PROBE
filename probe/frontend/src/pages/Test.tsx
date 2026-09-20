import { useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useTestEvents } from '../lib/sse'
import type { Test, SSEEvent, InteractiveElement, ConsoleMessage, JavaScriptException, FailedRequest } from '../types'

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
  if (event.type === 'connected') {
    return (
      <div className="text-xs font-mono text-slate-500 py-0.5">
        — Connected to PROBE live stream
      </div>
    )
  }

  if (event.type === 'status') {
    const color = STATUS_COLORS[event.status ?? ''] ?? '#6b7280'
    return (
      <div className="text-xs font-mono py-0.5" style={{ color }}>
        [{event.status?.toUpperCase()}] {event.message}
        {event.findings_count !== undefined && (
          <span className="text-slate-400 ml-2">({event.findings_count} finding{event.findings_count !== 1 ? 's' : ''})</span>
        )}
      </div>
    )
  }

  if (event.type === 'observation') {
    return (
      <div className="text-xs font-mono text-slate-300 py-0.5">
        <span className="text-indigo-400 font-semibold">[OBS]</span>{' '}
        <span className="text-slate-100">{event.url || event.requested_url}</span>
        {event.title && <span className="text-slate-400"> — "{event.title}"</span>}
        {event.status_code && (
          <span className="text-emerald-400 ml-2">({event.status_code})</span>
        )}
        {event.duration_ms !== undefined && event.duration_ms !== null && (
          <span className="text-slate-400 ml-2">in {event.duration_ms}ms</span>
        )}
        {event.element_count !== undefined && (
          <span className="text-slate-500 ml-2">
            · {event.element_count} elements
          </span>
        )}
      </div>
    )
  }

  if (event.type === 'screenshot') {
    return (
      <div className="text-xs font-mono text-emerald-400 py-0.5">
        <span>[SCREENSHOT]</span> Viewport captured successfully
      </div>
    )
  }

  if (event.type === 'finding') {
    const color = SEVERITY_COLORS[event.severity ?? 'info'] ?? '#6b7280'
    return (
      <div className="text-xs font-mono py-0.5">
        <span style={{ color }}>[{event.severity?.toUpperCase()}]</span>{' '}
        <span className="text-slate-300 font-medium">{event.category}: </span>
        <span className="text-slate-200">{event.description}</span>
      </div>
    )
  }

  return null
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
  const [activeTab, setActiveTab] = useState<'telemetry' | 'elements' | 'signals' | 'state'>('telemetry')
  const [elementFilter, setElementFilter] = useState<string>('all')

  const [liveElements, setLiveElements] = useState<InteractiveElement[]>([])
  const [liveConsoleMessages, setLiveConsoleMessages] = useState<ConsoleMessage[]>([])
  const [liveJsExceptions, setLiveJsExceptions] = useState<JavaScriptException[]>([])
  const [liveFailedRequests, setLiveFailedRequests] = useState<FailedRequest[]>([])
  const [liveFingerprint, setLiveFingerprint] = useState<string | null>(null)
  const [liveViewport, setLiveViewport] = useState<{ width: number; height: number } | null>(null)
  const [liveDimensions, setLiveDimensions] = useState<{ width: number; height: number } | null>(null)

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

        if (data.observations && data.observations.length > 0) {
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

    if (last.type === 'observation') {
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
    } else if (last.type === 'screenshot' && last.url) {
      setLiveScreenshotUrl(`${last.url}?t=${Date.now()}`)
    } else if (last.type === 'status') {
      if (last.current_url) setLiveCurrentUrl(last.current_url)
      if (last.page_title) setLiveTitle(last.page_title)
      if (last.status_code) setLiveStatusCode(last.status_code)
      if (last.duration_ms) setLiveDurationMs(last.duration_ms)
      if (last.screenshot_url) setLiveScreenshotUrl(`${last.screenshot_url}?t=${Date.now()}`)

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

  const findings = events.filter((e) => e.type === 'finding')
  const allFindings = (test.findings && test.findings.length > 0) ? test.findings : findings

  // Filter elements
  const filteredElements = liveElements.filter((el) => {
    if (elementFilter === 'all') return true
    if (elementFilter === 'links') return el.type === 'link'
    if (elementFilter === 'buttons') return el.type === 'button'
    if (elementFilter === 'inputs') return el.type.startsWith('input') || el.type === 'textarea' || el.type === 'select'
    return true
  })

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
          <Stat label="Navigation Duration" value={displayDuration} />
          <Stat label="Interactive Elements" value={liveElements.length} />
          <Stat label="Browser Signals" value={liveConsoleMessages.length + liveJsExceptions.length + liveFailedRequests.length} />
          <Stat label="Findings Detected" value={allFindings.length} />
        </div>
      </div>

      {/* Observation Tabs Bar */}
      <div className="flex items-center gap-2 border-b mb-6 pb-2" style={{ borderColor: '#1e1e2e' }}>
        <button
          onClick={() => setActiveTab('telemetry')}
          className={`px-3 py-1.5 rounded text-xs font-mono transition-colors ${
            activeTab === 'telemetry'
              ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Viewport & Live Stream
        </button>
        <button
          onClick={() => setActiveTab('elements')}
          className={`px-3 py-1.5 rounded text-xs font-mono transition-colors ${
            activeTab === 'elements'
              ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Interactive Elements ({liveElements.length})
        </button>
        <button
          onClick={() => setActiveTab('signals')}
          className={`px-3 py-1.5 rounded text-xs font-mono transition-colors ${
            activeTab === 'signals'
              ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/40'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Browser Signals ({liveConsoleMessages.length + liveJsExceptions.length + liveFailedRequests.length})
        </button>
        <button
          onClick={() => setActiveTab('state')}
          className={`px-3 py-1.5 rounded text-xs font-mono transition-colors ${
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
                  <p className="text-xs font-mono text-slate-400">Launching Chromium & capturing viewport...</p>
                </div>
              ) : (
                <div className="text-center py-12">
                  <p className="text-xs font-mono text-slate-600">No viewport screenshot captured</p>
                </div>
              )}
            </div>
          </div>

          {/* Live Event Log */}
          <div
            className="rounded-lg border flex flex-col"
            style={{ background: '#0d0d15', borderColor: '#1e1e2e' }}
          >
            <div
              className="px-4 py-2.5 border-b flex items-center justify-between"
              style={{ borderColor: '#1e1e2e', background: '#111118' }}
            >
              <span className="text-xs font-mono text-slate-400 font-semibold uppercase tracking-wider">
                Execution Telemetry Log
              </span>
              {isActive && (
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
                  <span className="text-xs font-mono text-indigo-400">live</span>
                </span>
              )}
            </div>
            <div
              ref={logRef}
              className="p-4 max-h-[380px] min-h-[280px] overflow-y-auto font-mono space-y-1.5"
            >
              {events.length === 0 ? (
                <p className="text-xs font-mono text-slate-600">Connecting to test lifecycle events...</p>
              ) : (
                events.map((e, i) => <EventRow key={i} event={e} />)
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: Interactive Elements */}
      {activeTab === 'elements' && (
        <div className="rounded-lg border mb-6 overflow-hidden" style={{ background: '#111118', borderColor: '#1e1e2e' }}>
          <div className="px-4 py-3 border-b flex items-center justify-between flex-wrap gap-2" style={{ borderColor: '#1e1e2e' }}>
            <span className="text-xs font-mono text-slate-400 uppercase tracking-wider font-semibold">
              Discovered UI Elements ({filteredElements.length})
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

      {/* TAB 3: Browser Signals */}
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

      {/* TAB 4: State & Fingerprint */}
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

      {/* Findings Section */}
      {allFindings.length > 0 && (
        <div className="mt-6">
          <h2 className="text-xs font-mono text-slate-400 uppercase tracking-wider font-semibold mb-3">
            Detected Findings ({allFindings.length})
          </h2>
          <div className="space-y-2">
            {allFindings.map((f, i) => (
              <div
                key={i}
                className="rounded border px-4 py-3"
                style={{ background: '#111118', borderColor: '#1e1e2e' }}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className="text-xs font-mono font-semibold uppercase"
                    style={{ color: SEVERITY_COLORS[f.severity ?? 'info'] }}
                  >
                    {f.severity}
                  </span>
                  <span className="text-xs font-mono text-slate-400">{f.category}</span>
                  {f.title && <span className="text-xs font-mono text-slate-300 font-semibold">— {f.title}</span>}
                </div>
                <p className="text-sm text-slate-300">{f.description}</p>
              </div>
            ))}
          </div>
        </div>
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
