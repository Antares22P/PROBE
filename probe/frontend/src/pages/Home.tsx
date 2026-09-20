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
      setError(err instanceof Error ? err.message : 'Failed to start test session')
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col items-center justify-center flex-1 px-4 py-12">
      <div className="w-full max-w-xl">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="inline-flex items-center gap-2 mb-3">
            <span className="font-mono text-xs font-semibold px-2.5 py-1 rounded bg-zinc-800 text-zinc-300 border border-zinc-700/80">
              PROBE Autonomous Engine
            </span>
          </div>
          <h1 className="text-2xl font-bold text-zinc-100 tracking-tight">
            Web Reliability & Issue Discovery
          </h1>
          <p className="text-zinc-400 text-xs font-mono mt-2 max-w-md mx-auto leading-relaxed">
            Real Playwright Chromium automation · Multi-agent state exploration · Deterministic telemetry capture
          </p>
        </div>

        {/* Form Card */}
        <div className="bg-[#121216] border border-zinc-800 rounded-xl p-6 shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Target URL */}
            <div>
              <label
                htmlFor="target-url"
                className="block text-xs font-mono font-medium text-zinc-300 mb-1.5 uppercase tracking-wider"
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
                  className="w-full px-3.5 py-2.5 rounded-lg text-sm font-mono text-zinc-100 placeholder-zinc-500 bg-zinc-900 border border-zinc-700/80 focus:border-indigo-500 focus:outline-none transition-colors disabled:opacity-50"
                />
              </div>
            </div>

            {/* Scan Presets */}
            <div>
              <div className="text-[11px] font-mono text-zinc-400 mb-2 uppercase tracking-wide">
                Inspection Preset
              </div>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => applyPreset(30, 15, 10, 3)}
                  className={`p-2.5 rounded-lg border text-left transition-colors cursor-pointer ${
                    durationSeconds === 30 && maxActions === 15
                      ? 'bg-zinc-800 border-zinc-600 text-zinc-100'
                      : 'bg-zinc-900/60 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900'
                  }`}
                >
                  <div className="text-xs font-semibold font-mono">Quick Scan</div>
                  <div className="text-[10px] text-zinc-500 font-mono mt-0.5">30s · 15 actions</div>
                </button>

                <button
                  type="button"
                  onClick={() => applyPreset(180, 50, 25, 5)}
                  className={`p-2.5 rounded-lg border text-left transition-colors cursor-pointer ${
                    durationSeconds === 180 && maxActions === 50
                      ? 'bg-zinc-800 border-zinc-600 text-zinc-100'
                      : 'bg-zinc-900/60 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900'
                  }`}
                >
                  <div className="text-xs font-semibold font-mono">Standard</div>
                  <div className="text-[10px] text-zinc-500 font-mono mt-0.5">180s · 50 actions</div>
                </button>

                <button
                  type="button"
                  onClick={() => applyPreset(300, 100, 40, 8)}
                  className={`p-2.5 rounded-lg border text-left transition-colors cursor-pointer ${
                    durationSeconds === 300 && maxActions === 100
                      ? 'bg-zinc-800 border-zinc-600 text-zinc-100'
                      : 'bg-zinc-900/60 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900'
                  }`}
                >
                  <div className="text-xs font-semibold font-mono">Deep Audit</div>
                  <div className="text-[10px] text-zinc-500 font-mono mt-0.5">300s · 100 actions</div>
                </button>
              </div>
            </div>

            {/* Advanced Exploration Config */}
            <div className="pt-1">
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center gap-2 text-xs font-mono text-zinc-400 hover:text-zinc-200 transition-colors py-1 cursor-pointer"
              >
                <span className="text-[10px] text-zinc-500 font-bold">
                  {showAdvanced ? '▼' : '▶'}
                </span>
                <span>Advanced Exploration Configuration</span>
              </button>

              {showAdvanced && (
                <div className="mt-3 p-4 rounded-lg bg-zinc-900 border border-zinc-800 space-y-3.5">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label
                        htmlFor="test-duration"
                        className="block text-[11px] font-mono text-zinc-400 mb-1"
                      >
                        Duration Timeout (sec)
                      </label>
                      <input
                        id="test-duration"
                        type="number"
                        min={10}
                        max={600}
                        value={durationSeconds}
                        onChange={(e) => setDurationSeconds(Math.max(10, Number(e.target.value)))}
                        className="w-full px-2.5 py-1.5 rounded text-xs font-mono text-zinc-100 bg-zinc-950 border border-zinc-700/80 focus:border-indigo-500 focus:outline-none"
                      />
                    </div>

                    <div>
                      <label
                        htmlFor="max-actions"
                        className="block text-[11px] font-mono text-zinc-400 mb-1"
                      >
                        Max Actions
                      </label>
                      <input
                        id="max-actions"
                        type="number"
                        min={1}
                        max={300}
                        value={maxActions}
                        onChange={(e) => setMaxActions(Math.max(1, Number(e.target.value)))}
                        className="w-full px-2.5 py-1.5 rounded text-xs font-mono text-zinc-100 bg-zinc-950 border border-zinc-700/80 focus:border-indigo-500 focus:outline-none"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label
                        htmlFor="max-states"
                        className="block text-[11px] font-mono text-zinc-400 mb-1"
                      >
                        Max States
                      </label>
                      <input
                        id="max-states"
                        type="number"
                        min={1}
                        max={150}
                        value={maxStates}
                        onChange={(e) => setMaxStates(Math.max(1, Number(e.target.value)))}
                        className="w-full px-2.5 py-1.5 rounded text-xs font-mono text-zinc-100 bg-zinc-950 border border-zinc-700/80 focus:border-indigo-500 focus:outline-none"
                      />
                    </div>

                    <div>
                      <label
                        htmlFor="max-depth"
                        className="block text-[11px] font-mono text-zinc-400 mb-1"
                      >
                        Max DOM Depth
                      </label>
                      <input
                        id="max-depth"
                        type="number"
                        min={1}
                        max={20}
                        value={maxDepth}
                        onChange={(e) => setMaxDepth(Math.max(1, Number(e.target.value)))}
                        className="w-full px-2.5 py-1.5 rounded text-xs font-mono text-zinc-100 bg-zinc-950 border border-zinc-700/80 focus:border-indigo-500 focus:outline-none"
                      />
                    </div>
                  </div>

                  <label className="flex items-center gap-2 text-xs font-mono text-zinc-300 pt-1 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={headless}
                      onChange={(e) => setHeadless(e.target.checked)}
                      className="rounded bg-zinc-800 border-zinc-700 text-indigo-600 focus:ring-0 cursor-pointer"
                    />
                    <span>Run Headless Chromium (Recommended for background execution)</span>
                  </label>
                </div>
              )}
            </div>

            {/* Error Display */}
            {error && (
              <div className="p-3 rounded-lg bg-rose-950/80 border border-rose-800 text-xs font-mono text-rose-200">
                {error}
              </div>
            )}

            {/* Launch Button */}
            <button
              type="submit"
              disabled={loading || !url.trim()}
              className="w-full py-2.5 rounded-lg text-xs font-mono font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Initializing Test Engine...</span>
                </>
              ) : (
                <span>Launch Inspection Session →</span>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
