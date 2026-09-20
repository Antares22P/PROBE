import React from 'react'
import type { TestSummaryAnalysis } from '../types'

interface AiModelReportProps {
  aiSummary: TestSummaryAnalysis | null
  testStatus: string
  findingsCount: number
  actionsCount: number
  statesCount: number
  targetUrl: string
  onGenerateReport: () => void
  isGenerating: boolean
  error?: string | null
}

export function AiModelReport({
  aiSummary,
  testStatus,
  findingsCount,
  actionsCount,
  statesCount,
  targetUrl,
  onGenerateReport,
  isGenerating,
  error,
}: AiModelReportProps) {
  const isRunning = testStatus === 'running'
  const isCompleted = testStatus === 'completed' || testStatus === 'failed' || testStatus === 'cancelled'

  const health = aiSummary?.overall_health?.toLowerCase() || 'unknown'
  const isHealthy = health === 'healthy' || health === 'optimal'
  const isDegraded = health === 'degraded' || health === 'warning'
  const isCritical = health.includes('critical') || health === 'danger' || health === 'failed'

  const getHealthBadge = () => {
    if (isHealthy) {
      return {
        label: 'HEALTH: OPTIMAL',
        sub: 'NO CRITICAL REGRESSIONS',
        color: 'text-emerald-400',
        bg: 'bg-emerald-950/40 border-emerald-800/80',
        accent: '#10b981',
      }
    }
    if (isDegraded) {
      return {
        label: 'HEALTH: DEGRADED',
        sub: 'WARNINGS & ANOMALIES IDENTIFIED',
        color: 'text-amber-400',
        bg: 'bg-amber-950/40 border-amber-800/80',
        accent: '#f59e0b',
      }
    }
    if (isCritical) {
      return {
        label: 'HEALTH: CRITICAL',
        sub: 'HIGH-SEVERITY DEFECTS DETECTED',
        color: 'text-rose-400',
        bg: 'bg-rose-950/40 border-rose-800/80',
        accent: '#f43f5e',
      }
    }
    return {
      label: `HEALTH: ${health.toUpperCase()}`,
      sub: 'AI EVALUATION RECORDED',
      color: 'text-zinc-300',
      bg: 'bg-zinc-900 border-zinc-700',
      accent: '#6366f1',
    }
  }

  const badge = getHealthBadge()
  const modelName = aiSummary?.model_name || 'gemini-2.5-flash'
  const analyzedAt = aiSummary?.analyzed_at
    ? new Date(aiSummary.analyzed_at).toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    : null

  return (
    <div className="bg-[#101117] border border-[#1c1e28] rounded p-3 shadow-xs space-y-2.5 select-none font-mono text-[10px]">
      {/* ------------------------------------------------------------------- */}
      {/* 1. TOP HEADER & MODEL BENCHMARK BAR                                 */}
      {/* ------------------------------------------------------------------- */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-[#1a1c26]">
        <div className="flex items-center gap-2 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
            <span className="font-bold text-zinc-100 tracking-wider text-[11px]">
              AI_MODEL_INSPECTION_REPORT
            </span>
          </div>

          <span className="px-1.5 py-0.2 rounded bg-indigo-950/60 text-indigo-300 border border-indigo-800/80 text-[8.5px] font-bold uppercase">
            MODEL: {modelName.toUpperCase()}
          </span>

          {analyzedAt && (
            <span className="text-zinc-500 text-[8.5px] hidden sm:inline">
              SYNTHESIZED: {analyzedAt}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {aiSummary && (
            <span className={`px-2 py-0.5 rounded text-[8.5px] font-bold border ${badge.bg} ${badge.color}`}>
              {badge.label}
            </span>
          )}

          <button
            onClick={onGenerateReport}
            disabled={isGenerating || isRunning}
            className={`px-2 py-0.5 rounded text-[8.5px] font-bold uppercase transition-all flex items-center gap-1 cursor-pointer ${
              isGenerating
                ? 'bg-indigo-950 text-indigo-400 border border-indigo-800 cursor-not-allowed'
                : isRunning
                ? 'bg-[#181a24] text-zinc-600 border border-[#242735] cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-500 text-white border border-indigo-400/50 shadow-xs active:scale-95'
            }`}
            title={isRunning ? 'Available when scan completes' : 'Run Gemini AI reasoning over all collected signals'}
          >
            {isGenerating ? (
              <>
                <span className="inline-block w-2 h-2 border-2 border-indigo-300 border-t-transparent rounded-full animate-spin" />
                <span>SYNTHESIZING...</span>
              </>
            ) : (
              <>
                <span>✨</span>
                <span>{aiSummary ? 'RE-RUN AI ANALYSIS' : 'GENERATE AI REPORT'}</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* 2. SCAN TELEMETRY SUMMARY STRIP                                     */}
      {/* ------------------------------------------------------------------- */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 text-[9px]">
        <div className="p-1.5 rounded bg-[#0d0e14] border border-[#181a24]">
          <div className="text-zinc-500 uppercase text-[8.5px]">Target URL</div>
          <div className="text-zinc-200 font-semibold truncate mt-0.5" title={targetUrl}>
            {targetUrl}
          </div>
        </div>

        <div className="p-1.5 rounded bg-[#0d0e14] border border-[#181a24] flex items-center justify-between">
          <div>
            <div className="text-zinc-500 uppercase text-[8.5px]">Explored States</div>
            <div className="text-zinc-200 font-semibold mt-0.5">{statesCount} Viewports</div>
          </div>
          <span className="text-indigo-400 font-bold text-[10px]">DOM_MAP</span>
        </div>

        <div className="p-1.5 rounded bg-[#0d0e14] border border-[#181a24] flex items-center justify-between">
          <div>
            <div className="text-zinc-500 uppercase text-[8.5px]">Autonomous Actions</div>
            <div className="text-zinc-200 font-semibold mt-0.5">{actionsCount} Executions</div>
          </div>
          <span className="text-purple-400 font-bold text-[10px]">SWARM</span>
        </div>

        <div className="p-1.5 rounded bg-[#0d0e14] border border-[#181a24] flex items-center justify-between">
          <div>
            <div className="text-zinc-500 uppercase text-[8.5px]">Defects Identified</div>
            <div
              className={`font-semibold mt-0.5 ${
                findingsCount > 0 ? 'text-rose-400' : 'text-emerald-400'
              }`}
            >
              {findingsCount} Findings
            </div>
          </div>
          <span
            className={`font-bold text-[10px] ${
              findingsCount > 0 ? 'text-rose-400' : 'text-emerald-400'
            }`}
          >
            {findingsCount > 0 ? 'FLAGGED' : 'CLEAN'}
          </span>
        </div>
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* 3. REPORT CONTENT STATES                                            */}
      {/* ------------------------------------------------------------------- */}

      {/* Case A: Scan in progress */}
      {isRunning && (
        <div className="p-4 rounded bg-[#0b0c10] border border-dashed border-[#242735] text-center space-y-1.5">
          <div className="flex items-center justify-center gap-2 text-indigo-400 font-bold text-[10.5px]">
            <span className="w-2 h-2 rounded-full bg-indigo-500 animate-ping" />
            <span>AI SCAN IN PROGRESS — ACTIVE AGENT TELEMETRY RUNNING</span>
          </div>
          <p className="text-zinc-500 text-[9.5px] max-w-md mx-auto">
            The multi-agent swarm is currently interacting with the application DOM, recording network telemetry, and checking for UI/functional defects. Full AI model summary report will synthesize automatically once exploration concludes.
          </p>
        </div>
      )}

      {/* Case B: Completed but no summary yet */}
      {!isRunning && !aiSummary && !isGenerating && (
        <div className="p-4 rounded bg-[#0b0c10] border border-[#1c1e28] text-center space-y-2">
          <div className="text-zinc-400 font-bold text-[10.5px]">
            AI MODEL SYNTHESIS READY
          </div>
          <p className="text-zinc-500 text-[9.5px] max-w-md mx-auto">
            Scan completed with {actionsCount} actions and {findingsCount} detected issues. Click below to generate an AI executive audit report powered by {modelName}.
          </p>
          <button
            onClick={onGenerateReport}
            className="px-3 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-[9.5px] uppercase transition-colors cursor-pointer"
          >
            ✨ Run AI Diagnostic Model Analysis
          </button>
        </div>
      )}

      {/* Case C: Error display if any */}
      {error && (
        <div className="p-2 rounded bg-rose-950/20 border border-rose-900/60 text-rose-300 text-[9.5px] flex items-center justify-between">
          <span>AI Analysis Error: {error}</span>
          <button
            onClick={onGenerateReport}
            className="text-rose-400 underline font-bold uppercase cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {/* Case D: AI Summary Report Available */}
      {aiSummary && (
        <div className="space-y-2.5">
          {/* Key Diagnostic Sections Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {/* 1. Key Takeaways */}
            <div className="p-2.5 rounded bg-[#0d0e14] border border-[#181a24] space-y-1.5">
              <div className="flex items-center gap-1.5 text-indigo-300 font-bold uppercase text-[9.5px] pb-1 border-b border-[#181a24]">
                <span>[✓]</span>
                <span>KEY_OBSERVATIONS & SYNTHESIS</span>
              </div>
              {aiSummary.key_takeaways && aiSummary.key_takeaways.length > 0 ? (
                <ul className="space-y-1 text-zinc-300 text-[9.5px]">
                  {aiSummary.key_takeaways.map((takeaway, idx) => (
                    <li key={idx} className="flex items-start gap-1.5 leading-snug">
                      <span className="text-indigo-400 shrink-0 select-none">•</span>
                      <span>{takeaway}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-zinc-600 text-[9px]">No specific takeaways recorded.</p>
              )}
            </div>

            {/* 2. Top Identified Risks */}
            <div className="p-2.5 rounded bg-[#0d0e14] border border-[#181a24] space-y-1.5">
              <div className="flex items-center gap-1.5 text-rose-300 font-bold uppercase text-[9.5px] pb-1 border-b border-[#181a24]">
                <span>[⚠]</span>
                <span>IDENTIFIED_RISKS & ANOMALIES</span>
              </div>
              {aiSummary.top_risks && aiSummary.top_risks.length > 0 ? (
                <ul className="space-y-1 text-zinc-300 text-[9.5px]">
                  {aiSummary.top_risks.map((risk, idx) => (
                    <li key={idx} className="flex items-start gap-1.5 leading-snug">
                      <span className="text-rose-400 shrink-0 select-none">▲</span>
                      <span>{risk}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-emerald-400/80 text-[9px]">
                  ✓ No severe risks or vulnerabilities flagged during inspection.
                </p>
              )}
            </div>

            {/* 3. Actionable Remediations */}
            <div className="p-2.5 rounded bg-[#0d0e14] border border-[#181a24] space-y-1.5">
              <div className="flex items-center gap-1.5 text-emerald-300 font-bold uppercase text-[9.5px] pb-1 border-b border-[#181a24]">
                <span>[➜]</span>
                <span>RECOMMENDED_ACTIONS</span>
              </div>
              {aiSummary.recommended_actions && aiSummary.recommended_actions.length > 0 ? (
                <ul className="space-y-1 text-zinc-300 text-[9.5px]">
                  {aiSummary.recommended_actions.map((action, idx) => (
                    <li key={idx} className="flex items-start gap-1.5 leading-snug">
                      <span className="text-emerald-400 shrink-0 select-none">→</span>
                      <span>{action}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-zinc-600 text-[9px]">No immediate actions recommended.</p>
              )}
            </div>
          </div>

          {/* Model Evaluation Stamp Footer */}
          <div className="flex flex-wrap items-center justify-between gap-2 p-1.5 rounded bg-[#0b0c10] border border-[#181a24] text-[8.5px] text-zinc-500">
            <div className="flex items-center gap-2">
              <span className="text-zinc-400 font-semibold">REASONING ENGINE:</span>
              <span className="text-indigo-300 font-mono">{modelName}</span>
              <span>|</span>
              <span className="text-zinc-400 font-semibold">CONFIDENCE:</span>
              <span className="text-emerald-400 font-mono">HIGH_FIDELITY</span>
            </div>

            <div className="flex items-center gap-1">
              <span>STATUS:</span>
              <span className="text-zinc-300 font-semibold uppercase">{health}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
