import { waitFor } from "@testing-library/react"
import { renderHook } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { usePipelineRun } from "./usePipelineRun"

function makePdfFile(): File {
  return new File(["%PDF-1.4 test"], "sample.pdf", { type: "application/pdf" })
}

describe("usePipelineRun", () => {
  const originalFetch = global.fetch
  afterEach(() => {
    global.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it("sends persist as a query param and the file as the only form field", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok", estimate_id: "e1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    )
    global.fetch = fetchMock as unknown as typeof fetch

    const client = new QueryClient()
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => usePipelineRun(), { wrapper })

    result.current.mutate({ file: makePdfFile(), persist: true })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("http://127.0.0.1:8000/api/e2e/run?persist=true")
    expect(init.method).toBe("POST")
    const body = init.body as FormData
    expect(body).toBeInstanceOf(FormData)
    // The backend declares persist as a FastAPI query parameter; sending it
    // as a multipart field is silently ignored (persist stays False and no
    // estimate_id is ever returned).
    expect(body.has("persist")).toBe(false)
    expect(body.get("file")).toBeInstanceOf(File)
  })
})
