"use client"

import * as React from "react"
import { XCircle, AlertTriangle, X } from "lucide-react"
import { Toast, ToastTitle, ToastDescription } from "@/components/ui/toast2"
import { RejectionNotification } from "@/hooks/useWorkflowRejectionHandler"

interface RejectionNotificationProps {
  rejection: RejectionNotification
  onDismiss: (id: string) => void
}

export function RejectionNotificationToast({
  rejection,
  onDismiss,
}: RejectionNotificationProps) {
  return (
    <Toast variant="error" onClose={() => onDismiss(rejection.id)}>
      <div className="flex gap-3">
        <XCircle className="h-5 w-5 shrink-0 mt-0.5" />
        <div className="flex-1 space-y-2">
          <ToastTitle className="flex items-center gap-2">
            <span>Workflow Generation Failed</span>
          </ToastTitle>
          <ToastDescription className="text-sm leading-relaxed">
            {rejection.assistant_message}
          </ToastDescription>
          
          {rejection.missing_context && rejection.missing_context.length > 0 && (
            <div className="mt-2 text-xs opacity-75">
              <div className="font-medium mb-1">Missing context:</div>
              <ul className="list-disc list-inside space-y-0.5">
                {rejection.missing_context.map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </ul>
            </div>
          )}
          
          {rejection.rejection_id && (
            <div className="text-xs opacity-50 font-mono mt-2">
              ID: {rejection.rejection_id}
            </div>
          )}
          
          <div className="text-xs opacity-50 mt-1">
            {rejection.timestamp.toLocaleTimeString()}
          </div>
        </div>
      </div>
    </Toast>
  )
}

interface RejectionToasterProps {
  rejections: RejectionNotification[]
  onDismiss: (id: string) => void
}

export function RejectionToaster({ rejections, onDismiss }: RejectionToasterProps) {
  return (
    <div className="fixed top-4 right-4 z-100 flex flex-col gap-2 max-w-md">
      {rejections.map((rejection) => (
        <RejectionNotificationToast
          key={rejection.id}
          rejection={rejection}
          onDismiss={onDismiss}
        />
      ))}
    </div>
  )
}
