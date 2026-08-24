"use client"

import type { ReactNode } from "react"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { getTierMeta } from "@/lib/confidenceTier"
import type { BoqItem } from "@/types/estimate"

const SIZE_SOURCE_LABELS: Record<string, string> = {
  schedule: "Cross-section resolved from a drawing schedule",
  label: "Cross-section resolved from a text label",
  geometry: "Cross-section measured from geometry",
  assumed: "Cross-section assumed — default applied",
}

function provenanceLines(item: BoqItem): string[] {
  const lines: string[] = [getTierMeta(item.confidence_status).tooltip]
  if (item.route_type) {
    lines.push(
      `Route · ${item.route_type}${
        typeof item.length_m === "number" ? ` · ${item.length_m.toLocaleString("en-US")} m` : ""
      }`,
    )
  }
  if (item.size_source) {
    lines.push(SIZE_SOURCE_LABELS[item.size_source] ?? `Size source: ${item.size_source}`)
  }
  if (item.source?.layer) lines.push(`Layer: ${item.source.layer}`)
  return lines
}

export function ProvenanceTooltip({ item, children }: { item: BoqItem; children: ReactNode }) {
  const lines = provenanceLines(item)
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>{children}</TooltipTrigger>
        <TooltipContent className="max-w-64">
          <div className="flex flex-col gap-1">
            {lines.map((line) => (
              <p key={line} className="text-xs">
                {line}
              </p>
            ))}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
