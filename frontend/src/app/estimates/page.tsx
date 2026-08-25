"use client"

import Link from "next/link"
import { useState } from "react"
import { AppShell } from "@/components/layout/AppShell"
import { EmptyState } from "@/components/common/EmptyState"
import { ErrorState } from "@/components/common/ErrorState"
import { LoadingSpinner } from "@/components/common/LoadingSpinner"
import { PageHeader } from "@/components/common/PageHeader"
import { Button } from "@/components/ui/button"
import { ESTIMATES_PER_PAGE, useEstimateList } from "@/hooks/useEstimateList"

export function formatMoney(value: number): string {
  return value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function EstimateListPage() {
  const [page, setPage] = useState(1)
  const query = useEstimateList(page)
  const data = query.data
  const totalPages = data ? Math.max(1, Math.ceil(data.total / ESTIMATES_PER_PAGE)) : 1

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-5xl px-4 py-10">
        <PageHeader
          title="Estimates"
          description="Every takeoff run that has been persisted. Open one to review its quantities."
        />

        {query.isPending && (
          <p className="flex items-center gap-2 text-sm text-ink-500">
            <LoadingSpinner />
            Loading estimates…
          </p>
        )}

        {query.isError && (
          <ErrorState
            description="Couldn't load the estimate list. Check that the takeoff service is running."
            action={
              <Button variant="outline" size="sm" onClick={() => void query.refetch()}>
                Retry
              </Button>
            }
          />
        )}

        {data !== undefined &&
          (data.total === 0 ? (
            <EmptyState
              title="No estimates yet."
              description="Upload a drawing and run a takeoff — it will be listed here."
              action={
                <Button asChild size="sm">
                  <Link href="/">Upload a drawing</Link>
                </Button>
              }
            />
          ) : (
            <>
              <div className="overflow-hidden rounded-lg border border-border bg-surface shadow-sm">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-muted/40 text-left text-xs uppercase tracking-wide text-ink-500">
                      <th scope="col" className="px-4 py-2.5 font-medium">
                        Estimate
                      </th>
                      <th scope="col" className="px-4 py-2.5 text-right font-medium">
                        Materials
                      </th>
                      <th scope="col" className="px-4 py-2.5 text-right font-medium">
                        Labor
                      </th>
                      <th scope="col" className="px-4 py-2.5 text-right font-medium">
                        Total cost
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((row) => (
                      <tr
                        key={row.estimate_id}
                        className="border-b border-border last:border-b-0 hover:bg-muted/30"
                      >
                        <td className="px-4 py-3">
                          <Link
                            href={`/estimates/${row.estimate_id}`}
                            className="font-medium text-ink-700 decoration-safety-amber decoration-2 underline-offset-4 hover:underline"
                          >
                            {row.project_name}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-right font-mono tabular-nums">
                          {formatMoney(row.total_material_cost)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono tabular-nums">
                          {formatMoney(row.total_labor_cost)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono font-semibold tabular-nums">
                          {formatMoney(row.total_cost)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {totalPages > 1 && (
                <nav
                  aria-label="Estimate pages"
                  className="mt-4 flex items-center justify-between text-sm text-ink-500"
                >
                  <span className="font-mono tabular-nums">
                    Page {page} of {totalPages} · {data.total} estimates
                  </span>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page <= 1}
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                    >
                      ← Prev
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page >= totalPages}
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    >
                      Next →
                    </Button>
                  </div>
                </nav>
              )}
            </>
          ))}
      </div>
    </AppShell>
  )
}

export default function EstimatesPage() {
  return <EstimateListPage />
}
