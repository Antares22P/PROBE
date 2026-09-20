import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import type { Test } from '../types'

function StatusBadge({ status }: { status: string }) {
  const isOk = status === 'completed'
  const isErr = status === 'failed'
  const isRun = status === 'running'

  return (
    <span
      className={`px-1.5 py-0.2 rounded text-[8.5px] font-mono font-bold uppercase tracking-wider inline-flex items-center gap-1 ${
        isRun
          ? 'bg-indigo-950 text-indigo-300 border border-indigo-700'
          : isOk
          ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
          : isErr
          ? 'bg-rose-950 text-rose-300 border border-rose-800'
          : 'bg-zinc-800 text-zinc-400 border border-zinc-700'
      }`}
    >
      <span
        className={`w-1 h-1 rounded-full ${
          isRun ? 'bg-indigo-400 animate-pulse' : isOk ? 'bg-emerald-400' : isErr ? 'bg-rose-400' : 'bg-zinc-500'
        }`}
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
  if (startedAt && !completedAt) return 'RUNNING...'
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
    <div className="max-w-6xl mx-auto px-4 py-4 space-y-3 font-mono text-[10.5px]">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-[#1c1e28]">
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-bold text-zinc-100 uppercase tracking-wider">
            TEST_RUN_ARCHIVE
          </span>
          <span className="px-1.5 py-0.2 rounded text-[9.5px] bg-[#141620] text-zinc-400 border border-[#242735]">
            {tests.length}_SESSIONS
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="text-[9.5px] text-zinc-400 hover:text-zinc-100 transition-colors px-2 py-1 rounded border border-[#242735] bg-[#141620] cursor-pointer"
          >
            [REFRESH]
          </button>
          <Link
            to="/"
            className="text-[9.5px] font-bold text-white px-2.5 py-1 rounded bg-indigo-600 hover:bg-indigo-500 transition-colors"
          >
            + NEW_SESSION
          </Link>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-[#101117] border border-[#1c1e28] rounded p-2 flex flex-wrap items-center justify-between gap-2">
        <div className="relative flex-1 min-w-[200px]">
          <input
            type="text"
            placeholder="Search by URL or Test ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full px-2 py-1 rounded text-[10px] text-zinc-200 placeholder-zinc-600 bg-[#0b0c10] border border-[#1c1e28] outline-none"
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="absolute right-2 top-1 text-[9px] text-zinc-500 hover:text-zinc-300"
            >
              ✕
            </button>
          )}
        </div>

        {/* Status Filters */}
        <div className="flex items-center gap-1 overflow-x-auto text-[9.5px]">
          {['all', 'running', 'completed', 'failed', 'cancelled', 'pending'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-2 py-0.5 rounded uppercase transition-colors cursor-pointer ${
                statusFilter === st
                  ? 'bg-indigo-950 text-indigo-300 border border-indigo-700 font-bold'
                  : 'bg-[#141620] text-zinc-400 border border-[#242735] hover:text-zinc-200'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="px-3 py-2 rounded text-[10px] bg-rose-950/80 border border-rose-800 text-rose-200 flex items-center justify-between">
          <span>ERROR: {error}</span>
          <button onClick={load} className="underline hover:text-white">[RETRY]</button>
        </div>
      )}

      {loading && tests.length === 0 ? (
        <div className="rounded border border-[#1c1e28] bg-[#101117] p-8 text-center text-zinc-500 text-[10px]">
          RETRIEVING_SESSIONS_FROM_DATABASE...
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded border border-[#1c1e28] bg-[#101117] px-4 py-8 text-center space-y-2">
          <p className="text-zinc-400 font-bold text-[11px]">
            {tests.length === 0 ? 'NO_SESSIONS_RECORDED' : 'NO_SESSIONS_MATCHING_FILTER'}
          </p>
          {tests.length === 0 && (
            <Link
              to="/"
              className="inline-block text-[10px] text-white px-3 py-1 rounded bg-indigo-600 font-bold mt-2"
            >
              START_FIRST_SESSION →
            </Link>
          )}
        </div>
      ) : (
        <div className="rounded border border-[#1c1e28] bg-[#101117] overflow-hidden">
          {/* Table Header */}
          <div className="grid grid-cols-[1fr_140px_90px_70px_70px_80px_100px] gap-2 px-3 py-2 border-b border-[#1c1e28] text-[9.5px] font-bold text-zinc-500 uppercase tracking-wider items-center bg-[#0d0e14]">
            <span>TARGET_URL</span>
            <span>DATE</span>
            <span>DURATION</span>
            <span className="text-center">ACTIONS</span>
            <span className="text-center">STATES</span>
            <span className="text-center">FINDINGS</span>
            <span className="text-right">STATUS</span>
          </div>

          {/* Rows */}
          <div className="divide-y divide-[#181a24]">
            {filtered.map((t) => {
              const findingsCount = t.findings_count ?? (t.findings?.length || 0)
              const actionsCount = t.actions_count ?? (t.actions?.length || 0)
              const statesCount = t.states_count ?? (t.observations?.length || 0)

              return (
                <div
                  key={t.id}
                  onClick={() => navigate(`/test/${t.id}`)}
                  className="grid grid-cols-[1fr_140px_90px_70px_70px_80px_100px] gap-2 px-3 py-2 hover:bg-[#141622] transition-colors items-center cursor-pointer group"
                >
                  {/* Target URL */}
                  <div className="min-w-0 pr-2">
                    <div className="text-[10.5px] font-bold text-zinc-200 group-hover:text-indigo-300 transition-colors truncate">
                      {t.url}
                    </div>
                    <div className="text-[8.5px] text-zinc-500 truncate mt-0.5">
                      ID: {t.id} · {t.platform}
                    </div>
                  </div>

                  {/* Date */}
                  <div className="text-[9.5px] text-zinc-400 whitespace-nowrap">
                    {formatDate(t.created_at)}
                  </div>

                  {/* Duration */}
                  <div className="text-[9.5px] text-zinc-300 whitespace-nowrap">
                    {formatDuration(t.duration_ms, t.started_at, t.completed_at)}
                  </div>

                  {/* Actions */}
                  <div className="text-center">
                    <span className="px-1.5 py-0.2 rounded text-[9px] bg-[#0b0c10] text-zinc-300 border border-[#1c1e28]">
                      {actionsCount}
                    </span>
                  </div>

                  {/* States */}
                  <div className="text-center">
                    <span className="px-1.5 py-0.2 rounded text-[9px] bg-[#0b0c10] text-zinc-300 border border-[#1c1e28]">
                      {statesCount}
                    </span>
                  </div>

                  {/* Findings */}
                  <div className="text-center">
                    <span
                      className={`px-1.5 py-0.2 rounded text-[9px] font-bold ${
                        findingsCount > 0
                          ? 'bg-rose-950 text-rose-300 border border-rose-800'
                          : 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                      }`}
                    >
                      {findingsCount}
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
