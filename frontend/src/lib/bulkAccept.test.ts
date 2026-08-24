import { describe, expect, it } from "vitest"
import { pickBulkAcceptable } from "./bulkAccept"
import type { BoqItem } from "@/types/estimate"

function item(partial: Partial<BoqItem>): BoqItem {
  return {
    key: "x",
    id: "x",
    description: "d",
    quantity: 1,
    unit: "nr",
    unit_price: 1,
    total_price: 1,
    confidence_status: "MEASURED",
    ...partial,
  }
}

describe("pickBulkAcceptable", () => {
  it("excludes ASSUMED rows and already-reviewed rows", () => {
    const items = [
      item({ id: "m", confidence_status: "MEASURED" }),
      item({ id: "d", confidence_status: "DERIVED" }),
      item({ id: "a", confidence_status: "ASSUMED" }),
      item({ id: "done", review_status: "accepted" }),
    ]
    expect(pickBulkAcceptable(items).map((i) => i.id)).toEqual(["m", "d"])
  })

  it("returns empty for all-assumed input", () => {
    expect(pickBulkAcceptable([item({ confidence_status: "ASSUMED" })])).toEqual([])
  })
})
