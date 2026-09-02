import { renderHook, act } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { afterEach, describe, expect, it, vi, beforeEach } from "vitest"

import { usePipelineRun } from "./usePipelineRun"

function makePdfFile(): File {
  return new File(["%PDF-1.4 test"], "sample.pdf", { type: "application/pdf" })
}

function makeResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  })
}

describe("usePipelineRun", () => {
  const originalFetch = global.fetch
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    global.fetch = originalFetch
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it("sends persist as a query param and the file as the only form field", async () => {
    const enqueueResponse = { job_id: "job-123", status: "queued", status_url: "/api/jobs/job-123", poll_after_ms: 2000 }
    const doneResponse = { id: "job-123", status: "done", progress: "done", created_at: Date.now(), started_at: Date.now(), finished_at: Date.now(), result: { status: "ok", estimate_id: "e1" }, error: null }

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse(enqueueResponse, { status: 202 }))
      .mockResolvedValueOnce(makeResponse(doneResponse, { status: 200 }))
    global.fetch = fetchMock as unknown as typeof fetch

    const client = new QueryClient()
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => usePipelineRun(), { wrapper })

    const promise = act(async () => {
      await result.current.mutateAsync({ file: makePdfFile(), persist: true })
    })

    await vi.advanceTimersByTimeAsync(2000)
    await promise

    expect(fetchMock).toHaveBeenCalledTimes(2)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("http://127.0.0.1:8000/api/e2e/run?persist=true")
    expect(init.method).toBe("POST")
    const body = init.body as FormData
    expect(body).toBeInstanceOf(FormData)
    expect(body.has("persist")).toBe(false)
    expect(body.get("file")).toBeInstanceOf(File)
  })

  it("POSTs, then polls until status=done", async () => {
    const enqueueResponse = { job_id: "job-123", status: "queued", status_url: "/api/jobs/job-123", poll_after_ms: 2000 }
    const runningResponse = { id: "job-123", status: "running", progress: "running", created_at: Date.now(), started_at: Date.now(), finished_at: null, result: null, error: null }
    const doneResponse = { id: "job-123", status: "done", progress: "done", created_at: Date.now(), started_at: Date.now(), finished_at: Date.now(), result: { status: "ok", estimate_id: "e1", boq_items: [] }, error: null }

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse(enqueueResponse, { status: 202 }))
      .mockResolvedValueOnce(makeResponse(runningResponse, { status: 200 }))
      .mockResolvedValueOnce(makeResponse(doneResponse, { status: 200 }))
    global.fetch = fetchMock as unknown as typeof fetch

    const client = new QueryClient()
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => usePipelineRun(), { wrapper })

    const promise = act(async () => {
      await result.current.mutateAsync({ file: makePdfFile(), persist: true })
    })

    await vi.advanceTimersByTimeAsync(2000)
    await vi.advanceTimersByTimeAsync(3000)
    await promise

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(result.current.data).toEqual(doneResponse.result)
  })

  it("surfaces a real backend error, not generic", async () => {
    const enqueueResponse = { job_id: "job-456", status: "queued", status_url: "/api/jobs/job-456", poll_after_ms: 2000 }
    const failedResponse = { id: "job-456", status: "failed", progress: "failed", created_at: Date.now(), started_at: Date.now(), finished_at: Date.now(), result: null, error: "ValueError: deliberate test failure | raise ValueError('deliberate test failure')" }

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse(enqueueResponse, { status: 202 }))
      .mockResolvedValueOnce(makeResponse(failedResponse, { status: 200 }))
    global.fetch = fetchMock as unknown as typeof fetch

    const client = new QueryClient()
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => usePipelineRun(), { wrapper })

    const promise = act(async () => {
      await expect(result.current.mutateAsync({ file: makePdfFile(), persist: true })).rejects.toThrow(
        /ValueError: deliberate test failure/,
      )
    })

    await vi.advanceTimersByTimeAsync(2000)
    await promise

    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("throws 'still running' after 120s timeout", async () => {
    const enqueueResponse = { job_id: "job-789", status: "queued", status_url: "/api/jobs/job-789", poll_after_ms: 2000 }
    const runningResponse = { id: "job-789", status: "running", progress: "running", created_at: Date.now(), started_at: Date.now(), finished_at: null, result: null, error: null }

    const fetchMock = vi.fn()
    // First call returns enqueue response
    fetchMock.mockResolvedValueOnce(makeResponse(enqueueResponse, { status: 202 }))
    // All subsequent calls return running response (new Response each time)
    fetchMock.mockImplementation(() => Promise.resolve(makeResponse(runningResponse, { status: 200 })))
    global.fetch = fetchMock as unknown as typeof fetch

    const client = new QueryClient()
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => usePipelineRun(), { wrapper })

    const promise = act(async () => {
      await expect(result.current.mutateAsync({ file: makePdfFile(), persist: true })).rejects.toThrow(
        /Pipeline still running after 120s/,
      )
    })

    // Run all pending timers (the polling loop creates sequential timers)
    await vi.runAllTimersAsync()
    await promise

    expect(fetchMock.mock.calls.length).toBeGreaterThan(1)
  }, 10000)
})
