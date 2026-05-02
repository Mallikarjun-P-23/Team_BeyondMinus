"use client"

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

const toastVariants = cva(
  "group pointer-events-auto relative flex w-full items-center justify-between space-x-4 overflow-hidden rounded-xl border-2 p-4 pr-8 shadow-lg transition-all duration-300 animate-in slide-in-from-top-5 data-[state=closed]:animate-out data-[state=closed]:slide-out-to-top-5 data-[state=closed]:fade-out-80",
  {
    variants: {
      variant: {
        default: "border-border bg-card text-card-foreground",
        critical:
          "border-destructive/50 bg-destructive/10 text-destructive dark:border-destructive dark:bg-destructive/20",
        error:
          "border-destructive/40 bg-destructive/5 text-destructive dark:border-destructive/80 dark:bg-destructive/15",
        warning:
          "border-warning/50 bg-warning/10 text-warning-foreground dark:border-warning dark:bg-warning/20",
        info: "border-primary/30 bg-primary/5 text-primary dark:border-primary/50 dark:bg-primary/10",
        success:
          "border-success/50 bg-success/10 text-success-foreground dark:border-success dark:bg-success/20",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface ToastProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof toastVariants> {
  onClose?: () => void
}

const Toast = React.forwardRef<HTMLDivElement, ToastProps>(
  ({ className, variant, onClose, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(toastVariants({ variant }), className)}
        {...props}
      >
        <div className="flex-1">{children}</div>
        {onClose && (
          <button
            onClick={onClose}
            className="absolute right-2 top-2 rounded-md p-1 text-foreground/50 opacity-0 transition-opacity hover:text-foreground focus:opacity-100 focus:outline-none focus:ring-2 group-hover:opacity-100"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    )
  }
)
Toast.displayName = "Toast"

const ToastTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("text-sm font-semibold font-sans", className)}
    {...props}
  />
))
ToastTitle.displayName = "ToastTitle"

const ToastDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("text-sm opacity-90 font-sans", className)}
    {...props}
  />
))
ToastDescription.displayName = "ToastDescription"

type ToastActionElement = React.ReactElement<typeof ToastAction>

interface ToastActionProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  altText?: string
}

const ToastAction = React.forwardRef<HTMLButtonElement, ToastActionProps>(
  ({ className, altText, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex h-8 shrink-0 items-center justify-center rounded-md border border-border bg-transparent px-3 text-sm font-medium transition-colors hover:bg-secondary focus:outline-none focus:ring-2 focus:ring-ring disabled:pointer-events-none disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
)
ToastAction.displayName = "ToastAction"

export { Toast, ToastTitle, ToastDescription, ToastAction, type ToastActionElement }
