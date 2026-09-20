import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'

export function Home() {
  const [url, setUrl] = useState('')
  const [durationSeconds, setDurationSeconds] = useState(180)
  const [maxActions, setMaxActions] = useState(50)
  const [maxStates, setMaxStates] = useState(25)
  const [maxDepth, setMaxDepth] = useState(5)
  const [headless, setHeadless] = useState(true)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const applyPreset = (duration: number, actions: number, states: number, depth: number) => {
    setDurationSeconds(duration)
    setMaxActions(actions)
    setMaxStates(states)
    setMaxDepth(depth)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    let trimmed = url.trim()
    if (!trimmed) return

    if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
      trimmed = `https://${trimmed}`
    }

    setError(null)
    setLoading(true)

    try {
      const config = {
        max_duration_seconds: Number(durationSeconds),
        timeout_seconds: Number(durationSeconds),
        max_actions: Number(maxActions),
        max_states: Number(maxStates),
        max_depth: Number(maxDepth),
        headless: Boolean(headless),
      }

      const test = await api.createTest(trimmed, 'web', config)
      await api.startTest(test.id)
      navigate(`/test/${test.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start test')
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-52px)] px-4 py-8">
      <div className="w-full max-w-xl">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="inline-flex items-center gap-2 mb-3">
            <span
              className="font-mono text-2xl font-bold px-3 py-1 rounded tracking-wider shadow-lg"
              style={{ background: '#6366f1', color: '#fff' }}
            >
              PROBE
            </span>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-indigo-950/80 text-indigo-300 border border-indigo-800/60 uppercase">
              V1 Autonomous
            </span>
          </div>
          <h1 className="text-xl font-mono font-semibold text-slate-100 tracking-tight">
            Autonomous Web Reliability & Issue Discovery
          </h1>
          <p className="text-slate-400 text-xs font-mono mt-1.5">
            Real Playwright browser automation · Deterministic issue detection · Gemini AI root cause reasoning
          </p>
        </div>

        {/* Card */}
        <div
          className="rounded-xl border p-6 shadow-2xl backdrop-blur-sm"
          style={{ background: '#0e0e17', borderColor: '#1e1e2e' }}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Target URL */}
            <div>
              <label
                htmlFor="target-url"
                className="block text-xs font-mono font-semibold text-slate-300 mb-1.5 uppercase tracking-wider"
              >
                Target URL
              </label>
              <div className="relative">
                <input
                  id="target-url"
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com"
                  required
                  disabled={loading}
                  className="w-full px-4 py-3 rounded-lg text-sm font-mono text-slate-100 placeholder-slate-600
                             border outline-none transition-all
                             disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{
                    background: '#07070d',
                    borderColor: '#1e1e2e',
                  }}
                  onFocus={(e) => { e.target.style.borderColor = '#6366f1' }}
                  onBlur={(e) => { e.target.style.borderColor = '#1e1e2e' }}
                />
              </div>
            </div>

            {/* Quick Presets */}
            <div className="flex flex-wrap gap-2 pt-1">
              <button
                type="button"
                onClick={() => applyPreset(30, 15, 10, 3)}
                className="text-[11px] font-mono px-2.5 py-1 rounded border transition-colors hover:border-indigo-500 hover:text-indigo-300"
                style={{
                  background: durationSeconds === 30 && maxActions === 15 ? '#6366f120' : '#141420',
                  borderColor: durationSeconds === 30 && maxActions === 15 ? '#6366f1' : '#232336',
                  color: durationSeconds === 30 && maxActions === 15 ? '#818cf8' : '#94a3b8',
                }}
              >
                ⚡ Quick Scan (30s · 15 acts)
              </button>
              <button
                type="button"
                onClick={() => applyPreset(180, 50, 25, 5)}
                className="text-[11px] font-mono px-2.5 py-1 rounded border transition-colors hover:border-indigo-500 hover:text-indigo-300"
                style={{
                  background: durationSeconds === 180 && maxActions === 50 ? '#6366f120' : '#141420',
                  borderColor: durationSeconds === 180 && maxActions === 50 ? '#6366f1' : '#232336',
                  color: durationSeconds === 180 && maxActions === 50 ? '#818cf8' : '#94a3b8',
                }}
              >
                🔍 Standard (180s · 50 acts)
              </button>
              <button
                type="button"
                onClick={() => applyPreset(300, 100, 40, 8)}
                className="text-[11px] font-mono px-2.5 py-1 rounded border transition-colors hover:border-indigo-500 hover:text-indigo-300"
                style={{
                  background: durationSeconds === 300 && maxActions === 100 ? '#6366f120' : '#141420',
                  borderColor: durationSeconds === 300 && maxActions === 100 ? '#6366f1' : '#232336',
                  color: durationSeconds === 300 && maxActions === 100 ? '#818cf8' : '#94a3b8',
                }}
              >
                🛡️ Deep Audit (300s · 100 acts)
              </button>
            </div>

            {/* Collapsible Advanced Settings */}
            <div className="pt-2">
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center gap-2 text-xs font-mono text-slate-400 hover:text-slate-200 transition-colors py-1 cursor-pointer"
              >
                <span className="text-[10px] text-indigo-400 font-bold">
                  {showAdvanced ? '▼' : '▶'}
                </span>
                <span>Advanced Exploration Settings</span>
                <span className="text-[10px] text-slate-600">
                  ({durationSeconds}s, {maxActions} max actions)
                </span>
              </button>

              {showAdvanced && (
                <div
                  className="mt-3 p-4 rounded-lg border space-y-3.5"
                  style={{ background: '#080811', borderColor: '#1c1c2b' }}
                >
                  <div className="grid grid-cols-2 gap-3">
                    {/* Test Duration */}
                    <div>
                      <label
                        htmlFor="test-duration"
                        className="block text-[11px] font-mono text-slate-400 mb-1 uppercase"
                      >
                        Test Duration (seconds)
                      </label>
                      <input
                        id="test-duration"
                        type="number"
                        min={10}
                        max={600}
                        step={10}
                        value={durationSeconds}
                        onChange={(e) => setDurationSeconds(Number(e.target.value))}
                        disabled={loading}
                        className="w-full px-3 py-1.5 rounded text-xs font-mono text-slate-200 border outline-none"
                        style={{ background: '#11111d', borderColor: '#26263b' }}
                      />
                    </div>

                    {/* Maximum Actions */}
                    <div>
                      <label
                        htmlFor="max-actions"
                        className="block text-[11px] font-mono text-slate-400 mb-1 uppercase"
                      >
                        Maximum Actions
                      </label>
                      <input
                        id="max-actions"
                        type="number"
                        min={5}
                        max={200}
                        step={5}
                        value={maxActions}
                        onChange={(e) => setMaxActions(Number(e.target.value))}
                        disabled={loading}
                        className="w-full px-3 py-1.5 rounded text-xs font-mono text-slate-200 border outline-none"
                        style={{ background: '#11111d', borderColor: '#26263b' }}
                      />
                    </div>

                    {/* Max States */}
                    <div>
                      <label
                        htmlFor="max-states"
                        className="block text-[11px] font-mono text-slate-400 mb-1 uppercase"
                      >
                        Max Distinct States
                      </label>
                      <input
                        id="max-states"
                        type="number"
                        min={5}
                        max={100}
                        step={5}
                        value={maxStates}
                        onChange={(e) => setMaxStates(Number(e.target.value))}
                        disabled={loading}
                        className="w-full px-3 py-1.5 rounded text-xs font-mono text-slate-200 border outline-none"
                        style={{ background: '#11111d', borderColor: '#26263b' }}
                      />
                    </div>

                    {/* Max Depth */}
                    <div>
                      <label
                        htmlFor="max-depth"
                        className="block text-[11px] font-mono text-slate-400 mb-1 uppercase"
                      >
                        Max Exploration Depth
                      </label>
                      <input
                        id="max-depth"
                        type="number"
                        min={1}
                        max={20}
                        step={1}
                        value={maxDepth}
                        onChange={(e) => setMaxDepth(Number(e.target.value))}
                        disabled={loading}
                        className="w-full px-3 py-1.5 rounded text-xs font-mono text-slate-200 border outline-none"
                        style={{ background: '#11111d', borderColor: '#26263b' }}
                      />
                    </div>
                  </div>

                  {/* Headless Toggle */}
                  <div className="flex items-center justify-between pt-1 border-t border-slate-800/60">
                    <div>
                      <span className="text-xs font-mono text-slate-300 block">Headless Browser</span>
                      <span className="text-[10px] font-mono text-slate-500">Run browser in background for speed</span>
                    </div>
                    <input
                      type="checkbox"
                      checked={headless}
                      onChange={(e) => setHeadless(e.target.checked)}
                      disabled={loading}
                      className="rounded accent-indigo-500 w-4 h-4 cursor-pointer"
                    />
                  </div>
                </div>
              )}
            </div>

            {error && (
              <div
                className="px-3.5 py-2.5 rounded-lg text-xs font-mono border flex items-start gap-2"
                style={{ background: '#1a0a0a', borderColor: '#7f1d1d', color: '#fca5a5' }}
              >
                <span className="text-red-400 font-bold">⚠</span>
                <span>{error}</span>
              </div>
            )}

            {/* Start Button */}
            <button
              type="submit"
              disabled={loading || !url.trim()}
              className="w-full py-3.5 rounded-lg text-sm font-mono font-bold cursor-pointer
                         transition-all shadow-lg hover:shadow-indigo-500/25
                         disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              style={{
                background: loading ? '#4f52c4' : '#6366f1',
                color: '#fff',
              }}
            >
              {loading ? (
                <>
                  <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Initializing Test Engine...</span>
                </>
              ) : (
                <>
                  <span>▶ Start Autonomous Test</span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between text-xs font-mono text-slate-600 mt-6 px-2">
          <span>Real Browser Automation</span>
          <span>Zero Fake Data</span>
          <span>100% Deterministic Baseline</span>
        </div>
      </div>
    </div>
  )
}
