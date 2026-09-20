import React, { useEffect, useRef, useState } from 'react'
import type { AgentType, BrowserActionEvent, InteractiveElement } from '../types'

interface LiveBrowserViewProps {
  testId: string
  currentUrl: string
  pageTitle?: string
  statusCode?: number | null
  screenshotTimestamp: number
  activeAction?: BrowserActionEvent | null
  activeAgent?: AgentType
  elements?: InteractiveElement[]
  isLoading?: boolean
  error?: string | null
  viewport?: { width: number; height: number } | null
  onRefresh?: () => void
  onStopInspection?: () => void
  isStopping?: boolean
}

const AGENT_COLORS: Record<AgentType, string> = {
  technical: '#0284c7',      // Sky-600
  user_behavior: '#9333ea',  // Purple-600
  ux_ui: '#db2777',          // Pink-600
  chaos: '#ea580c',          // Orange-600
}

const AGENT_LABELS: Record<AgentType, string> = {
  technical: 'TECHNICAL',
  user_behavior: 'BEHAVIOR',
  ux_ui: 'VISUAL',
  chaos: 'CHAOS',
}

export function LiveBrowserView({
  testId,
  currentUrl,
  pageTitle,
  statusCode,
  screenshotTimestamp,
  activeAction,
  activeAgent = 'technical',
  elements = [],
  isLoading = false,
  error = null,
  viewport = { width: 1280, height: 720 },
  onRefresh,
  onStopInspection,
  isStopping = false,
}: LiveBrowserViewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const imageRef = useRef<HTMLImageElement>(null)

  // Image load / error tracking
  const [imageLoaded, setImageLoaded] = useState(false)
  const [imageError, setImageError] = useState(false)
  const [copiedUrl, setCopiedUrl] = useState(false)

  // Cursor position in rendered coordinates
  const [cursorPos, setCursorPos] = useState<{ x: number; y: number; visible: boolean }>({
    x: 200,
    y: 160,
    visible: true,
  })

  // Target lock-on bounding box
  const [targetBox, setTargetBox] = useState<{
    x: number
    y: number
    width: number
    height: number
    visible: boolean
    label: string
  }>({
    x: 0,
    y: 0,
    width: 0,
    height: 0,
    visible: false,
    label: '',
  })

  // Action feedback states
  const [isClicking, setIsClicking] = useState(false)
  const [isTyping, setIsTyping] = useState(false)
  const [isScrolling, setIsScrolling] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showAiVision, setShowAiVision] = useState(true)

  const nativeWidth = viewport?.width || 1280
  const nativeHeight = viewport?.height || 720

  useEffect(() => {
    setImageError(false)
  }, [screenshotTimestamp])

  // Calculate transformed cursor position & target lock box
  useEffect(() => {
    if (!activeAction) return

    const img = imageRef.current
    const container = containerRef.current
    if (!img && !container) return

    const rect = img && imageLoaded ? img.getBoundingClientRect() : container ? container.getBoundingClientRect() : null
    const renderedW = rect && rect.width > 50 ? rect.width : 760
    const renderedH = rect && rect.height > 50 ? rect.height : 480

    const scaleX = renderedW / nativeWidth
    const scaleY = renderedH / nativeHeight

    const rawX = activeAction.x ?? nativeWidth / 2
    const rawY = activeAction.y ?? nativeHeight / 2

    const mappedX = Math.max(10, Math.min(renderedW - 14, rawX * scaleX))
    const mappedY = Math.max(10, Math.min(renderedH - 14, rawY * scaleY))

    setCursorPos({
      x: mappedX,
      y: mappedY,
      visible: true,
    })

    const tb = activeAction.target_bounds
    if (tb && tb.width > 0 && tb.height > 0) {
      setTargetBox({
        x: Math.max(0, tb.x * scaleX),
        y: Math.max(0, tb.y * scaleY),
        width: Math.max(tb.width * scaleX, 18),
        height: Math.max(tb.height * scaleY, 16),
        visible: true,
        label: activeAction.target || activeAction.selector || 'TARGET',
      })
    } else if (activeAction.x !== undefined && activeAction.y !== undefined && activeAction.x !== null) {
      const approxW = Math.max(60 * scaleX, 40)
      const approxH = Math.max(26 * scaleY, 20)
      setTargetBox({
        x: Math.max(0, mappedX - approxW / 2),
        y: Math.max(0, mappedY - approxH / 2),
        width: approxW,
        height: approxH,
        visible: true,
        label: activeAction.target || activeAction.selector || 'TARGET',
      })
    } else {
      setTargetBox((prev) => ({ ...prev, visible: false }))
    }

    if (activeAction.action === 'click') {
      setIsClicking(true)
      const timer = setTimeout(() => setIsClicking(false), 600)
      return () => clearTimeout(timer)
    } else if (activeAction.action === 'type') {
      setIsTyping(true)
      const timer = setTimeout(() => setIsTyping(false), 950)
      return () => clearTimeout(timer)
    } else if (activeAction.action === 'scroll') {
      setIsScrolling(true)
      const timer = setTimeout(() => setIsScrolling(false), 750)
      return () => clearTimeout(timer)
    }
  }, [activeAction, nativeWidth, nativeHeight, imageLoaded])

  const currentAgentType = activeAction?.agent || activeAgent || 'technical'
  const agentColor = AGENT_COLORS[currentAgentType] || '#0284c7'
  const agentLabel = AGENT_LABELS[currentAgentType] || 'ENGINE'
  const isHttps = currentUrl.startsWith('https://')

  const phaseLabel = activeAction?.action === 'click'
    ? 'CLICK'
    : activeAction?.action === 'type'
    ? 'TYPE'
    : activeAction?.action === 'scroll'
    ? 'SCROLL'
    : 'OBSERVE'

  const isNearTop = cursorPos.y < 50
  const isNearRight = cursorPos.x > 480

  const handleCopyUrl = () => {
    if (!currentUrl) return
    navigator.clipboard.writeText(currentUrl)
    setCopiedUrl(true)
    setTimeout(() => setCopiedUrl(false), 1200)
  }

  return (
    <div
      ref={containerRef}
      className={`rounded border border-[#1c1e28] bg-[#101117] shadow-xs flex flex-col overflow-hidden select-none ${
        isFullscreen ? 'fixed inset-2 z-50 bg-[#0c0d10]' : ''
      }`}
    >
      {/* 1. Micro Console Titlebar */}
      <div className="px-2.5 py-1 border-b border-[#1a1c26] bg-[#141620] flex items-center justify-between gap-2 text-[9.5px]">
        {/* Navigation & Status */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="flex items-center gap-1">
            <div className="w-1.5 h-1.5 rounded-full bg-zinc-500" />
            <div className="w-1.5 h-1.5 rounded-full bg-zinc-500" />
            <div className="w-1.5 h-1.5 rounded-full bg-zinc-500" />
          </div>

          <button
            onClick={onRefresh}
            className="p-0.5 rounded hover:bg-[#1f2230] text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
            title="Refresh Live Frame"
          >
            [REFRESH]
          </button>
        </div>

        {/* Address Bar */}
        <div className="flex-1 min-w-[160px] max-w-md px-2 py-0.5 rounded bg-[#0b0c10] border border-[#1c1e28] flex items-center justify-between gap-1.5">
          <div className="flex items-center gap-1 min-w-0 flex-1">
            <span className="text-zinc-500 text-[9px]">{isHttps ? '🔒' : '🌐'}</span>
            <span className="text-[9.5px] font-mono text-zinc-200 truncate">{currentUrl || 'about:blank'}</span>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {statusCode && (
              <span
                className="text-[8.5px] px-1 py-0.2 rounded font-bold"
                style={{
                  color: statusCode < 300 ? '#34d399' : statusCode < 400 ? '#38bdf8' : '#f87171',
                  backgroundColor: `${statusCode < 300 ? '#34d399' : statusCode < 400 ? '#38bdf8' : '#f87171'}18`,
                }}
              >
                HTTP_{statusCode}
              </span>
            )}

            <button
              onClick={handleCopyUrl}
              className="text-[8.5px] text-zinc-400 hover:text-zinc-200 px-1 rounded hover:bg-[#1c1e28] transition-colors"
            >
              {copiedUrl ? 'COPIED' : 'COPY'}
            </button>
          </div>
        </div>

        {/* Right Tools Controls */}
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => setShowAiVision(!showAiVision)}
            className={`px-1.5 py-0.2 rounded text-[8.5px] font-mono font-bold transition-colors cursor-pointer ${
              showAiVision
                ? 'bg-indigo-950 text-indigo-300 border border-indigo-700'
                : 'bg-[#181a24] text-zinc-500 border border-[#242735]'
            }`}
          >
            DOM_OVERLAY:{showAiVision ? 'ON' : 'OFF'}
          </button>

          {onStopInspection && (
            <button
              onClick={onStopInspection}
              disabled={isStopping}
              className="px-1.5 py-0.2 rounded bg-rose-950 text-rose-300 border border-rose-800 hover:bg-rose-900 transition-colors text-[8.5px] font-bold cursor-pointer disabled:opacity-50"
            >
              {isStopping ? 'STOPPING...' : 'STOP'}
            </button>
          )}

          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="px-1.5 py-0.2 rounded bg-[#181a24] text-zinc-400 hover:text-zinc-200 transition-colors text-[8.5px] border border-[#242735] cursor-pointer"
          >
            {isFullscreen ? 'COLLAPSE' : 'EXPAND'}
          </button>
        </div>
      </div>

      {/* 2. Micro Telemetry Sub-strip */}
      <div className="px-2.5 py-0.5 border-b border-[#181a24] bg-[#0f1016] flex items-center justify-between text-[9px] text-zinc-400">
        {/* Phase Indicator */}
        <div className="flex items-center gap-1">
          <span
            className="w-1 h-1 rounded-full shrink-0"
            style={{ backgroundColor: agentColor }}
          />
          <span className="text-zinc-500">PHASE:</span>
          <span className="font-bold text-zinc-200" style={{ color: agentColor }}>
            [{phaseLabel}]
          </span>
        </div>

        {/* Target Element Info */}
        <div className="hidden sm:flex items-center gap-1 truncate max-w-xs">
          {targetBox.visible ? (
            <span className="truncate text-zinc-300">
              TARGET: <code className="text-zinc-100 bg-[#1a1c26] px-1 rounded">{targetBox.label}</code>
            </span>
          ) : (
            <span className="text-zinc-500">SURFACE_OBSERVATION</span>
          )}
        </div>

        {/* Viewport Info */}
        <div className="flex items-center gap-1.5 text-zinc-400">
          <span>{elements.length}_NODES</span>
          <span className="text-zinc-600">|</span>
          <span>{nativeWidth}×{nativeHeight}</span>
        </div>
      </div>

      {/* 3. Live Browser Viewport Canvas */}
      <div className="relative flex-1 min-h-[360px] bg-[#09090b] flex items-center justify-center overflow-hidden">
        {/* Connecting / Loading Canvas */}
        {(!imageLoaded || imageError) && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-3 text-center z-5">
            <div className="w-6 h-6 rounded-full border-2 border-zinc-700 border-t-indigo-500 animate-spin" />
            <div className="space-y-0.5">
              <div className="text-[10px] font-bold text-zinc-200">
                PLAYWRIGHT_CHROMIUM_VIEWPORT_SYNC...
              </div>
              <div className="text-[9px] text-zinc-500 truncate max-w-xs">
                {currentUrl || 'INITIALIZING_HEADLESS_PIPELINE'}
              </div>
            </div>
          </div>
        )}

        {/* Realtime Screenshot Frame */}
        <img
          ref={imageRef}
          src={`/api/tests/${testId}/screenshot?t=${screenshotTimestamp}`}
          alt=""
          onLoad={() => {
            setImageLoaded(true)
            setImageError(false)
          }}
          onError={() => {
            setImageError(true)
          }}
          className={`w-full h-full object-contain max-h-[540px] select-none pointer-events-none transition-opacity duration-150 ${
            imageLoaded && !imageError ? 'opacity-100' : 'opacity-0'
          }`}
        />

        {/* 4. DOM Elements Overlay */}
        {showAiVision && elements.length > 0 && imageLoaded && imageRef.current && (
          <div className="absolute inset-0 pointer-events-none z-15 overflow-hidden">
            {elements.slice(0, 30).map((el, i) => {
              const bbox = el.bounding_box || el.bounds
              if (!bbox || bbox.width <= 0 || bbox.height <= 0) return null

              const img = imageRef.current!
              const rect = img.getBoundingClientRect()
              const scaleX = rect.width / nativeWidth
              const scaleY = rect.height / nativeHeight

              const left = bbox.x * scaleX
              const top = bbox.y * scaleY
              const width = Math.max(bbox.width * scaleX, 4)
              const height = Math.max(bbox.height * scaleY, 4)

              return (
                <div
                  key={el.id || i}
                  className="absolute border border-indigo-500/20 bg-indigo-500/5 rounded-xs"
                  style={{
                    left: `${left}px`,
                    top: `${top}px`,
                    width: `${width}px`,
                    height: `${height}px`,
                  }}
                />
              )
            })}
          </div>
        )}

        {/* 5. Target Lock-on Reticle */}
        {targetBox.visible && (
          <div
            className="absolute pointer-events-none z-20 transition-all duration-200"
            style={{
              left: `${targetBox.x}px`,
              top: `${targetBox.y}px`,
              width: `${targetBox.width}px`,
              height: `${targetBox.height}px`,
            }}
          >
            <div
              className="absolute inset-0 rounded-xs border"
              style={{
                borderColor: agentColor,
                backgroundColor: `${agentColor}12`,
              }}
            />

            {/* Corner crosshairs */}
            <div className="absolute -top-0.5 -left-0.5 w-1 h-1 border-t border-l" style={{ borderColor: agentColor }} />
            <div className="absolute -top-0.5 -right-0.5 w-1 h-1 border-t border-r" style={{ borderColor: agentColor }} />
            <div className="absolute -bottom-0.5 -left-0.5 w-1 h-1 border-b border-l" style={{ borderColor: agentColor }} />
            <div className="absolute -bottom-0.5 -right-0.5 w-1 h-1 border-b border-r" style={{ borderColor: agentColor }} />

            {/* Target Label */}
            <div
              className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-1 py-0.2 rounded text-[7.5px] font-bold text-white whitespace-nowrap"
              style={{ backgroundColor: agentColor }}
            >
              {targetBox.label}
            </div>
          </div>
        )}

        {/* 6. Precision AI Cursor */}
        {cursorPos.visible && (
          <div
            className="absolute pointer-events-none z-30 transition-all duration-400 cubic-bezier(0.2, 0.9, 0.3, 1)"
            style={{
              left: 0,
              top: 0,
              transform: `translate3d(${cursorPos.x}px, ${cursorPos.y}px, 0)`,
            }}
          >
            {/* SVG Cursor Pointer */}
            <div className="relative">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                className="drop-shadow-xs -translate-x-0.5 -translate-y-0.5"
              >
                <path
                  d="M5.5 3.21V20.8c0 .45.54.67.85.35l4.62-4.62c.13-.13.3-.2.49-.2h6.36c.45 0 .67-.54.35-.85L5.85 3.21a.498.498 0 0 0-.35 0Z"
                  fill={agentColor}
                  stroke="#ffffff"
                  strokeWidth="1.5"
                  strokeLinejoin="round"
                />
              </svg>
            </div>

            {/* Floating Intent Tooltip */}
            <div
              className={`absolute px-1 py-0.2 rounded text-[8px] font-bold border border-zinc-700 bg-[#090a0f] text-zinc-200 whitespace-nowrap ${
                isNearTop ? 'top-4' : '-top-5'
              } ${isNearRight ? 'right-3 -translate-x-2' : 'left-3'}`}
            >
              <span style={{ color: agentColor }}>[{agentLabel}]</span>{' '}
              <span>
                {activeAction?.action === 'click'
                  ? `CLK(${activeAction.target || 'EL'})`
                  : activeAction?.action === 'type'
                  ? `INP("${activeAction.value || ''}")`
                  : activeAction?.action === 'scroll'
                  ? `SCR()`
                  : `OBS()`}
              </span>
            </div>

            {/* Click Ripple */}
            {isClicking && (
              <div
                className="absolute -left-2.5 -top-2.5 w-6 h-6 rounded-full border animate-ping pointer-events-none"
                style={{ borderColor: agentColor }}
              />
            )}
          </div>
        )}

        {/* 7. Bottom Action Reasoning Subtitle */}
        {activeAction && activeAction.reason && (
          <div className="absolute bottom-1.5 left-1.5 right-1.5 max-w-md mx-auto px-2 py-0.5 rounded border border-[#1f2230] bg-[#0c0d12]/95 text-[9px] text-zinc-300 shadow-md flex items-center gap-1 z-20">
            <span className="font-bold shrink-0" style={{ color: agentColor }}>
              [{agentLabel}]:
            </span>
            <span className="truncate">{activeAction.reason}</span>
          </div>
        )}

        {/* Error Banner */}
        {error && (
          <div className="absolute bottom-1.5 left-1.5 right-1.5 p-1.5 rounded bg-rose-950/90 border border-rose-800 text-rose-200 text-[9px] flex items-center gap-1 z-20">
            <span>ERR:</span>
            <span>{error}</span>
          </div>
        )}
      </div>
    </div>
  )
}
