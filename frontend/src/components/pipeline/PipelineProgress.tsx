"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { apiGet } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { ErrorState } from "@/components/common/ErrorState"
import { LoadingSpinner } from "@/components/common/LoadingSpinner"
import type { EstimateBoq } from "@/types/estimate"

const STAGES = [
  "Parse layers",
  "Classify disciplines",
  "Cluster symbols",
  "Measure routes",
  "Apply assemblies",
  "Calculate costs",
] as const

const PROGRESS_TIMEOUT_MS = 120_000

function hasItems(data: EstimateBoq | undefined): boolean {
  return Boolean(data && (data.routes.length > 0 || data.materials.length > 0))
}

export function PipelineProgress({ estimateId }: { estimateId: string }) {
  const [deadlineHit, setDeadlineHit] = useState(false)
  const query = useQuery<EstimateBoq, Error>({
    queryKey: ["estimate", estimateId, "boq"],
    queryFn: ({ signal }) => apiGet<EstimateBoq>(`/api/estimates/${estimateId}/boq`, signal),
    refetchInterval: (q) => (hasItems(q.state.data ?? undefined) ? false : 2000),
    retry: false,
    staleTime: 0,
  })

  useEffect(() => {
    const timer = window.setTimeout(() => setDeadlineHit(true), PROGRESS_TIMEOUT_MS)
    return () => window.clearTimeout(timer)
  }, [])

  if (query.isSuccess && query.data && !hasItems(query.data)) {
    return (
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
  }

  if (query.isError && deadlineHit) {
    return (
      <div className="mx-auto w-full max-w-xl px-6 py-16">
        <ErrorState
          description="Can't reach the takeoff service. Check that it's running, then retry."
          action={<Button onClick={() => void query.refetch()}>Retry</Button>}
        />
      </div>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-6 px-6 py-16">
      <header className="flex flex-col gap-1">
        <h1 className="text-lg font-semibold text-ink-900">Processing drawing</h1>
        <p className="flex items-center gap-2 text-sm text-ink-500">
          <LoadingSpinner />
          Working — this usually takes 15–60 seconds.
        </p>
      </header>

      <div
        role="progressbar"
        aria-label="Processing progress"
        className="h-1 w-full animate-pulse overflow-hidden rounded-full bg-primary/40"
      />

      <ol className="flex flex-col gap-2" data-testid="pipeline-stages">
        {STAGES.map((stage) => (
          <li key={stage} className="flex items-center gap-2 text-sm text-ink-300">
            <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
              <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.5" fill="none" />
            </svg>
            {stage}
          </li>
        ))}
      </ol>
    </div>
  )
}
