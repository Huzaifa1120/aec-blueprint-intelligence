import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { PipelineProgress } from "./PipelineProgress"

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(() => ({ data: undefined, isError: false, error: null })),
}))

const STAGES = [
  "Parse layers",
  "Classify disciplines",
  "Cluster symbols",
  "Measure routes",
  "Apply assemblies",
  "Calculate costs",
]

describe("PipelineProgress", () => {
  it("renders the static stage checklist while polling", () => {
    render(<PipelineProgress estimateId="est-1" />)
    const list = screen.getByTestId("pipeline-stages")
    for (const stage of STAGES) {
      expect(list).toHaveTextContent(stage)
    }
    expect(screen.getByText("Processing drawing")).toBeInTheDocument()
  })
})
