"use client"

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react"
import Link from "next/link"
import { useVirtualizer } from "@tanstack/react-virtual"
import { getCoreRowModel, useLegacyTable, type LegacyColumnDef } from "@tanstack/react-table/legacy"
import { flexRender } from "@tanstack/react-table"
import { CheckCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/common/EmptyState"
import { ConfidenceBadge } from "@/components/estimate/ConfidenceBadge"
import { ProvenanceTooltip } from "@/components/estimate/ProvenanceTooltip"
import { ReviewControls } from "@/components/estimate/ReviewControls"
import { cn } from "@/lib/utils"
import type { BoqItem, Discipline, ReviewStatus } from "@/types/estimate"

const DISCIPLINES: readonly Discipline[] = ["Electrical", "Architectural", "Mechanical", "Envelope"]

const MECHANICAL_KEYWORDS = [
  "duct",
  "hvac",
  "pipe",
  "sheet_metal",
  "vibration_isolator",
  "unit_connector",
  "damper",
  "valve",
  "chiller",
  "fan_",
  "coil",
  "hanger",
]

const ELECTRICAL_KEYWORDS = [
  "conduit",
  "cable",
  "tray",
  "wire",
  "wiring",
  "switch",
  "socket",
  "outlet",
  "lighting",
  "lamp",
  "panel_board",
  "circuit_breaker",
  "busbar",
  "terminal_block",
  "card_reader",
  "magnetic_lock",
  "door_controller",
  "push_button",
  "access_control",
  "disconnect",
  "power",
  "clamp",
  "cover_plate",
  "box",
]

const ENVELOPE_KEYWORDS = ["glazing", "window", "curtain_wall", "cladding", "facade", "roof"]

const ARCHITECTURAL_KEYWORDS = ["ceiling", "tile", "paint", "floor_finish", "wall_finish"]

function matchesAny(name: string, keywords: string[]): boolean {
  return keywords.some((keyword) => name.includes(keyword))
}

export function classifyDiscipline(name: string): Discipline | undefined {
  const lower = name.toLowerCase()
  if (matchesAny(lower, MECHANICAL_KEYWORDS)) return "Mechanical"
  if (matchesAny(lower, ENVELOPE_KEYWORDS)) return "Envelope"
  if (matchesAny(lower, ELECTRICAL_KEYWORDS)) return "Electrical"
  if (matchesAny(lower, ARCHITECTURAL_KEYWORDS)) return "Architectural"
  return undefined
}

export function formatQuantity(quantity: number): string {
  return quantity.toLocaleString("en-US", { maximumFractionDigits: 3 })
}

export function formatMoney(value: number): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export type DisciplineTab = Discipline | "All" | "Unpriced"

export interface DisciplineCounts {
  all: number
  unpriced: number
  byDiscipline: Partial<Record<Discipline, number>>
}

export function disciplineCounts(rows: BoqItem[]): DisciplineCounts {
  const counts: DisciplineCounts = { all: rows.length, unpriced: 0, byDiscipline: {} }
  for (const row of rows) {
    if (row.unpriced) counts.unpriced += 1
    if (row.discipline) {
      counts.byDiscipline[row.discipline] = (counts.byDiscipline[row.discipline] ?? 0) + 1
    }
  }
  return counts
}

type Entry =
  { kind: "group"; key: string; label: string } | { kind: "row"; key: string; item: BoqItem }

function groupRowsByDiscipline(rows: BoqItem[]): Entry[] {
  const groups = new Map<string, BoqItem[]>()
  for (const row of rows) {
    const label = row.discipline ?? "Unclassified"
    const bucket = groups.get(label)
    if (bucket) bucket.push(row)
    else groups.set(label, [row])
  }
  const ordered: Array<[string, BoqItem[]]> = DISCIPLINES.filter((d) => groups.has(d)).map((d) => [
    d,
    groups.get(d) as BoqItem[],
  ])
  for (const [label, items] of groups) {
    if (!(DISCIPLINES as readonly string[]).includes(label)) ordered.push([label, items])
  }
  const entries: Entry[] = []
  for (const [label, items] of ordered) {
    entries.push({ kind: "group", key: `group:${label}`, label })
    for (const item of items) entries.push({ kind: "row", key: item.key, item })
  }
  return entries
}

export interface BOQTableHandle {
  scrollToRow: (key: string) => boolean
}

const PULSE_RESET_MS = 1600

export interface BOQTableProps {
  rows: BoqItem[]
  reviewStatuses: Record<string, ReviewStatus>
  selectedKey: string | null
  bulkAcceptableCount: number
  assumedPendingCount: number
  onSelectRow: (item: BoqItem) => void
  onAccept: (item: BoqItem) => void
  onReset: (item: BoqItem) => void
  onReject: (item: BoqItem) => void
  onEdit: (item: BoqItem) => void
  onAcceptAll: () => void
  acceptingAll?: boolean
}

const GRID_TEMPLATE = "32px minmax(0,1fr) 96px 48px 96px 104px 88px"

const ROW_HEIGHT_PX = 44
const GROUP_HEIGHT_PX = 36

const columns: LegacyColumnDef<BoqItem>[] = [
  {
    id: "confidence",
    header: "",
    cell: ({ row }) => (
      <ConfidenceBadge
        status={row.original.confidence_status}
        sourceQuality={row.original.source_quality}
      />
    ),
  },
  {
    id: "item",
    header: "Item",
    cell: ({ row }) => (
      <ProvenanceTooltip item={row.original}>
        <span
          className="block max-w-full cursor-pointer truncate text-left text-sm text-ink-700"
          title={row.original.description}
        >
          {row.original.description}
        </span>
      </ProvenanceTooltip>
    ),
  },
  {
    id: "qty",
    header: "Qty",
    cell: ({ row }) => (
      <span className="block truncate font-mono text-sm tabular-nums text-ink-900">
        {formatQuantity(row.original.quantity)}
      </span>
    ),
  },
  {
    id: "unit",
    header: "Unit",
    cell: ({ row }) => {
      const unit = row.original.unit
      return (
        <span className={cn("block truncate text-sm", unit ? "text-ink-500" : "text-unmapped")}>
          {unit ?? "—"}
        </span>
      )
    },
  },
  {
    id: "rate",
    header: "Rate",
    cell: ({ row }) => {
      const rate = row.original.unit_price
      if (rate == null || row.original.unpriced) {
        return (
          <Link
            href="/catalog"
            title="No catalog rate — open the catalog to add one"
            className="inline-block rounded border border-warning/40 px-1 py-0.5 font-mono text-xs text-warning hover:bg-warning/10"
          >
            [no rate]
          </Link>
        )
      }
      return (
        <span className="block truncate font-mono text-sm tabular-nums text-ink-700">
          {formatMoney(rate)}
        </span>
      )
    },
  },
  {
    id: "total",
    header: "Total",
    cell: ({ row }) => {
      const total = row.original.total_price
      if (total == null || row.original.unpriced) {
        return (
          <span className="block truncate font-mono text-sm tabular-nums text-unmapped">—</span>
        )
      }
      return (
        <span className="block truncate font-mono text-sm font-semibold tabular-nums text-ink-900">
          {formatMoney(total)}
        </span>
      )
    },
  },
  {
    id: "review",
    header: "Review",
  },
]

export const BOQTable = forwardRef<BOQTableHandle, BOQTableProps>(function BOQTable(
  {
    rows,
    reviewStatuses,
    selectedKey,
    bulkAcceptableCount,
    assumedPendingCount,
    onSelectRow,
    onAccept,
    onReset,
    onReject,
    onEdit,
    onAcceptAll,
    acceptingAll = false,
  },
  ref,
) {
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const [pulseKey, setPulseKey] = useState<string | null>(null)
  const pulseTimerRef = useRef<number | null>(null)

  const table = useLegacyTable({
    data: rows,
    columns,
    getRowId: (row) => row.key,
    getCoreRowModel: getCoreRowModel(),
  })

  const entries = useMemo(() => groupRowsByDiscipline(rows), [rows])

  const virtualizer = useVirtualizer({
    count: entries.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: (index) => (entries[index]?.kind === "group" ? GROUP_HEIGHT_PX : ROW_HEIGHT_PX),
    getItemKey: (index) => entries[index]?.key ?? index,
    overscan: 8,
  })

  useEffect(() => {
    if (scrollRef.current) virtualizer.measure()
  }, [entries.length, virtualizer])

  useEffect(() => {
    return () => {
      if (pulseTimerRef.current !== null) window.clearTimeout(pulseTimerRef.current)
    }
  }, [])

  const scrollToRow = useCallback(
    (key: string): boolean => {
      const index = entries.findIndex((entry) => entry.kind === "row" && entry.key === key)
      if (index < 0) return false
      const reducedMotion =
        typeof window !== "undefined" &&
        typeof window.matchMedia === "function" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches
      virtualizer.scrollToIndex(index, {
        align: "center",
        behavior: reducedMotion ? "auto" : "smooth",
      })
      setPulseKey(key)
      if (pulseTimerRef.current !== null) window.clearTimeout(pulseTimerRef.current)
      pulseTimerRef.current = window.setTimeout(() => setPulseKey(null), PULSE_RESET_MS)
      return true
    },
    [entries, virtualizer],
  )

  useImperativeHandle(ref, () => ({ scrollToRow }), [scrollToRow])

  const reviewColumnId = "review"

  return (
    <div className="flex min-h-0 flex-1 flex-col" data-testid="boq-table">
      <div className="flex shrink-0 items-center justify-between gap-2 px-4 pb-2 pt-3">
        <Button
          variant="outline"
          size="sm"
          disabled={bulkAcceptableCount === 0 || acceptingAll}
          onClick={onAcceptAll}
          title="Accepts measured and derived rows. Assumed rows require individual review."
          data-testid="accept-all"
        >
          <CheckCheck aria-hidden="true" />
          Accept All{bulkAcceptableCount > 0 ? ` (${bulkAcceptableCount})` : ""}
        </Button>
        {assumedPendingCount > 0 && (
          <p className="text-xs text-assumed">
            {assumedPendingCount.toLocaleString("en-US")} assumed{" "}
            {assumedPendingCount === 1 ? "item requires" : "items require"} individual review.
          </p>
        )}
      </div>

      <div
        className="grid shrink-0 items-center gap-x-3 border-b border-border px-4 py-1.5 text-xs font-medium tracking-wide text-ink-500 uppercase"
        style={{ gridTemplateColumns: GRID_TEMPLATE }}
        data-testid="boq-header"
      >
        {table.getHeaderGroups()[0]?.headers.map((header) => (
          <span key={header.id} className="truncate">
            {flexRender(header.column.columnDef.header, header.getContext())}
          </span>
        ))}
      </div>

      {rows.length === 0 ? (
        <div className="px-4 py-8">
          <EmptyState
            title="Nothing matches this filter."
            description="Switch back to the All tab to see every extracted line."
          />
        </div>
      ) : (
        <div ref={scrollRef} className="min-h-0 flex-1 overflow-auto" data-testid="boq-scroll">
          <div className="relative w-full" style={{ height: virtualizer.getTotalSize() }}>
            {virtualizer.getVirtualItems().map((virtualRow) => {
              const entry = entries[virtualRow.index]
              const style = {
                height: `${virtualRow.size}px`,
                transform: `translateY(${virtualRow.start}px)`,
              }
              if (entry.kind === "group") {
                return (
                  <div
                    key={virtualRow.key}
                    data-testid="discipline-group"
                    className="absolute inset-x-0 flex items-center gap-2 px-4"
                    style={style}
                  >
                    <span className="h-px flex-1 bg-border" />
                    <span className="text-xs font-semibold tracking-wide text-ink-500 uppercase">
                      {entry.label}
                    </span>
                    <span className="h-px flex-1 bg-border" />
                  </div>
                )
              }
              const row = table.getRow(entry.item.key)
              const status = reviewStatuses[entry.item.key] ?? "pending"
              const cells = row?.getVisibleCells() ?? []
              return (
                <div
                  key={virtualRow.key}
                  data-testid="boq-row"
                  data-row-key={entry.item.key}
                  data-assumed-pulse={entry.item.confidence_status === "ASSUMED"}
                  onClick={() => onSelectRow(entry.item)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault()
                      onSelectRow(entry.item)
                    }
                  }}
                  tabIndex={0}
                  className={cn(
                    "absolute inset-x-0 grid cursor-pointer items-center gap-x-3 border-b border-border/60 px-4 transition-colors duration-[var(--duration-fast)]",
                    selectedKey === entry.item.key ? "bg-accent-wash" : "hover:bg-muted/60",
                    entry.item.key === pulseKey && "assumed-pulse",
                  )}
                  style={style}
                >
                  {cells.map((cell) =>
                    cell.column.id === reviewColumnId ? (
                      <ReviewControls
                        key={cell.column.id}
                        item={entry.item}
                        status={status}
                        onAccept={onAccept}
                        onReset={onReset}
                        onReject={onReject}
                        onEdit={onEdit}
                      />
                    ) : (
                      <div
                        key={cell.column.id}
                        className={cn(
                          cell.column.id === "qty" ||
                            cell.column.id === "rate" ||
                            cell.column.id === "total"
                            ? "text-right"
                            : "",
                          cell.column.id === "confidence" && "flex justify-start",
                          cell.column.id === "review" && "flex justify-end",
                        )}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </div>
                    ),
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
})
