import { describe, expect, it } from "vitest"
import { TIER_ORDER, getTierMeta } from "./confidenceTier"

describe("getTierMeta", () => {
  it("maps all four tiers with three-signal metadata", () => {
    expect(getTierMeta("MEASURED")).toEqual({
      key: "MEASURED",
      label: "Measured",
      colorClass: "text-measured",
      tooltip: "Read directly from drawing geometry",
    })
    expect(getTierMeta("DERIVED").label).toBe("Derived")
    expect(getTierMeta("ASSUMED").colorClass).toBe("text-assumed")
    expect(getTierMeta("UNMAPPED").label).toBe("No rule")
  })

  it("falls back to UNMAPPED for unknown statuses", () => {
    expect(getTierMeta("SOMETHING_NEW").key).toBe("UNMAPPED")
  })

  it("exposes a stable display order", () => {
    expect(TIER_ORDER).toEqual(["MEASURED", "DERIVED", "ASSUMED", "UNMAPPED"])
  })
})
