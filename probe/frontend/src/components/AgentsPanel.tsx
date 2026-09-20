import React from 'react'
import type { AgentType, AgentState } from '../types'

interface AgentsPanelProps {
  activeAgent: AgentType
  agentStates: Record<AgentType, AgentState>
  currentMessage?: string
}

interface AgentMeta {
  id: AgentType
  name: string
  role: string
  description: string
}

const AGENTS: AgentMeta[] = [
  {
    id: 'technical',
    name: 'TECHNICAL.01',
    role: 'DOM & Network Telemetry',
    description: 'DOM hierarchy, HTTP requests, console logs & JS errors.',
  },
  {
    id: 'user_behavior',
    name: 'BEHAVIOR.02',
    role: 'User Journey Simulation',
    description: 'Interactive inputs, form workflows, and navigation paths.',
  },
  {
    id: 'ux_ui',
    name: 'VISUAL.03',
    role: 'Viewport & Layout Stability',
    description: 'Viewport stability, responsive scroll, and below-the-fold layout.',
  },
  {
    id: 'chaos',
    name: 'CHAOS.04',
    role: 'Fuzzing & Boundary Testing',
    description: 'Edge inputs, boundary mutations, and state perturbations.',
  },
]

export function AgentsPanel({ activeAgent, agentStates, currentMessage }: AgentsPanelProps) {
  const currentActiveMeta = AGENTS.find((a) => a.id === activeAgent) || AGENTS[0]

  return (
    <div className="bg-[#101117] border border-[#1c1e28] rounded p-2 shadow-xs select-none">
      {/* Micro Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 pb-1.5 border-b border-[#1a1c26] text-[9.5px]">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-bold text-zinc-200 tracking-wider">
            SWARM_ORCHESTRATOR
          </span>
          <span className="px-1 rounded bg-[#181a24] text-zinc-400 border border-[#242735]">
            4_NODES
          </span>
        </div>

        {/* Live Intent Ticker */}
        <div className="flex items-center gap-1.5 text-zinc-400 truncate max-w-lg bg-[#0b0c10] px-2 py-0.5 rounded border border-[#1a1c26]">
          <span className="text-zinc-500 font-bold shrink-0">INTENT:</span>
          <span className="text-zinc-200 truncate">
            {currentMessage || `Active state exploration via ${currentActiveMeta.name}`}
          </span>
        </div>
      </div>

      {/* 4 Agent Robotic Cards Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-1.5 mt-1.5">
        {AGENTS.map((agent) => {
          const isActive = activeAgent === agent.id
          const state: AgentState = agentStates[agent.id] || (isActive ? 'exploring' : 'waiting')

          return (
            <div
              key={agent.id}
              className={`rounded border p-1.5 transition-colors flex flex-col justify-between ${
                isActive
                  ? 'bg-[#151722] border-indigo-600/60 shadow-xs'
                  : 'bg-[#0d0e13] border-[#181a24] opacity-75 hover:opacity-100'
              }`}
            >
              <div>
                {/* Top Node Row */}
                <div className="flex items-center justify-between gap-1 mb-0.5">
                  <div className="flex items-center gap-1 min-w-0">
                    <span
                      className="w-1 h-1 rounded-full shrink-0"
                      style={{
                        backgroundColor: isActive ? '#10b981' : '#4b5563',
                      }}
                    />
                    <span className="text-[10px] font-bold text-zinc-100 truncate tracking-wide">
                      {agent.name}
                    </span>
                  </div>

                  <span
                    className={`text-[8px] px-1 py-0.2 rounded uppercase font-bold tracking-wider ${
                      isActive
                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                        : 'bg-[#181a24] text-zinc-500 border border-[#242735]'
                    }`}
                  >
                    {state}
                  </span>
                </div>

                {/* Subtitle Role */}
                <div className="text-[9px] text-zinc-400 truncate">
                  {agent.role}
                </div>

                {/* Micro Description */}
                <p className="text-[8.5px] text-zinc-500 leading-tight line-clamp-1 mt-0.5">
                  {isActive && currentMessage ? currentMessage : agent.description}
                </p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
