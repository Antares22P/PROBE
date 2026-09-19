import { useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useTestEvents } from '../lib/sse'
import type { Test, SSEEvent } from '../types'

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
      className="px-2 py-0.5 rounded text-xs font-mono font-semibold uppercase"
      style={{ color: STATUS_COLORS[status] ?? '#6b7280', background: `${STATUS_COLORS[status] ?? '#6b7280'}18` }}
    >
      {status}
    </span>
  )
}

function EventRow({ event }: { event: SSEEvent }) {
  if (event.type === 'connected') {
    return (
      <div className="text-xs font-mono text-slate-600 py-0.5">
        — connected to event stream
      </div>
    )
  }

  if (event.type === 'status') {
    const color = STATUS_COLORS[event.status ?? ''] ?? '#6b7280'
    return (
      <div className="text-xs font-mono py-0.5" style={{ color }}>
        [{event.status?.toUpperCase()}] {event.message}
        {event.findings_count !== undefined && (
          <span className="text-slate-500 ml-2">({event.findings_count} finding{event.findings_count !== 1 ? 's' : ''})</span>
        )}
      </div>
    )
  }

  if (event.type === 'observation') {
    return (
      <div className="text-xs font-mono text-slate-400 py-0.5">
        <span className="text-slate-600">[OBS]</span>{' '}
        <span className="text-indigo-400">{event.url}</span>
        {event.title && <span className="text-slate-500"> — {event.title}</span>}
        <span className="text-slate-600 ml-2">
          {event.element_count} elements, {event.console_errors} errors
        </span>
      </div>
    )
  }

  if (event.type === 'finding') {
    const color = SEVERITY_COLORS[event.severity ?? 'info'] ?? '#6b7280'
    return (
      <div className="text-xs font-mono py-0.5">
        <span style={{ color }}>[{event.severity?.toUpperCase()}]</span>{' '}
        <span className="text-slate-300">{event.category}: </span>
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
  const { events } = useTestEvents(id ?? null)
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!id) return
    api.getTest(id)
      .then(setTest)
      .catch((e) => setLoadError(e.message))
  }, [id])

  // Auto-scroll log to bottom
  useEffect(() => {
    const el = logRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [events])

  // Refresh test status when a status event arrives
  useEffect(() => {
    const last = events[events.length - 1]
    if (!last || last.type !== 'status') return
    if (!id) return
    api.getTest(id).then(setTest).catch(() => {})
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
        <span className="text-xs font-mono text-slate-500">Loading...</span>
      </div>
    )
  }

  const isActive = test.status === 'running'
  const findings = events.filter((e) => e.type === 'finding')

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 mb-6">
        <Link to="/history" className="text-xs font-mono text-slate-500 hover:text-slate-300">
          Tests
        </Link>
        <span className="text-slate-700 text-xs">/</span>
        <span className="text-xs font-mono text-slate-400 truncate max-w-xs">{test.id}</span>
      </div>

      {/* Test header */}
      <div
        className="rounded border p-5 mb-6"
        style={{ background: '#111118', borderColor: '#1e1e2e' }}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-3 mb-2">
              <StatusBadge status={test.status} />
              <span className="text-xs font-mono text-slate-600">
                {test.platform} · {new Date(test.created_at).toLocaleString()}
              </span>
            </div>
            <p className="text-sm font-mono text-indigo-400 truncate">{test.url}</p>
            {test.error_message && (
              <p className="text-xs font-mono text-red-400 mt-1">{test.error_message}</p>
            )}
          </div>
          {isActive && (
            <button
              onClick={handleCancel}
              className="shrink-0 px-3 py-1.5 rounded text-xs font-mono border transition-colors hover:bg-red-950 hover:border-red-800"
              style={{ borderColor: '#2d1f1f', color: '#ef4444' }}
            >
              Cancel
            </button>
          )}
        </div>

        {/* Stats row */}
        <div className="flex gap-4 mt-4 pt-4 border-t" style={{ borderColor: '#1a1a2e' }}>
          <Stat label="Findings" value={findings.length} />
          <Stat label="Events" value={events.length} />
          {test.completed_at && (
            <Stat
              label="Duration"
              value={`${Math.round((new Date(test.completed_at).getTime() - new Date(test.created_at).getTime()) / 1000)}s`}
            />
          )}
        </div>
      </div>

      {/* Event log */}
      <div
        className="rounded border"
        style={{ background: '#0d0d15', borderColor: '#1e1e2e' }}
      >
        <div
          className="px-4 py-2 border-b flex items-center justify-between"
          style={{ borderColor: '#1e1e2e' }}
        >
          <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">Event Log</span>
          {isActive && (
            <span className="flex items-center gap-1.5">
              <span
                className="w-1.5 h-1.5 rounded-full animate-pulse"
                style={{ background: '#6366f1' }}
              />
              <span className="text-xs font-mono text-slate-600">live</span>
            </span>
          )}
        </div>
        <div
          ref={logRef}
          className="px-4 py-3 max-h-96 overflow-y-auto log-scroll space-y-0.5"
        >
          {events.length === 0 ? (
            <p className="text-xs font-mono text-slate-700">Waiting for events...</p>
          ) : (
            events.map((e, i) => <EventRow key={i} event={e} />)
          )}
        </div>
      </div>

      {/* Findings summary */}
      {findings.length > 0 && (
        <div className="mt-6">
          <h2 className="text-xs font-mono text-slate-500 uppercase tracking-wider mb-3">
            Findings ({findings.length})
          </h2>
          <div className="space-y-2">
            {findings.map((f, i) => (
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
                  <span className="text-xs font-mono text-slate-600">{f.category}</span>
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
      <p className="text-xs font-mono text-slate-600 mb-0.5">{label}</p>
      <p className="text-sm font-mono font-semibold text-slate-300">{value}</p>
    </div>
  )
}
