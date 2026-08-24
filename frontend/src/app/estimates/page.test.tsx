import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { EstimateListPage } from "./page"

vi.mock("@/lib/api", () => ({
  apiGet: vi.fn(),
}))

import { apiGet } from "@/lib/api"
import type { EstimateSummary } from "@/types/estimate"

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <EstimateListPage />
    </QueryClientProvider>,
  )
}

const ROWS: EstimateSummary[] = [
  {
    estimate_id: "e-2",
    project_name: "Zeta Clinic",
    total_material_cost: 10,
    total_labor_cost: 2,
    total_cost: 12,
  },
  {
    estimate_id: "e-1",
    project_name: "Alpha Villa",
    total_material_cost: 1000.5,
    total_labor_cost: 200,
    total_cost: 1200.5,
  },
]

describe("EstimateListPage", () => {
  it("renders rows with mono totals and workspace links", async () => {
    vi.mocked(apiGet).mockResolvedValueOnce(ROWS)
    renderPage()
    const link = await screen.findByRole("link", { name: "Alpha Villa" })
    expect(link).toHaveAttribute("href", "/estimates/e-1")
    expect(screen.getByText("Zeta Clinic")).toBeInTheDocument()
    expect(screen.getByText("1,000.50")).toHaveClass("font-mono")
    expect(screen.getAllByText("12.00").length).toBeGreaterThan(0)
  })

  it("shows the empty state with upload CTA when no estimates exist", async () => {
    vi.mocked(apiGet).mockResolvedValueOnce([])
    renderPage()
    expect(
      await screen.findByText("Upload a drawing and run a takeoff — it will be listed here."),
    ).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Upload a drawing" })).toHaveAttribute("href", "/")
  })

  it("shows a named failure with retry when the API errors", async () => {
    vi.mocked(apiGet).mockRejectedValueOnce(new Error("backend down"))
    renderPage()
    const alert = await screen.findByRole("alert")
    expect(alert).toHaveTextContent("Couldn't load the estimate list.")
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument()
  })
})
