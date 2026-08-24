"use client"

import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { apiGet } from "@/lib/api"
import type { CatalogEntry } from "@/types/catalog"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { EmptyState } from "@/components/common/EmptyState"
import { ErrorState } from "@/components/common/ErrorState"
import { CATALOG_IMPORT_CARD_ID } from "./CatalogImport"

async function fetchCatalog(): Promise<CatalogEntry[]> {
  const raw: unknown = await apiGet<unknown>("/api/catalog/")
  if (Array.isArray(raw)) return raw as CatalogEntry[]
  if (
    raw !== null &&
    typeof raw === "object" &&
    Array.isArray((raw as { items?: unknown }).items)
  ) {
    return (raw as { items: CatalogEntry[] }).items
  }
  return []
}

const rateFormatter = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export function formatRate(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? rateFormatter.format(value) : "—"
}

const monthYearFormatter = new Intl.DateTimeFormat("en-US", {
  month: "short",
  year: "numeric",
})

export function formatEffective(value: string | null | undefined): string {
  if (!value) return "—"
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? "—" : monthYearFormatter.format(date)
}

function focusImportCard() {
  const el = document.getElementById(CATALOG_IMPORT_CARD_ID)
  el?.scrollIntoView({ behavior: "smooth", block: "start" })
  el?.focus()
}

const SKELETON_ROW_KEYS = ["name", "unit", "rate", "effective"] as const

export function CatalogTable() {
  const { data, isPending, isError, error, refetch } = useQuery<CatalogEntry[], Error>({
    queryKey: ["catalog"],
    queryFn: fetchCatalog,
  })

  const [search, setSearch] = useState("")
  const [categoryFilter, setCategoryFilter] = useState<string>("all")

  const entries = useMemo(() => data ?? [], [data])

  const categories = useMemo(() => {
    const set = new Set<string>()
    for (const entry of entries) {
      if (entry.category) set.add(entry.category)
    }
    return [...set].sort()
  }, [entries])

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return entries.filter((entry) => {
      if (categoryFilter !== "all" && (entry.category ?? "") !== categoryFilter) {
        return false
      }
      if (needle && !entry.name.toLowerCase().includes(needle)) return false
      return true
    })
  }, [entries, search, categoryFilter])

  if (isPending) {
    return (
      <div data-testid="catalog-table-loading">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="w-[45%] py-2 text-left text-xs font-medium tracking-wider text-ink-500 uppercase">
                Name
              </th>
              <th className="w-[15%] py-2 pr-4 text-left text-xs font-medium tracking-wider text-ink-500 uppercase">
                Unit
              </th>
              <th className="w-[20%] py-2 pr-4 text-right text-xs font-medium tracking-wider text-ink-500 uppercase">
                Rate
              </th>
              <th className="w-[20%] py-2 text-right text-xs font-medium tracking-wider text-ink-500 uppercase">
                Effective
              </th>
            </tr>
          </thead>
          <tbody>
            {[0, 1, 2, 3, 4, 5].map((row) => (
              <tr key={row} className="border-b border-border/60">
                {SKELETON_ROW_KEYS.map((key) => (
                  <td key={key} className="py-3">
                    <Skeleton className="h-4 w-full max-w-32" />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (isError) {
    return (
      <ErrorState
        title="Couldn't load the price catalog."
        description={
          error.message || "The catalog service didn't respond. Check the backend and try again."
        }
        action={
          <Button variant="outline" size="sm" onClick={() => void refetch()}>
            Try again
          </Button>
        }
      />
    )
  }

  if (entries.length === 0) {
    return (
      <EmptyState
        title="No rates added yet."
        description="Import a CSV to start pricing your estimates."
        action={
          <Button size="sm" onClick={focusImportCard}>
            Import CSV
          </Button>
        }
      />
    )
  }

  return (
    <div data-testid="catalog-table">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {categories.length > 0 && (
            <Select value={categoryFilter} onValueChange={setCategoryFilter}>
              <SelectTrigger aria-label="Filter by category" className="w-48 bg-surface">
                <SelectValue placeholder="All categories" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All categories</SelectItem>
                {categories.map((category) => (
                  <SelectItem key={category} value={category}>
                    {category}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
        <input
          type="search"
          aria-label="Search catalog"
          placeholder="Search..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="h-8 w-full max-w-xs rounded-lg border border-input bg-surface px-2.5 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        />
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="py-2 text-left text-xs font-medium tracking-wider text-ink-500 uppercase">
              Name
            </th>
            <th className="py-2 pr-4 text-left text-xs font-medium tracking-wider text-ink-500 uppercase">
              Unit
            </th>
            <th className="py-2 pr-4 text-right text-xs font-medium tracking-wider text-ink-500 uppercase">
              Rate
            </th>
            <th className="py-2 text-right text-xs font-medium tracking-wider text-ink-500 uppercase">
              Effective
            </th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((entry) => (
            <tr key={entry.id ?? entry.name} className="border-b border-border/60 last:border-0">
              <td className="py-2 font-medium text-ink-900">{entry.name}</td>
              <td className="py-2 pr-4 text-ink-500">{entry.unit}</td>
              <td className="py-2 pr-4 text-right font-mono tabular-nums">
                <span
                  className={
                    typeof entry.latest_unit_price === "number" ? undefined : "text-ink-300"
                  }
                >
                  {formatRate(entry.latest_unit_price)}
                </span>
              </td>
              <td className="py-2 text-right font-mono tabular-nums text-ink-500">
                {formatEffective(entry.effective_from)}
              </td>
            </tr>
          ))}
          {filtered.length === 0 && (
            <tr>
              <td colSpan={4} className="py-6 text-center text-sm text-ink-500">
                No rates match your filters. Clear the search or category filter to see the full
                catalog.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <p className="mt-2 text-xs text-ink-500">
        Showing {filtered.length} of {entries.length} rates.
      </p>
    </div>
  )
}
