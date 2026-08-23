import { cn } from "@/lib/utils"
import type { DrawingQualityCheck, LayerRichnessMetrics, QualityVerdict } from "@/types/drawing"

const TIER_STYLES: Record<
  QualityVerdict,
  { symbol: string; chip: string; accentClass: string; borderClass: string }
> = {
  layered_vector: {
    symbol: "\u25CF",
    chip: "READY",
    accentClass: "text-measured",
    borderClass: "border-measured",
  },
  degraded_vector: {
    symbol: "\u25D1",
    chip: "LOWER CONFIDENCE",
    accentClass: "text-assumed",
    borderClass: "border-assumed",
  },
  raster: {
    symbol: "\u25CB",
    chip: "CV PIPELINE",
    accentClass: "text-raster",
    borderClass: "border-raster",
  },
}

export function formatLayerCounts(metrics: LayerRichnessMetrics): string {
  return `${metrics.distinct_ocg_count} layers · ${metrics.total_paths.toLocaleString(
    "en-US",
  )} paths`
}

function headingFor(verdict: QualityVerdict, metrics: LayerRichnessMetrics | null) {
  if (verdict === "layered_vector") {
    return metrics ? formatLayerCounts(metrics) : "Vector layer data found"
  }
  return verdict === "degraded_vector" ? "Layer data not found" : "No vector data"
}

function bodyFor(verdict: QualityVerdict) {
  if (verdict === "layered_vector") {
    return [
      "This PDF preserves CAD layer data. Quantities will be measured directly from geometry.",
    ]
  }
  if (verdict === "degraded_vector") {
    return [
      "This PDF appears to have been flattened. Measurements will use the CV fallback pipeline and will be tagged RASTER in the results.",
      "You can continue, or request a re-export from the author.",
    ]
  }
  return [
    "This file is a scanned or rasterised drawing. Symbol detection and measurement will be visual-only and tagged accordingly in the results.",
  ]
}

export interface QualityGateBadgeProps {
  quality: Pick<DrawingQualityCheck, "verdict" | "metrics">
}

export function QualityGateBadge({ quality }: QualityGateBadgeProps) {
  const tier = TIER_STYLES[quality.verdict]
  return (
    <div
      data-testid="quality-gate-badge"
      className={cn(
        "flex items-start gap-4 rounded-r-lg border-l-[3px] bg-canvas py-4 pr-6 pl-5",
        tier.borderClass,
      )}
    >
      <span aria-hidden="true" className={cn("mt-0.5 text-xl leading-none", tier.accentClass)}>
        {tier.symbol}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-ink-900">
          {headingFor(quality.verdict, quality.metrics)}
        </p>
        {bodyFor(quality.verdict).map((line) => (
          <p key={line} className="mt-1 text-sm leading-relaxed text-ink-500">
            {line}
          </p>
        ))}
      </div>
      <span
        className={cn(
          "shrink-0 pt-0.5 text-[11px] font-semibold tracking-wider uppercase",
          tier.accentClass,
        )}
      >
        {tier.chip}
      </span>
    </div>
  )
}
