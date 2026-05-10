"use client"

import { useObserver } from "./ObserverProvider"
import { ErrorToaster } from "./ErrorNotification"

export function ObserverNotifications() {
  const { errors, dismissError } = useObserver()

  // Only render if there are errors
  if (errors.length === 0) {
    return null
  }

  return <ErrorToaster errors={errors} onDismiss={dismissError} />
}
