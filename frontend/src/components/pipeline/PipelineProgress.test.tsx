import { act, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { useQuery, type UseQueryResult } from "@tanstack/react-query"
import { PipelineProgress } from "./PipelineProgress"
import type { EstimateBoq } from "@/types/estimate"

const EMPTY_BOQ = { routes: [], materials: [] } as unknown as EstimateBoq

function queryResult(
  overrides: Partial<UseQueryResult<EstimateBoq, Error>> = {},
): UseQueryResult<EstimateBoq, Error> {
  return {
    data: undefined,
    error: null,
    isError: false,
    isPending: true,
    isLoading: true,
    isSuccess: false,
    refetch: vi.fn(),
    ...overrides,
  } as unknown as UseQueryResult<EstimateBoq, Error>
}

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(() => queryResult()),
}))

const mockedUseQuery = vi.mocked(useQuery)

const STAGES = [
  "Parse layers",
  "Classify disciplines",
  "Cluster symbols",
  "Measure routes",
  "Apply assemblies",
  "Calculate costs",
]

describe("PipelineProgress", () => {
  beforeEach(() => {
    mockedUseQuery.mockImplementation(() => queryResult())
  })

  it("renders the static stage checklist while polling", () => {
    render(<PipelineProgress estimateId="est-1" />)
    const list = screen.getByTestId("pipeline-stages")
    for (const stage of STAGES) {
      expect(list).toHaveTextContent(stage)
    }
    expect(screen.getByText("Processing drawing")).toBeInTheDocument()
  })

  it("shows backend-unreachable copy after the mount-anchored deadline passes on a failing poll", () => {
    mockedUseQuery.mockImplementation(() =>
      queryResult({ isError: true, error: new Error("network down") }),
    )
    vi.useFakeTimers()
    try {
      render(<PipelineProgress estimateId="est-1" />)
      expect(screen.queryByText(/Can't reach the takeoff service/)).not.toBeInTheDocument()
      act(() => {
        vi.advanceTimersByTime(120_000)
      })
      expect(
        screen.getByText("Can't reach the takeoff service. Check that it's running, then retry."),
      ).toBeInTheDocument()
      expect(
        screen.queryByText(
          "No components were extracted from this drawing. This may be an unsupported discipline or drawing type.",
        ),
      ).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it("keeps the empty-extraction copy for polls that succeed with zero items", () => {
    mockedUseQuery.mockImplementation(() => queryResult({ data: EMPTY_BOQ, isSuccess: true }))
    render(<PipelineProgress estimateId="est-1" />)
    expect(
      screen.getByText(
        "No components were extracted from this drawing. This may be an unsupported discipline or drawing type.",
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Can't reach the takeoff service/)).not.toBeInTheDocument()
  })
})
