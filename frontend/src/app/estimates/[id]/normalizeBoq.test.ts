import { createElement, type ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const { apiPostMock } = vi.hoisted(() => ({ apiPostMock: vi.fn() }))

vi.mock("@/lib/api", () => ({
  API_BASE: "http://127.0.0.1:8000",
  apiGet: vi.fn(),
  apiPost: apiPostMock,
}))

import { normalizeBoq } from "./EstimateClient"
import { useReviewSession } from "@/hooks/useReviewSession"
import type { EstimateBoq } from "@/types/estimate"

const ROUTE_ITEM_ID = "11111111-1111-1111-1111-111111111111"
const MATERIAL_ITEM_ID = "22222222-2222-2222-2222-222222222222"

function boqFixture(): EstimateBoq {
  return {
    estimate_id: "e1",
    totals: { materials: 13, labor: 0, grand: 13 },
    routes: [
      {
        material_name: "Cable tray",
        quantity: 2,
        unit: "m",
        unit_cost: 3,
        unit_price: 3,
        total_cost: 6,
        unpriced: false,
        confidence_status: "DERIVED",
        size_source: null,
        route_type: "tray",
        length_m: 2,
        size_json: null,
        item_id: ROUTE_ITEM_ID,
        source: { page: 0, bbox: [10, 20, 30, 40] },
        source_quality: "layered_vector",
      },
      {
        material_name: "Conduit run",
        quantity: 1,
        unit: "m",
        unit_cost: 2,
        unit_price: 2,
        total_cost: 2,
        unpriced: false,
        confidence_status: "MEASURED",
        size_source: null,
        route_type: "conduit",
        length_m: 1,
        size_json: null,
        source: null,
      },
    ],
    materials: [
      {
        material_name: "Door station",
        quantity: 1,
        unit: "nr",
        unit_cost: 7,
        unit_price: 7,
        total_cost: 7,
        unpriced: false,
        confidence_status: "MEASURED",
        size_source: null,
        item_id: MATERIAL_ITEM_ID,
        source: { page: 1, bbox: [1, 2, 3, 4] },
      },
    ],
  }
}

describe("normalizeBoq", () => {
  it("prefers item_id for row keys and falls back to index keys", () => {
    const rows = normalizeBoq(boqFixture())
    expect(rows.map((row) => row.key)).toEqual([ROUTE_ITEM_ID, "route-1", MATERIAL_ITEM_ID])
  })

  it("converts source bbox arrays to highlight objects", () => {
    const rows = normalizeBoq(boqFixture())
    expect(rows[0].source).toEqual({
      page: 0,
      bbox: { x1: 10, y1: 20, x2: 30, y2: 40 },
    })
    expect(rows[2].source).toEqual({
      page: 1,
      bbox: { x1: 1, y1: 2, x2: 3, y2: 4 },
    })
  })

  it("keeps legacy rows with a null source region highlight-free", () => {
    const rows = normalizeBoq(boqFixture())
    expect(rows[1].source).toBeUndefined()
    expect(rows[1].key).toBe("route-1")
  })

  it("passes source_quality through to review rows", () => {
    const rows = normalizeBoq(boqFixture())
    expect(rows[0].source_quality).toBe("layered_vector")
    expect(rows[1].source_quality).toBeUndefined()
  })
})

describe("useReviewSession payload shape", () => {
  function makeWrapper(): (props: { children: ReactNode }) => ReactNode {
    const client = new QueryClient()
    return function Wrapper({ children }) {
      return createElement(QueryClientProvider, { client }, children)
    }
  }

  beforeEach(() => {
    apiPostMock.mockReset()
    apiPostMock.mockResolvedValue({ session_id: "s1" })
  })

  it("forwards boq_item_id, reason and corrected_value on correction actions", async () => {
    const wrapper = makeWrapper()
    const { result } = renderHook(() => useReviewSession("est-1"), { wrapper })

    await waitFor(() => expect(result.current.sessionId).toBe("s1"))

    await result.current.logAction({
      action: "correct",
      boq_item_id: "row-7",
      confidence_tier: "ASSUMED",
      reason: "measured length wrong",
      corrected_value: 12.5,
    })

    expect(apiPostMock).toHaveBeenCalledTimes(2)
    const [path, payload] = apiPostMock.mock.calls[1]
    expect(path).toBe("/api/review/sessions/s1/actions")
    expect(payload).toEqual({
      item_id: "row-7",
      action: "correct",
      confidence_tier: "ASSUMED",
      boq_item_id: "row-7",
      reason: "measured length wrong",
      corrected_value: 12.5,
    })
  })

  it("omits optional fields when they are not provided", async () => {
    const wrapper = makeWrapper()
    const { result } = renderHook(() => useReviewSession("est-1"), { wrapper })

    await waitFor(() => expect(result.current.sessionId).toBe("s1"))

    await result.current.logAction({
      action: "accept",
      boq_item_id: "row-3",
      confidence_tier: "MEASURED",
    })

    const [, payload] = apiPostMock.mock.calls[1]
    expect(payload).toStrictEqual({
      item_id: "row-3",
      action: "accept",
      confidence_tier: "MEASURED",
      boq_item_id: "row-3",
    })
  })
})
