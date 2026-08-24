"use client"

import Link from "next/link"
import { ArrowRight, TriangleAlert } from "lucide-react"

export function UnpricedGap({ count }: { count: number }) {
  if (count === 0) return null
  return (
    <div className="flex items-center justify-between gap-3 border-t border-border bg-canvas px-4 py-2.5">
      <p className="flex items-center gap-2 text-xs text-ink-700">
        <TriangleAlert aria-hidden="true" className="size-3.5 shrink-0 text-warning" />
        {count.toLocaleString("en-US")} {count === 1 ? "item has" : "items have"} no rate assigned.
      </p>
      <Link
        href="/catalog"
        className="flex shrink-0 items-center gap-1 text-xs font-medium text-primary hover:underline"
      >
        Open catalog to add rates
        <ArrowRight aria-hidden="true" className="size-3" />
      </Link>
    </div>
  )
}
