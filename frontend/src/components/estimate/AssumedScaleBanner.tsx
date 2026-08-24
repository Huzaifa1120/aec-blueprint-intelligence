"use client"

import { TriangleAlert } from "lucide-react"

export function AssumedScaleBanner({ status }: { status: "detected" | "assumed" }) {
  if (status !== "assumed") return null
  return (
    <div
      role="status"
      className="flex items-center gap-2 border-t border-border bg-canvas px-4 py-2.5"
    >
      <TriangleAlert aria-hidden="true" className="size-3.5 shrink-0 text-warning" />
      <p className="text-xs text-ink-700">
        Scale not detected — lengths measured at 1:100 and flagged for review.
      </p>
    </div>
  )
}
