import React, { useEffect, useMemo, useRef, useState } from 'react'
import type { AgentType } from '../types'

export interface TimelineEntry {
  id: string
  time: string
  type: 'action' | 'observation' | 'finding' | 'signal' | 'agent' | 'status'
  agent?: AgentType | string
  label: string
  detail?: string
  success?: boolean
  color?: string
}

interface LiveActivityTimelineProps {
  events: TimelineEntry[]
  activeAgent?: AgentType
}

export function LiveActivityTimeline({ events, activeAgent }: LiveActivityTimelineProps) {
  const [filter, setFilter] = useState<'all' | 'actions' | 'findings' | 'signals'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [autoScroll, setAutoScroll] = useState(true)
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  const filteredEvents = useMemo(() => {
    return events.filter((ev) => {
      if (filter === 'actions' && ev.type !== 'action' && ev.type !== 'agent') return false
      if (filter === 'findings' && ev.type !== 'finding') return false
      if (filter === 'signals' && ev.type !== 'signal' && ev.type !== 'observation') return false

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        const matchLabel = ev.label.toLowerCase().includes(q)
        const matchDetail = ev.detail?.toLowerCase().includes(q) || false
        const matchAgent = ev.agent?.toLowerCase().includes(q) || false
        if (!matchLabel && !matchDetail && !matchAgent) return false
      }

      return true
    })
  }, [events, filter, searchQuery])

  useEffect(() => {
    if (autoScroll && scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight
    }
  }, [filteredEvents, autoScroll])

  const getActionBadge = (ev: TimelineEntry) => {
    if (ev.type === 'finding') {
      return { label: 'FINDING', bg: 'bg-rose-950 text-rose-300 border-rose-800' }
    }
    if (ev.type === 'observation') {
      return { label: 'OBSERVE', bg: 'bg-sky-950 text-sky-300 border-sky-800' }
    }
    if (ev.type === 'agent') {
      return { label: 'SWARM', bg: 'bg-purple-950 text-purple-300 border-purple-800' }
    }
    const lower = ev.label.toLowerCase()
    if (lower.includes('click')) return { label: 'CLICK', bg: 'bg-indigo-950 text-indigo-300 border-indigo-800' }
    if (lower.includes('type') || lower.includes('input')) return { label: 'TYPE', bg: 'bg-violet-950 text-violet-300 border-violet-800' }
    if (lower.includes('scroll')) return { label: 'SCROLL', bg: 'bg-pink-950 text-pink-300 border-pink-800' }
    if (lower.includes('navigate')) return { label: 'NAVIGATE', bg: 'bg-blue-950 text-blue-300 border-blue-800' }
    return { label: 'ACTION', bg: 'bg-zinc-800 text-zinc-300 border-zinc-700' }
  }

  return (
    <div className="bg-[#101117] border border-[#1c1e28] rounded p-2 shadow-xs flex flex-col h-full min-h-[440px] max-h-[580px] select-none">
      {/* Micro Header */}
      <div className="flex items-center justify-between pb-1.5 border-b border-[#1a1c26] shrink-0 text-[9.5px]">
        <div className="flex items-center gap-1.5">
          <span className="font-bold text-zinc-200 tracking-wider">EVENT_STREAM</span>
          <span className="px-1 py-0.2 rounded bg-[#181a24] text-zinc-400 border border-[#242735]">
            {events.length}
          </span>
        </div>

        <label className="flex items-center gap-1 text-zinc-400 cursor-pointer hover:text-zinc-200">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
            className="rounded bg-zinc-800 border-zinc-700 text-indigo-600 focus:ring-0 w-2.5 h-2.5 cursor-pointer"
          />
          <span>AUTO_SCROLL</span>
        </label>
      </div>

      {/* Filter Tabs & Search Bar */}
      <div className="flex items-center justify-between gap-1.5 pt-1.5 pb-1.5 border-b border-[#181a24] shrink-0 text-[9px]">
        <div className="flex items-center gap-0.5 bg-[#0b0c10] p-0.5 rounded border border-[#1c1e28]">
          {(['all', 'actions', 'findings', 'signals'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-1.5 py-0.2 rounded uppercase transition-colors cursor-pointer ${
                filter === f
                  ? 'bg-[#202330] text-white font-bold'
                  : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative flex-1 max-w-[110px]">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search..."
            className="w-full text-[9px] font-mono bg-[#0b0c10] border border-[#1c1e28] rounded px-1.5 py-0.5 text-zinc-200 placeholder-zinc-600 focus:border-indigo-500 focus:outline-none"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-1 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 text-[9px]"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Event Stream Log */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto mt-1 pr-1 space-y-1 custom-scrollbar min-h-0 text-[9.5px]"
      >
        {filteredEvents.length === 0 ? (
          <div className="p-4 text-center text-zinc-600">
            {searchQuery ? 'NO_MATCHING_RECORDS' : 'AWAITING_STREAM_TELEMETRY...'}
          </div>
        ) : (
          filteredEvents.map((ev) => {
            const badge = getActionBadge(ev)
            const isFinding = ev.type === 'finding'

            return (
              <div
                key={ev.id}
                className={`p-1.5 rounded border transition-colors ${
                  isFinding
                    ? 'bg-rose-950/20 border-rose-900/60'
                    : 'bg-[#0d0e14] border-[#181a24] hover:bg-[#13151f]'
                }`}
              >
                <div className="flex items-center justify-between text-[8.5px] text-zinc-500 mb-0.5">
                  <div className="flex items-center gap-1 truncate">
                    <span className={`px-1 py-0.2 rounded font-bold border ${badge.bg}`}>
                      {badge.label}
                    </span>
                    {ev.agent && (
                      <span className="text-zinc-400 truncate max-w-[80px]">
                        {ev.agent.replace('_', ' ')}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-1 shrink-0">
                    <span>{ev.time}</span>
                    {ev.success !== undefined && (
                      <span
                        className={`font-bold ${
                          ev.success ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {ev.success ? 'OK' : 'ERR'}
                      </span>
                    )}
                  </div>
                </div>

                {/* Event Description */}
                <div className="text-zinc-200 font-medium leading-snug break-words">
                  {ev.label}
                </div>

                {/* Event Metadata detail */}
                {ev.detail && (
                  <div className="text-[8.5px] text-zinc-400 mt-0.5 pl-1 border-l border-zinc-700/60 leading-tight">
                    {ev.detail}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
