// SSE hook — subscribes to the backend event stream for a test

import { useEffect, useRef, useState } from 'react'
import type { SSEEvent } from '../types'

export interface UseTestEventsOptions {
  onEvent?: (event: SSEEvent) => void
}

export function useTestEvents(testId: string | null, options?: UseTestEventsOptions) {
  const [events, setEvents] = useState<SSEEvent[]>([])
  const esRef = useRef<EventSource | null>(null)
  const onEventRef = useRef(options?.onEvent)

  useEffect(() => {
    onEventRef.current = options?.onEvent
  }, [options?.onEvent])

  useEffect(() => {
    if (!testId) return

    const es = new EventSource(`/api/tests/${testId}/events`)
    esRef.current = es

    es.onmessage = (e) => {
      try {
        const event: SSEEvent = JSON.parse(e.data)
        setEvents((prev) => [...prev, event])
        if (onEventRef.current) {
          onEventRef.current(event)
        }
      } catch {
        // ignore parse errors
      }
    }

    es.onerror = () => {
      es.close()
    }

    return () => {
      es.close()
      esRef.current = null
    }
  }, [testId])

  const clearEvents = () => setEvents([])

  return { events, clearEvents }
}
