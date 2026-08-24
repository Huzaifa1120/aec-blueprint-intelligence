"use client"

import Link from "next/link"
import { AppShell } from "@/components/layout/AppShell"
import { EmptyState } from "@/components/common/EmptyState"
import { ErrorState } from "@/components/common/ErrorState"
import { LoadingSpinner } from "@/components/common/LoadingSpinner"
import { PageHeader } from "@/components/common/PageHeader"
import { Button } from "@/components/ui/button"
import { useEstimateList } from "@/hooks/useEstimateList"

export function formatMoney(value: number): string {
  return value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function EstimateListPage() {
  const query = useEstimateList()

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

        {query.isSuccess &&
          (query.data.length === 0 ? (
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
                  {query.data.map((row) => (
                    <tr
                      key={row.estimate_id}
                      className="border-b border-border last:border-b-0 hover:bg-muted/30"
                    >
                      <td className="px-4 py-3">
                        <Link
                          href={`/estimates/${row.estimate_id}`}
                          className="font-medium text-primary underline-offset-4 hover:underline"
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
          ))}
      </div>
    </AppShell>
  )
}

export default function EstimatesPage() {
  return <EstimateListPage />
}
