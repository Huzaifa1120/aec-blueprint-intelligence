import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { EstimateListPage } from "./page"

vi.mock("@/lib/api", () => ({
  apiGet: vi.fn(),
}))

import { apiGet } from "@/lib/api"
import type { EstimateListResponse, EstimateSummary } from "@/types/estimate"

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

function envelope(items: EstimateSummary[], total = items.length, page = 1): EstimateListResponse {
  return { items, total, page, per_page: 20 }
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
  beforeEach(() => {
    vi.mocked(apiGet).mockClear()
  })

  it("renders rows with mono totals and workspace links", async () => {
    vi.mocked(apiGet).mockResolvedValueOnce(envelope(ROWS))
    renderPage()
    const link = await screen.findByRole("link", { name: "Alpha Villa" })
    expect(link).toHaveAttribute("href", "/estimates/e-1")
    expect(screen.getByText("Zeta Clinic")).toBeInTheDocument()
    expect(screen.getByText("1,000.50")).toHaveClass("font-mono")
  })

  it("pages through results via Prev/Next with bounds", async () => {
    const user = userEvent.setup()
    vi.mocked(apiGet)
      .mockResolvedValueOnce({ ...envelope(ROWS), total: 25 })
      .mockResolvedValueOnce({
        items: [ROWS[0]],
        total: 25,
        page: 2,
        per_page: 20,
      })
    renderPage()
    await screen.findByRole("link", { name: "Alpha Villa" })

    expect(screen.getByRole("button", { name: "← Prev" })).toBeDisabled()
    await user.click(screen.getByRole("button", { name: "Next →" }))

    await waitFor(() => expect(apiGet).toHaveBeenCalledTimes(2))
    expect(String(vi.mocked(apiGet).mock.calls[1][0])).toContain("page=2")
    await screen.findByText("Page 2 of 2 · 25 estimates")
    expect(screen.getByRole("button", { name: "Next →" })).toBeDisabled()
  })

  it("shows the empty state with upload CTA when no estimates exist", async () => {
    vi.mocked(apiGet).mockResolvedValueOnce(envelope([]))
    renderPage()
    expect(await screen.findByText(/Upload a drawing and run a takeoff/)).toBeInTheDocument()
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
