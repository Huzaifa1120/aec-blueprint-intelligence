"use client"

import { Component, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import dynamic from "next/dynamic"
import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import {
  Group,
  Panel,
  Separator,
  useDefaultLayout,
  type LayoutStorage,
} from "react-resizable-panels"
import { useEstimateBoq } from "@/hooks/useEstimateBoq"
import { useReviewSession } from "@/hooks/useReviewSession"
import { API_BASE, apiGet } from "@/lib/api"
import { firstAssumed, pickBulkAcceptable } from "@/lib/bulkAccept"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { AppShell } from "@/components/layout/AppShell"
import { ErrorState } from "@/components/common/ErrorState"
import { PipelineProgress } from "@/components/pipeline/PipelineProgress"
import {
  BOQTable,
  classifyDiscipline,
  disciplineCounts,
  type BOQTableHandle,
  type DisciplineTab,
} from "@/components/estimate/BOQTable"
import { CorrectionDialog, type CorrectionResult } from "@/components/estimate/CorrectionDialog"
import { ReviewProgress } from "@/components/estimate/ReviewProgress"
import { UnpricedGap } from "@/components/estimate/UnpricedGap"
import { AssumedScaleBanner } from "@/components/estimate/AssumedScaleBanner"
import type {
  BoqItem,
  Discipline,
  EstimateBoq,
  NarrationResponse,
  ReviewStatus,
} from "@/types/estimate"
import type { PDFViewerHandle } from "@/components/pdf/PDFViewer"

const PDFViewer = dynamic(() => import("@/components/pdf/PDFViewer"), {
  ssr: false,
  loading: () => <Skeleton className="size-full rounded-none" />,
})

const TAB_ORDER: readonly DisciplineTab[] = [
  "All",
  "Electrical",
  "Architectural",
  "Mechanical",
  "Envelope",
  "Unpriced",
]

const NO_SOURCE_MESSAGE = "No source region recorded for this item."

const PULSE_CSS = `
@keyframes assumed-row-pulse {
  0%, 100% { background-color: transparent; }
  50% { background-color: color-mix(in srgb, var(--tier-assumed) 15%, transparent); }
}
.assumed-pulse {
  animation: assumed-row-pulse calc(var(--duration-slow) * 4) var(--ease-symmetric);
}
`

const safeStorage: LayoutStorage = {
  getItem: (key) => (typeof window === "undefined" ? null : window.localStorage.getItem(key)),
  setItem: (key, value) => {
    if (typeof window !== "undefined") window.localStorage.setItem(key, value)
  },
}

export function normalizeBoq(boq: EstimateBoq): BoqItem[] {
  const routes: BoqItem[] = boq.routes.map((route, index) => ({
    key: `route-${index}`,
    description: route.material_name,
    quantity: route.quantity,
    unit: route.unit,
    unit_price: route.unpriced ? null : route.unit_price,
    total_price: route.total_cost,
    unpriced: route.unpriced,
    confidence_status: route.confidence_status,
    size_source: route.size_source,
    route_type: route.route_type,
    length_m: route.length_m,
    discipline: classifyDiscipline(route.material_name),
  }))
  const materials: BoqItem[] = boq.materials.map((material, index) => ({
    key: `material-${index}`,
    description: material.material_name,
    quantity: material.quantity,
    unit: material.unit,
    unit_price: material.unpriced ? null : material.unit_price,
    total_price: material.total_cost,
    unpriced: material.unpriced,
    confidence_status: material.confidence_status,
    size_source: material.size_source,
    discipline: classifyDiscipline(material.material_name),
  }))
  return [...routes, ...materials]
}

function formatMoney(value: number | null): string {
  if (value == null) return "—"
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function ExportMenu({ estimateId }: { estimateId: string }) {
  const [value, setValue] = useState("")
  return (
    <Select
      value={value}
      onValueChange={(format) => {
        setValue("")
        window.location.href = `${API_BASE}/api/exports/estimates/${estimateId}/export?format=${format}`
      }}
    >
      <SelectTrigger size="sm" aria-label="Export format" className="w-36">
        <SelectValue placeholder="Export" />
      </SelectTrigger>
      <SelectContent position="popper">
        <SelectItem value="json">Download as JSON</SelectItem>
        <SelectItem value="xlsx">Download as XLSX</SelectItem>
        <SelectItem value="pdf">Download as PDF</SelectItem>
      </SelectContent>
    </Select>
  )
}

function NarrationPanel({ estimateId, enabled }: { estimateId: string; enabled: boolean }) {
  const query = useQuery<NarrationResponse, Error>({
    queryKey: ["estimate", estimateId, "narration"],
    queryFn: () => apiGet<NarrationResponse>(`/api/narration/estimates/${estimateId}`),
    enabled,
    staleTime: 300_000,
  })

  if (query.isPending) {
    return (
      <div className="flex max-w-2xl flex-col gap-2">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-2/3" />
      </div>
    )
  }
  if (query.isError || !query.data) {
    return (
      <p role="alert" className="text-sm text-ink-500">
        Couldn&apos;t load the narrated scope of work. Check that the backend is running and try
        again.
      </p>
    )
  }
  return (
    <pre className="font-mono text-sm whitespace-pre-wrap text-ink-700">{query.data.narrative}</pre>
  )
}

interface WorkspaceProps {
  estimateId: string
  boq: EstimateBoq
}

function Workspace({ estimateId, boq }: WorkspaceProps) {
  const rows = useMemo(() => normalizeBoq(boq), [boq])
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [reviewStatuses, setReviewStatuses] = useState<Record<string, ReviewStatus>>({})
  const [dialogState, setDialogState] = useState<{
    mode: "reject" | "edit"
    item: BoqItem
  } | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [submittingCorrection, setSubmittingCorrection] = useState(false)
  const [acceptingAll, setAcceptingAll] = useState(false)
  const [activeTab, setActiveTab] = useState<DisciplineTab>("All")
  const [outerTab, setOuterTab] = useState("boq")
  const [sessionClosed, setSessionClosed] = useState(false)
  const [closingSession, setClosingSession] = useState(false)
  const viewerRef = useRef<PDFViewerHandle | null>(null)
  const tableRef = useRef<BOQTableHandle | null>(null)
  const session = useReviewSession(estimateId)

  const layout = useDefaultLayout({
    id: "estimate-workspace",
    panelIds: ["pdf-panel", "boq-panel"],
    storage: safeStorage,
  })

  const statusOf = useCallback(
    (key: string): ReviewStatus => reviewStatuses[key] ?? "pending",
    [reviewStatuses],
  )

  const statusedRows = useMemo(
    () => rows.map((row) => ({ ...row, review_status: statusOf(row.key) })),
    [rows, statusOf],
  )

  const counts = useMemo(() => disciplineCounts(statusedRows), [statusedRows])
  const bulkAcceptableCount = useMemo(() => pickBulkAcceptable(statusedRows).length, [statusedRows])
  const assumedPendingCount = useMemo(
    () =>
      rows.filter((row) => row.confidence_status === "ASSUMED" && statusOf(row.key) === "pending")
        .length,
    [rows, statusOf],
  )

  const filteredRows = useMemo(() => {
    if (activeTab === "All") return statusedRows
    if (activeTab === "Unpriced") return statusedRows.filter((row) => row.unpriced)
    return statusedRows.filter((row) => row.discipline === activeTab)
  }, [statusedRows, activeTab])

  const selectedRow = selectedKey ? (rows.find((row) => row.key === selectedKey) ?? null) : null
  const highlightMessage = selectedRow && !selectedRow.source?.bbox ? NO_SOURCE_MESSAGE : null

  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || !selectedRow) {
      viewer?.clearHighlight()
      return
    }
    viewer.clearHighlight()
    const source = selectedRow.source
    if (source?.bbox) {
      if (source.page != null) viewer.navigateTo(source.page + 1)
      viewer.drawHighlight(source.bbox)
    }
  }, [selectedRow])

  const markStatus = useCallback((key: string, status: ReviewStatus) => {
    setReviewStatuses((previous) => ({ ...previous, [key]: status }))
  }, [])

  const handleAccept = useCallback(
    async (item: BoqItem) => {
      try {
        await session.logAction({
          action: "accept",
          boq_item_id: item.key,
          confidence_tier: item.confidence_status,
        })
        markStatus(item.key, "accepted")
      } catch (error) {
        console.error(error)
      }
    },
    [session, markStatus],
  )

  const handleReset = useCallback(
    (item: BoqItem) => {
      markStatus(item.key, "pending")
    },
    [markStatus],
  )

  const openCorrection = useCallback((item: BoqItem, mode: "reject" | "edit") => {
    setDialogState({ mode, item })
    setDialogOpen(true)
  }, [])

  const handleSubmitCorrection = useCallback(
    async (result: CorrectionResult) => {
      if (!dialogState) return
      setSubmittingCorrection(true)
      try {
        await session.logAction({
          action: dialogState.mode === "reject" ? "reject" : "correct",
          boq_item_id: dialogState.item.key,
          confidence_tier: dialogState.item.confidence_status,
          reason: result.reason,
          corrected_value: result.correctedValue,
        })
        markStatus(dialogState.item.key, dialogState.mode === "reject" ? "rejected" : "corrected")
        setDialogOpen(false)
      } catch (error) {
        console.error(error)
      } finally {
        setSubmittingCorrection(false)
      }
    },
    [dialogState, session, markStatus],
  )

  const handleAcceptAll = useCallback(async () => {
    setAcceptingAll(true)
    try {
      const acceptable = pickBulkAcceptable(statusedRows)
      const results = await Promise.allSettled(
        acceptable.map(async (item) => {
          await session.logAction({
            action: "accept",
            boq_item_id: item.key,
            confidence_tier: item.confidence_status,
          })
          return item
        }),
      )
      for (const outcome of results) {
        if (outcome.status === "fulfilled") markStatus(outcome.value.key, "accepted")
      }
      const stillPendingAssumed = firstAssumed(
        rows.filter(
          (row) => row.confidence_status === "ASSUMED" && statusOf(row.key) === "pending",
        ),
      )
      const target =
        stillPendingAssumed ?? rows.find((row) => row.confidence_status === "ASSUMED") ?? null
      if (target) tableRef.current?.scrollToRow(target.key)
    } finally {
      setAcceptingAll(false)
    }
  }, [statusedRows, rows, session, markStatus, statusOf])

  const handleCloseSession = useCallback(async () => {
    setClosingSession(true)
    try {
      await session.closeSession()
      setSessionClosed(true)
    } catch (error) {
      console.error(error)
    } finally {
      setClosingSession(false)
    }
  }, [session])

  const reviewedCount = rows.filter((row) => statusOf(row.key) !== "pending").length

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] min-h-0 flex-col">
      <style>{PULSE_CSS}</style>
      <Group
        orientation="horizontal"
        id="estimate-workspace"
        defaultLayout={layout.defaultLayout}
        onLayoutChanged={layout.onLayoutChanged}
        className="flex min-h-0 flex-1"
      >
        <Panel
          id="pdf-panel"
          defaultSize="40%"
          minSize="20%"
          maxSize="70%"
          className="flex min-h-0"
        >
          <div className="flex h-full w-full min-h-0 flex-col">
            <PDFViewer src={null} highlightMessage={highlightMessage} ref={viewerRef} />
          </div>
        </Panel>
        <Separator className="w-px shrink-0 bg-border transition-colors hover:bg-primary/60" />
        <Panel id="boq-panel" minSize="30%" className="flex min-h-0">
          <div className="flex h-full min-h-0 w-full flex-col bg-surface">
            <Tabs
              value={outerTab}
              onValueChange={setOuterTab}
              className="flex h-full min-h-0 flex-col gap-0"
            >
              <header className="flex shrink-0 items-center justify-between gap-3 border-b border-border px-4 py-2">
                <div className="min-w-0">
                  <h1 className="truncate text-xl font-semibold text-ink-900">Takeoff workspace</h1>
                  <p className="truncate font-mono text-xs text-ink-500">{estimateId}</p>
                </div>
                <TabsList variant="line">
                  <TabsTrigger value="boq">Bill of quantities</TabsTrigger>
                  <TabsTrigger value="narration">Scope of work</TabsTrigger>
                </TabsList>
              </header>

              <TabsContent value="boq" className="flex min-h-0 flex-1 flex-col">
                <div className="shrink-0 border-b border-border px-4 pt-2 pb-0">
                  <Tabs
                    value={activeTab}
                    onValueChange={(value) => setActiveTab(value as DisciplineTab)}
                  >
                    <TabsList
                      variant="line"
                      className="w-full justify-start overflow-x-auto"
                      data-testid="discipline-tabs"
                    >
                      {TAB_ORDER.map((tab) => (
                        <TabsTrigger key={tab} value={tab}>
                          {tab}
                          <span className="font-mono text-xs tabular-nums text-ink-300">
                            {tab === "All"
                              ? counts.all
                              : tab === "Unpriced"
                                ? counts.unpriced
                                : (counts.byDiscipline[tab as Discipline] ?? 0)}
                          </span>
                        </TabsTrigger>
                      ))}
                    </TabsList>
                  </Tabs>
                </div>

                <BOQTable
                  ref={tableRef}
                  rows={filteredRows}
                  reviewStatuses={reviewStatuses}
                  selectedKey={selectedKey}
                  bulkAcceptableCount={bulkAcceptableCount}
                  assumedPendingCount={assumedPendingCount}
                  onSelectRow={(item) => setSelectedKey(item.key)}
                  onAccept={handleAccept}
                  onReset={handleReset}
                  onReject={(item) => openCorrection(item, "reject")}
                  onEdit={(item) => openCorrection(item, "edit")}
                  onAcceptAll={handleAcceptAll}
                  acceptingAll={acceptingAll}
                />

                {boq.scale?.status === "assumed" && <AssumedScaleBanner status="assumed" />}

                <UnpricedGap count={counts.unpriced} />

                <div className="flex shrink-0 items-center justify-between gap-3 border-t border-border px-4 py-2">
                  <span className="text-xs text-ink-500">
                    Materials{" "}
                    <span className="font-mono tabular-nums text-ink-700">
                      {formatMoney(boq.totals.materials)}
                    </span>{" "}
                    · Labor{" "}
                    <span className="font-mono tabular-nums text-ink-700">
                      {formatMoney(boq.totals.labor)}
                    </span>
                  </span>
                  <span className="text-xs font-medium text-ink-700">
                    Total (priced items):{" "}
                    <span className="font-mono font-semibold tabular-nums text-ink-900">
                      SAR {formatMoney(boq.totals.grand)}
                    </span>
                  </span>
                </div>

                <ReviewProgress
                  reviewed={reviewedCount}
                  total={rows.length}
                  closed={sessionClosed}
                  closing={closingSession}
                  onClose={handleCloseSession}
                />
              </TabsContent>

              <TabsContent value="narration" className="min-h-0 flex-1 overflow-auto p-4">
                <NarrationPanel estimateId={estimateId} enabled={outerTab === "narration"} />
              </TabsContent>
            </Tabs>
          </div>
        </Panel>
      </Group>

      <CorrectionDialog
        key={dialogState ? `${dialogState.mode}:${dialogState.item.key}` : "correction-dialog"}
        item={dialogState?.item ?? null}
        mode={dialogState?.mode ?? "reject"}
        open={dialogOpen}
        submitting={submittingCorrection}
        onOpenChange={setDialogOpen}
        onSubmit={handleSubmitCorrection}
      />
    </div>
  )
}

class WorkspaceErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="mx-auto w-full max-w-xl px-6 py-16">
          <ErrorState
            title="The workspace hit a problem"
            description="Reload the workspace to continue reviewing."
            action={
              <Button onClick={() => this.setState({ error: null })}>Reload workspace</Button>
            }
          />
        </div>
      )
    }
    return this.props.children
  }
}

export default function EstimateClient({ estimateId }: { estimateId: string }) {
  const query = useEstimateBoq(estimateId)
  const empty = query.data && query.data.routes.length === 0 && query.data.materials.length === 0

  let content: ReactNode
  if (!query.data) {
    content = <PipelineProgress estimateId={estimateId} />
  } else if (empty) {
    content = (
      <div className="mx-auto w-full max-w-xl px-6 py-16">
        <ErrorState
          description="No components were extracted from this drawing. This may be an unsupported discipline or drawing type."
          action={
            <Button asChild>
              <Link href="/">Upload a different drawing</Link>
            </Button>
          }
        />
      </div>
    )
  } else {
    content = <Workspace estimateId={estimateId} boq={query.data} />
  }

  return (
    <AppShell right={<ExportMenu estimateId={estimateId} />}>
      <WorkspaceErrorBoundary>{content}</WorkspaceErrorBoundary>
    </AppShell>
  )
}
