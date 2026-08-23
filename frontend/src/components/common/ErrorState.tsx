import type { ReactNode } from "react"
import { TriangleAlert } from "lucide-react"

export interface ErrorStateProps {
  title?: string
  description: string
  action?: ReactNode
}

export function ErrorState({
  title = "Couldn't complete this action",
  description,
  action,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-2 rounded-lg border border-error/30 bg-surface p-6"
    >
      <div className="flex items-center gap-2 text-error">
        <TriangleAlert className="size-4" aria-hidden="true" />
        <p className="text-sm font-semibold">{title}</p>
      </div>
      <p className="text-sm text-ink-500">{description}</p>
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}
