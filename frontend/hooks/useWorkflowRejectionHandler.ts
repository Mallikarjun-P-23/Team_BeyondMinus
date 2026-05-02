"use client"

import { useState, useCallback } from "react"

export interface WorkflowRejection {
  status: "declined"
  assistant_message: string
  declined_reason: string
  rejection_id?: string
  missing_context?: string[]
  warnings?: string[]
}

export interface RejectionNotification extends WorkflowRejection {
  id: string
  timestamp: Date
}

export function useWorkflowRejectionHandler() {
  const [rejections, setRejections] = useState<RejectionNotification[]>([])

  const handleRejection = useCallback((rejection: WorkflowRejection) => {
    const notification: RejectionNotification = {
      ...rejection,
      id: rejection.rejection_id || `rej_${Date.now()}`,
      timestamp: new Date(),
    }

    setRejections((prev) => [...prev, notification])

    // Log to console for developers
    console.group("🚫 Workflow Generation Rejected")
    console.log("Rejection ID:", rejection.rejection_id)
    console.log("Reason:", rejection.declined_reason)
    console.log("User Message:", rejection.assistant_message)
    if (rejection.missing_context) {
      console.log("Missing Context:", rejection.missing_context)
    }
    if (rejection.warnings) {
      console.log("Warnings:", rejection.warnings)
    }
    console.groupEnd()

    // Auto-dismiss after 10 seconds
    setTimeout(() => {
      dismissRejection(notification.id)
    }, 10000)
  }, [])

  const dismissRejection = useCallback((id: string) => {
    setRejections((prev) => prev.filter((r) => r.id !== id))
  }, [])

  return {
    rejections,
    handleRejection,
    dismissRejection,
    clearAllRejections: () => setRejections([]),
  }
}
