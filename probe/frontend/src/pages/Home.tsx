import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'

export function Home() {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = url.trim()
    if (!trimmed) return

    setError(null)
    setLoading(true)

    try {
      const test = await api.createTest(trimmed)
      await api.startTest(test.id)
      navigate(`/test/${test.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start test')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-52px)] px-4">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="mb-10 text-center">
          <div className="flex justify-center mb-4">
            <span
              className="font-mono text-2xl font-semibold px-3 py-1 rounded"
              style={{ background: '#6366f1', color: '#fff', letterSpacing: '0.08em' }}
            >
              PROBE
            </span>
          </div>
          <p className="text-slate-400 text-sm font-mono mt-3">
            Autonomous Application Testing
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <div className="mb-3">
            <label
              htmlFor="target-url"
              className="block text-xs font-mono text-slate-500 mb-1.5 uppercase tracking-wider"
            >
              Target URL
            </label>
            <input
              id="target-url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com"
              required
              disabled={loading}
              className="w-full px-4 py-3 rounded text-sm font-mono text-slate-200 placeholder-slate-600
                         border outline-none transition-colors
                         disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                background: '#111118',
                borderColor: '#1e1e2e',
              }}
              onFocus={(e) => { e.target.style.borderColor = '#6366f1' }}
              onBlur={(e) => { e.target.style.borderColor = '#1e1e2e' }}
            />
          </div>

          {error && (
            <div
              className="mb-3 px-3 py-2 rounded text-xs font-mono border"
              style={{ background: '#1a0a0a', borderColor: '#7f1d1d', color: '#fca5a5' }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !url.trim()}
            className="w-full py-3 rounded text-sm font-mono font-semibold
                       transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              background: loading ? '#4f52c4' : '#6366f1',
              color: '#fff',
            }}
          >
            {loading ? 'Starting...' : 'Start Test'}
          </button>
        </form>

        {/* Footer hint */}
        <p className="text-center text-xs font-mono text-slate-700 mt-6">
          PROBE will autonomously explore the target URL
        </p>
      </div>
    </div>
  )
}
