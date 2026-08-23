"use client"

import { getTierMeta, type TierKey } from "@/lib/confidenceTier"
import type { SourceQuality } from "@/types/api"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

export interface ConfidenceBadgeProps {
  status: TierKey
  sourceQuality?: SourceQuality
  showLabel?: boolean
  className?: string
}

function TierSymbol({ status }: { status: TierKey }) {
  if (status === "MEASURED") {
    return (
      <svg
        data-testid="confidence-badge-symbol"
        width="12"
        height="12"
        viewBox="0 0 12 12"
        aria-hidden="true"
      >
        <circle cx="6" cy="6" r="5" fill="currentColor" />
      </svg>
    )
  }
  if (status === "DERIVED") {
    return (
      <svg
        data-testid="confidence-badge-symbol"
        width="12"
        height="12"
        viewBox="0 0 12 12"
        aria-hidden="true"
      >
        <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.5" fill="none" />
        <path d="M6 1 A5 5 0 0 1 6 11 Z" fill="currentColor" />
      </svg>
    )
  }
  if (status === "ASSUMED") {
    return (
      <svg
        data-testid="confidence-badge-symbol"
        width="12"
        height="12"
        viewBox="0 0 12 12"
        aria-hidden="true"
      >
        <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.5" fill="none" />
      </svg>
    )
  }
  return (
    <svg
      data-testid="confidence-badge-symbol"
      width="12"
      height="12"
      viewBox="0 0 12 12"
      aria-hidden="true"
    >
      <line
        x1="2"
        y1="6"
        x2="10"
        y2="6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  )
}

export function ConfidenceBadge({
  status,
  sourceQuality,
  showLabel = false,
  className,
}: ConfidenceBadgeProps) {
  const meta = getTierMeta(status)
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            data-testid="confidence-badge"
            className={cn(
              "inline-flex items-center gap-1.5 text-xs font-medium",
              meta.colorClass,
              className,
            )}
          >
            <TierSymbol status={status} />
            <span className={cn(!showLabel && "sr-only")}>{meta.label}</span>
            {sourceQuality === "raster" && (
              <sup data-testid="confidence-badge-raster" className="font-semibold text-raster">
                [R]
              </sup>
            )}
          </span>
        </TooltipTrigger>
        <TooltipContent>
          <p>
            {meta.label} — {meta.tooltip}
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
