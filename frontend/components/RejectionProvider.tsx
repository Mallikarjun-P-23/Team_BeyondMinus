"use client"

import React, { createContext, useContext } from "react"
import { useWorkflowRejectionHandler, WorkflowRejection, RejectionNotification } from "@/hooks/useWorkflowRejectionHandler"
import { RejectionToaster } from "@/components/RejectionNotification"

interface RejectionContextType {
  rejections: RejectionNotification[]
  handleRejection: (rejection: WorkflowRejection) => void
  dismissRejection: (id: string) => void
  clearAllRejections: () => void
}

const RejectionContext = createContext<RejectionContextType | undefined>(undefined)

export function useRejections() {
  const context = useContext(RejectionContext)
  if (!context) {
    throw new Error("useRejections must be used within a RejectionProvider")
  }
  return context
}

interface RejectionProviderProps {
  children: React.ReactNode
}

export function RejectionProvider({ children }: RejectionProviderProps) {
  const rejectionHandler = useWorkflowRejectionHandler()

  return (
    <RejectionContext.Provider value={rejectionHandler}>
      {children}
      <RejectionToaster
        rejections={rejectionHandler.rejections}
        onDismiss={rejectionHandler.dismissRejection}
      />
    </RejectionContext.Provider>
  )
}
