import type { MeasurementStatus } from "@/types/api"

export type TierKey = MeasurementStatus | "UNMAPPED"

export interface TierMeta {
  key: TierKey
  label: string
  colorClass: string
  tooltip: string
}

const TIERS: Record<TierKey, TierMeta> = {
  MEASURED: {
    key: "MEASURED",
    label: "Measured",
    colorClass: "text-measured",
    tooltip: "Read directly from drawing geometry",
  },
  DERIVED: {
    key: "DERIVED",
    label: "Derived",
    colorClass: "text-derived",
    tooltip: "Calculated from an engineering assembly rule",
  },
  ASSUMED: {
    key: "ASSUMED",
    label: "Assumed",
    colorClass: "text-assumed",
    tooltip: "Filled from a default or historical assumption — review required",
  },
  UNMAPPED: {
    key: "UNMAPPED",
    label: "No rule",
    colorClass: "text-unmapped",
    tooltip: "Quantity measured, but no pricing rule exists yet",
  },
}

export const TIER_ORDER: readonly TierKey[] = ["MEASURED", "DERIVED", "ASSUMED", "UNMAPPED"]

export function getTierMeta(status: string): TierMeta {
  return TIERS[status as TierKey] ?? TIERS.UNMAPPED
}
