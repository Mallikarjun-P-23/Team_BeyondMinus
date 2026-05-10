"use client"

import * as React from "react"
import { AlertTriangle, XCircle, AlertCircle, Info, CheckCircle } from "lucide-react"
import {
  Toast,
  ToastTitle,
  ToastDescription,
  type ToastActionElement,
} from "@/components/ui/toast"

export interface SystemError {
  error_id: string
  category: string
  severity: "critical" | "error" | "warning" | "info" | "debug"
  message: string
  details?: Record<string, any>
  stack_trace?: string
  context?: Record<string, any>
  timestamp: string
}

interface ErrorNotificationProps {
  error: SystemError
  onClose: () => void
  action?: ToastActionElement
}

const severityIcons = {
  critical: XCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
  debug: Info,
}

const severityLabels = {
  critical: "Critical Error",
  error: "Error",
  warning: "Warning",
  info: "Information",
  debug: "Debug",
}

export function ErrorNotification({
  error,
  onClose,
  action,
}: ErrorNotificationProps) {
  const Icon = severityIcons[error.severity] || AlertCircle
  const variant = error.severity === "debug" ? "info" : error.severity

  return (
    <Toast variant={variant} onClose={onClose}>
      <div className="flex gap-3">
        <Icon className="h-5 w-5 shrink-0 mt-0.5" />
        <div className="flex-1 space-y-1">
          <ToastTitle className="flex items-center gap-2">
            <span>{severityLabels[error.severity]}</span>
            <span className="text-xs opacity-60 font-mono">
              {error.category.toUpperCase()}
            </span>
          </ToastTitle>
          <ToastDescription className="text-xs leading-relaxed">
            {error.message}
          </ToastDescription>
          {error.context?.endpoint && (
            <div className="text-xs opacity-60 font-mono mt-1">
              {error.context.endpoint}
            </div>
          )}
          <div className="text-xs opacity-50 mt-1">
            {new Date(error.timestamp).toLocaleTimeString()}
          </div>
        </div>
      </div>
      {action}
    </Toast>
  )
}

interface ErrorToasterProps {
  errors: SystemError[]
  onDismiss: (errorId: string) => void
}

export function ErrorToaster({ errors, onDismiss }: ErrorToasterProps) {
  return (
    <div className="fixed top-4 right-4 z-100 flex flex-col gap-2 max-w-md">
      {errors.map((error) => (
        <ErrorNotification
          key={error.error_id}
          error={error}
          onClose={() => onDismiss(error.error_id)}
        />
      ))}
    </div>
  )
}
