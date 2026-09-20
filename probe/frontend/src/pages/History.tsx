import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import type { Test } from '../types'

const STATUS_COLORS: Record<string, string> = {
  pending: '#6b7280',
  running: '#6366f1',
  completed: '#22c55e',
  failed: '#ef4444',
  cancelled: '#f59e0b',
}

function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] ?? '#6b7280'
  return (
    <span
      className="px-2 py-0.5 rounded text-[11px] font-mono font-bold uppercase tracking-wider inline-flex items-center gap-1.5"
      style={{
        color,
        backgroundColor: `${color}18`,
        border: `1px solid ${color}35`,
      }}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${status === 'running' ? 'animate-pulse' : ''}`}
        style={{ background: color }}
      />
      {status}
    </span>
  )
}

function formatDuration(ms?: number | null, startedAt?: string | null, completedAt?: string | null): string {
  if (ms !== undefined && ms !== null && ms > 0) {
    if (ms < 1000) return `${Math.round(ms)}ms`
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
    const mins = Math.floor(ms / 60000)
    const secs = Math.round((ms % 60000) / 1000)
    return `${mins}m ${secs}s`
  }
  if (startedAt && completedAt) {
    const diff = new Date(completedAt).getTime() - new Date(startedAt).getTime()
    if (diff > 0) {
      if (diff < 60000) return `${(diff / 1000).toFixed(1)}s`
      return `${Math.floor(diff / 60000)}m ${Math.round((diff % 60000) / 1000)}s`
    }
  }
  if (startedAt && !completedAt) return 'Running...'
  return '—'
}

function formatDate(isoStr: string): string {
  try {
    const d = new Date(isoStr)
    return d.toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return isoStr
  }
}

export function History() {
  const [tests, setTests] = useState<Test[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const navigate = useNavigate()

  const load = () => {
    setLoading(true)
    setError(null)
    api.listTests()
      .then(setTests)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const filtered = tests.filter((t) => {
    const matchesSearch = !search || t.url.toLowerCase().includes(search.toLowerCase()) || t.id.includes(search)
    const matchesStatus = statusFilter === 'all' || t.status === statusFilter
    return matchesSearch && matchesStatus
  })

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-base font-mono font-bold text-slate-100 uppercase tracking-wider">
              Test Run History
            </h1>
            <span className="px-2 py-0.5 rounded text-xs font-mono bg-slate-800 text-slate-300 border border-slate-700">
              {tests.length} Total Runs
            </span>
          </div>
          <p className="text-xs font-mono text-slate-500 mt-1">
            Persisted autonomous test sessions from the real database
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={load}
            className="text-xs font-mono text-slate-400 hover:text-slate-100 transition-colors px-3 py-1.5 rounded-lg border flex items-center gap-1.5 cursor-pointer"
            style={{ background: '#11111d', borderColor: '#26263b' }}
          >
            <span>↻</span>
            <span>Refresh</span>
          </button>
          <Link
            to="/"
            className="text-xs font-mono font-semibold text-white px-3.5 py-1.5 rounded-lg transition-all shadow-md flex items-center gap-1.5"
            style={{ background: '#6366f1' }}
          >
            <span>+</span>
            <span>New Test</span>
          </Link>
        </div>
      </div>

      {/* Filter Bar */}
      <div
        className="rounded-xl border p-3 mb-6 flex flex-wrap items-center justify-between gap-3"
        style={{ background: '#0e0e17', borderColor: '#1e1e2e' }}
      >
        <div className="relative flex-1 min-w-[220px]">
          <input
            type="text"
            placeholder="Search by URL or Test ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full px-3 py-1.5 rounded-lg text-xs font-mono text-slate-200 placeholder-slate-600 border outline-none"
            style={{ background: '#07070d', borderColor: '#1e1e2e' }}
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="absolute right-2.5 top-1.5 text-xs text-slate-500 hover:text-slate-300"
            >
              ✕
            </button>
          )}
        </div>

        {/* Status Filters */}
        <div className="flex items-center gap-1 overflow-x-auto">
          {['all', 'running', 'completed', 'failed', 'cancelled', 'pending'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className="px-2.5 py-1 rounded text-[11px] font-mono capitalize transition-colors cursor-pointer"
              style={{
                background: statusFilter === st ? '#6366f125' : '#11111d',
                color: statusFilter === st ? '#a5b4fc' : '#94a3b8',
                border: `1px solid ${statusFilter === st ? '#6366f1' : '#1e1e2e'}`,
              }}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div
          className="mb-6 px-4 py-3 rounded-lg text-xs font-mono border flex items-center justify-between"
          style={{ background: '#1a0a0a', borderColor: '#7f1d1d', color: '#fca5a5' }}
        >
          <span>Error loading test history: {error}</span>
          <button onClick={load} className="underline hover:text-white">Retry</button>
        </div>
      )}

      {loading && tests.length === 0 ? (
        <div className="rounded-xl border p-12 text-center" style={{ background: '#0e0e17', borderColor: '#1e1e2e' }}>
          <div className="inline-block w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-3" />
          <p className="text-xs font-mono text-slate-500">Retrieving test runs from database...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div
          className="rounded-xl border px-6 py-16 text-center"
          style={{ background: '#0e0e17', borderColor: '#1e1e2e' }}
        >
          <div className="text-2xl mb-2">🔍</div>
          <p className="text-sm font-mono text-slate-400">
            {tests.length === 0 ? 'No test runs found in database.' : 'No tests match the current filter.'}
          </p>
          <p className="text-xs font-mono text-slate-600 mt-1">
            {tests.length === 0
              ? 'Launch an autonomous exploration to record telemetry and findings.'
              : 'Try clearing your search or status filter.'}
          </p>
          {tests.length === 0 ? (
            <Link
              to="/"
              className="inline-block text-xs font-mono text-white px-4 py-2 rounded-lg mt-4 font-semibold"
              style={{ background: '#6366f1' }}
            >
              Start First Test →
            </Link>
          ) : (
            <button
              onClick={() => { setSearch(''); setStatusFilter('all') }}
              className="text-xs font-mono text-indigo-400 underline mt-3 inline-block cursor-pointer"
            >
              Reset filters
            </button>
          )}
        </div>
      ) : (
        <div
          className="rounded-xl border overflow-hidden shadow-xl"
          style={{ borderColor: '#1e1e2e', background: '#0e0e17' }}
        >
          {/* Table Header */}
          <div
            className="grid grid-cols-[1fr_160px_100px_90px_90px_100px_120px] gap-3 px-4 py-3 border-b text-xs font-mono font-semibold text-slate-500 uppercase tracking-wider items-center"
            style={{ background: '#090910', borderColor: '#1e1e2e' }}
          >
            <span>Target URL</span>
            <span>Date</span>
            <span>Duration</span>
            <span className="text-center">Actions</span>
            <span className="text-center">States</span>
            <span className="text-center">Findings</span>
            <span className="text-right">Status</span>
          </div>

          {/* Rows */}
          <div className="divide-y" style={{ borderColor: '#161622' }}>
            {filtered.map((t) => {
              const findingsCount = t.findings_count ?? (t.findings?.length || 0)
              const actionsCount = t.actions_count ?? (t.actions?.length || 0)
              const statesCount = t.states_count ?? (t.observations?.length || 0)

              return (
                <div
                  key={t.id}
                  onClick={() => navigate(`/test/${t.id}`)}
                  className="grid grid-cols-[1fr_160px_100px_90px_90px_100px_120px] gap-3 px-4 py-3.5
                             hover:bg-indigo-950/15 transition-colors items-center cursor-pointer group"
                >
                  {/* Target URL */}
                  <div className="min-w-0 pr-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-medium text-slate-200 group-hover:text-indigo-300 transition-colors truncate">
                        {t.url}
                      </span>
                    </div>
                    <div className="text-[10px] font-mono text-slate-600 truncate mt-0.5">
                      ID: {t.id} · Platform: {t.platform}
                    </div>
                  </div>

                  {/* Date */}
                  <div className="text-xs font-mono text-slate-400 whitespace-nowrap">
                    {formatDate(t.created_at)}
                  </div>

                  {/* Duration */}
                  <div className="text-xs font-mono text-slate-300 whitespace-nowrap">
                    {formatDuration(t.duration_ms, t.started_at, t.completed_at)}
                  </div>

                  {/* Actions */}
                  <div className="text-center">
                    <span className="inline-block px-2 py-0.5 rounded text-xs font-mono bg-slate-900 text-slate-300 border border-slate-800">
                      {actionsCount}
                    </span>
                  </div>

                  {/* States */}
                  <div className="text-center">
                    <span className="inline-block px-2 py-0.5 rounded text-xs font-mono bg-slate-900 text-slate-300 border border-slate-800">
                      {statesCount}
                    </span>
                  </div>

                  {/* Findings */}
                  <div className="text-center">
                    <span
                      className="inline-block px-2 py-0.5 rounded text-xs font-mono font-semibold"
                      style={{
                        background: findingsCount > 0 ? '#ef444420' : '#22c55e15',
                        color: findingsCount > 0 ? '#f87171' : '#4ade80',
                        border: `1px solid ${findingsCount > 0 ? '#ef444440' : '#22c55e30'}`,
                      }}
                    >
                      {findingsCount} {findingsCount === 1 ? 'issue' : 'issues'}
                    </span>
                  </div>

                  {/* Status */}
                  <div className="text-right">
                    <StatusBadge status={t.status} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
