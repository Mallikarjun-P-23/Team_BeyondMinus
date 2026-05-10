"use client"

import React, { createContext, useContext, useEffect, useState, useCallback } from "react"
import { SystemError } from "@/components/ErrorNotification"

interface ObserverContextType {
  errors: SystemError[]
  dismissError: (errorId: string) => void
  isConnected: boolean
  connectionError: string | null
}

const ObserverContext = createContext<ObserverContextType | undefined>(undefined)

export function useObserver() {
  const context = useContext(ObserverContext)
  if (!context) {
    throw new Error("useObserver must be used within an ObserverProvider")
  }
  return context
}

interface ObserverProviderProps {
  children: React.ReactNode
  wsUrl?: string
  maxErrors?: number
  autoConnect?: boolean
}

export function ObserverProvider({
  children,
  wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/monitoring/errors",
  maxErrors = 10,
  autoConnect = true,
}: ObserverProviderProps) {
  const [errors, setErrors] = useState<SystemError[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const wsRef = React.useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = React.useRef<NodeJS.Timeout | undefined>(undefined)
  const reconnectAttempts = React.useRef(0)

  const dismissError = useCallback((errorId: string) => {
    setErrors((prev) => prev.filter((e) => e.error_id !== errorId))
  }, [])

  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    console.log("[ObserverAgent] Connecting to WebSocket:", wsUrl)
    
    try {
      const ws = new WebSocket(wsUrl)
      
      ws.onopen = () => {
        console.log("[ObserverAgent] ✅ WebSocket connected")
        setIsConnected(true)
        setConnectionError(null)
        reconnectAttempts.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          
          console.log("[ObserverAgent] Message received:", message.type)

          if (message.type === "error") {
            const newError: SystemError = message.data
            
            // Only show errors to users with appropriate severity
            if (["critical", "error", "warning"].includes(newError.severity)) {
              setErrors((prev) => {
                const filtered = prev.filter((e) => e.error_id !== newError.error_id)
                return [...filtered, newError].slice(-maxErrors)
              })

              // Auto-dismiss warnings after 10 seconds
              if (newError.severity === "warning") {
                setTimeout(() => {
                  dismissError(newError.error_id)
                }, 10000)
              }
              
              // Auto-dismiss info after 5 seconds
              if (newError.severity === "info") {
                setTimeout(() => {
                  dismissError(newError.error_id)
                }, 5000)
              }
            }
          } else if (message.type === "connected") {
            console.log("[ObserverAgent] Connection confirmed:", message.message)
          } else if (message.type === "heartbeat") {
            // Heartbeat - connection is alive
          }
        } catch (err) {
          console.error("[ObserverAgent] Failed to parse message:", err)
        }
      }

      ws.onerror = (error) => {
        console.error("[ObserverAgent] ❌ WebSocket error:", error)
        setConnectionError("Connection error")
      }

      ws.onclose = () => {
        console.log("[ObserverAgent] WebSocket disconnected")
        setIsConnected(false)
        wsRef.current = null

        // Attempt to reconnect with exponential backoff
        if (autoConnect && reconnectAttempts.current < 10) {
          reconnectAttempts.current += 1
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)
          console.log(`[ObserverAgent] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current})`)
          
          reconnectTimeoutRef.current = setTimeout(() => {
            connectWebSocket()
          }, delay)
        }
      }

      wsRef.current = ws
    } catch (err) {
      console.error("[ObserverAgent] Failed to create WebSocket:", err)
      setConnectionError("Failed to connect")
    }
  }, [wsUrl, maxErrors, autoConnect, dismissError])

  useEffect(() => {
    if (autoConnect) {
      connectWebSocket()
    }

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [connectWebSocket, autoConnect])

  const value: ObserverContextType = {
    errors,
    dismissError,
    isConnected,
    connectionError,
  }

  return (
    <ObserverContext.Provider value={value}>
      {children}
    </ObserverContext.Provider>
  )
}
