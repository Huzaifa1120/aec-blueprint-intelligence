"use client"

import { Button } from "@/components/ui/button"

export interface ReviewProgressProps {
  reviewed: number
  total: number
  closed?: boolean
  closing?: boolean
  onClose: () => void
}

export function ReviewProgress({
  reviewed,
  total,
  closed = false,
  closing = false,
  onClose,
}: ReviewProgressProps) {
  const pct = total === 0 ? 0 : Math.min(100, Math.round((reviewed / total) * 100))
  return (
    <footer className="flex shrink-0 items-center gap-3 border-t border-border bg-surface px-4 py-2.5">
      <span className="font-mono text-sm tabular-nums text-ink-900" data-testid="review-progress">
        Review: {reviewed.toLocaleString("en-US")} / {total.toLocaleString("en-US")}
      </span>
      <div
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Review progress"
        className="h-1 min-w-16 flex-1 overflow-hidden rounded-full bg-muted"
      >
        <div
          className="h-full bg-measured transition-[width] duration-[var(--duration-base)] ease-[var(--ease-symmetric)]"
          style={{ width: `${pct}%` }}
        />
      </div>
      {closed ? (
        <Button variant="outline" size="sm" disabled>
          Session closed
        </Button>
      ) : (
        <Button variant="outline" size="sm" disabled={closing} onClick={onClose}>
          Close session
        </Button>
      )}
    </footer>
  )
}
