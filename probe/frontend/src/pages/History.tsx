import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import type { Test } from '../types'

const STATUS_COLORS: Record<string, string> = {
  pending: '#6b7280',
  running: '#6366f1',
  completed: '#22c55e',
  failed: '#ef4444',
  cancelled: '#f59e0b',
}

function StatusDot({ status }: { status: string }) {
  return (
    <span
      className="w-1.5 h-1.5 rounded-full shrink-0 mt-1.5"
      style={{ background: STATUS_COLORS[status] ?? '#6b7280' }}
    />
  )
}

export function History() {
  const [tests, setTests] = useState<Test[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    api.listTests()
      .then(setTests)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-sm font-mono font-semibold text-slate-300 uppercase tracking-wider">
          Test History
        </h1>
        <button
          onClick={load}
          className="text-xs font-mono text-slate-500 hover:text-slate-300 transition-colors px-2 py-1 rounded border"
          style={{ borderColor: '#1e1e2e' }}
        >
          Refresh
        </button>
      </div>

      {error && (
        <div
          className="mb-4 px-3 py-2 rounded text-xs font-mono border"
          style={{ background: '#1a0a0a', borderColor: '#7f1d1d', color: '#fca5a5' }}
        >
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-xs font-mono text-slate-600">Loading...</p>
      ) : tests.length === 0 ? (
        <div
          className="rounded border px-6 py-12 text-center"
          style={{ background: '#111118', borderColor: '#1e1e2e' }}
        >
          <p className="text-sm font-mono text-slate-600">No tests yet.</p>
          <Link
            to="/"
            className="text-xs font-mono text-indigo-400 hover:underline mt-2 block"
          >
            Start your first test →
          </Link>
        </div>
      ) : (
        <div
          className="rounded border overflow-hidden"
          style={{ borderColor: '#1e1e2e' }}
        >
          {/* Table header */}
          <div
            className="grid grid-cols-[1fr_auto_auto_auto] gap-4 px-4 py-2 border-b"
            style={{ background: '#0d0d15', borderColor: '#1e1e2e' }}
          >
            <span className="text-xs font-mono text-slate-600 uppercase tracking-wider">URL</span>
            <span className="text-xs font-mono text-slate-600 uppercase tracking-wider">Platform</span>
            <span className="text-xs font-mono text-slate-600 uppercase tracking-wider">Status</span>
            <span className="text-xs font-mono text-slate-600 uppercase tracking-wider">Created</span>
          </div>

          {/* Rows */}
          {tests.map((t) => (
            <Link
              key={t.id}
              to={`/test/${t.id}`}
              className="grid grid-cols-[1fr_auto_auto_auto] gap-4 px-4 py-3 border-b
                         hover:bg-white/[0.02] transition-colors items-start"
              style={{ borderColor: '#1e1e2e' }}
            >
              <div className="flex items-start gap-2 min-w-0">
                <StatusDot status={t.status} />
                <span className="text-sm font-mono text-slate-300 truncate">{t.url}</span>
              </div>
              <span className="text-xs font-mono text-slate-500 whitespace-nowrap">{t.platform}</span>
              <span
                className="text-xs font-mono font-semibold uppercase whitespace-nowrap"
                style={{ color: STATUS_COLORS[t.status] ?? '#6b7280' }}
              >
                {t.status}
              </span>
              <span className="text-xs font-mono text-slate-600 whitespace-nowrap">
                {new Date(t.created_at).toLocaleDateString()}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
