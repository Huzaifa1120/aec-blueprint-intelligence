import type { BoqItem } from "@/types/estimate"

export function pickBulkAcceptable(items: BoqItem[]): BoqItem[] {
  return items.filter(
    (item) =>
      item.confidence_status !== "ASSUMED" && (item.review_status ?? "pending") === "pending",
  )
}

export function firstAssumed(items: BoqItem[]): BoqItem | undefined {
  return items.find((item) => item.confidence_status === "ASSUMED")
}
