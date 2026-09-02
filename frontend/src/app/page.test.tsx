import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor, fireEvent } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import UploadPage from "./page"

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: vi.fn() })),
  usePathname: vi.fn(() => "/"),
}))

vi.mock("@/lib/api", () => ({
  apiPostForm: vi.fn(),
  apiGet: vi.fn(),
}))

import { apiPostForm, apiGet } from "@/lib/api"
import { usePipelineRun } from "@/hooks/usePipelineRun"
import type { E2eRunResult } from "@/types/estimate"
import type { UseMutationResult } from "@tanstack/react-query"

vi.mock("@/hooks/usePipelineRun", () => ({
  usePipelineRun: vi.fn<() => UseMutationResult<E2eRunResult, Error, { file: File; persist?: boolean }>>(),
}))

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <UploadPage />
    </QueryClientProvider>,
  )
}

function makePdfFile(): File {
  return new File(["%PDF-1.4 test"], "sample.pdf", { type: "application/pdf" })
}

function makeLayeredQualityResponse(overrides: Partial<{ drawing_id: string; verdict: string }> = {}) {
  return {
    verdict: overrides.verdict ?? "layered_vector",
    metrics: {
      distinct_ocg_count: 12,
      tagged_paths: 5000,
      total_paths: 5200,
      tagged_path_fraction: 0.96,
      has_extractable_text: true,
    },
    drawing_id: overrides.drawing_id ?? "test-drawing-1",
  }
}

function makeEmptyBoqResult(): E2eRunResult & { layers_count: number } {
  return {
    status: "ok",
    boq_items: [],
    estimate_id: undefined,
    layers_count: 12,
    detail: undefined,
  }
}

function makeMutationMock(
  mutateImpl: (vars: { file: File; persist?: boolean }, opts?: { onSuccess?: (result: E2eRunResult) => void; onError?: (error: Error) => void }) => void
): UseMutationResult<E2eRunResult, Error, { file: File; persist?: boolean }> {
  return {
    mutate: mutateImpl,
    mutateAsync: vi.fn(),
    data: undefined,
    error: null,
    isError: false,
    isIdle: true,
    isPending: false,
    isSuccess: false,
    status: "idle",
    reset: vi.fn(),
    failureCount: 0,
    failureReason: null,
    isPaused: false,
    submittedAt: 0,
    variables: undefined,
    context: undefined,
  } as unknown as UseMutationResult<E2eRunResult, Error, { file: File; persist?: boolean }>
}

describe("UploadPage — empty BOQ and backend error messages", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(usePipelineRun).mockReset()
  })

  it("shows empty-BOQ specific message (no assembly rule matches), not generic quality-check copy", async () => {
    const user = userEvent.setup()

    vi.mocked(apiPostForm).mockResolvedValueOnce(makeLayeredQualityResponse())
    vi.mocked(apiGet).mockResolvedValueOnce(makeLayeredQualityResponse())

    const mockMutate = vi.fn(
      (_vars: { file: File; persist?: boolean }, opts?: { onSuccess?: (result: E2eRunResult) => void; onError?: (error: Error) => void }) => {
        opts?.onSuccess?.(makeEmptyBoqResult())
      }
    )
    vi.mocked(usePipelineRun).mockReturnValue(makeMutationMock(mockMutate))

    renderPage()

    const dropZone = screen.getByTestId("dropzone")
    const input = dropZone.querySelector('input[type="file"]') as HTMLInputElement
    const file = makePdfFile()
    
    // Use fireEvent to simulate file selection
    Object.defineProperty(input, "files", { 
      value: [file], 
      configurable: true 
    })
    fireEvent.change(input)

    await waitFor(() => expect(screen.getByRole("button", { name: /Run takeoff/i })).toBeInTheDocument())

    await user.click(screen.getByRole("button", { name: /Run takeoff/i }))

    await waitFor(() => expect(screen.getByText(/no assembly rule matches this discipline/i)).toBeInTheDocument())

    expect(screen.queryByText(/Couldn't read this PDF's structure/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Couldn't complete the takeoff/i)).toBeInTheDocument()

    expect(mockMutate).toHaveBeenCalledTimes(1)
  })

  it("surfaces real backend error message verbatim, not generic quality-check copy", async () => {
    const user = userEvent.setup()

    vi.mocked(apiPostForm).mockResolvedValueOnce(makeLayeredQualityResponse())
    vi.mocked(apiGet).mockResolvedValueOnce(makeLayeredQualityResponse())

    const realError = "ValueError: Layer 'E-LIGHT' not mapped in assembly rules | raise ValueError('Layer not mapped')"
    const mockMutate = vi.fn(
      (_vars: { file: File; persist?: boolean }, opts?: { onSuccess?: (result: E2eRunResult) => void; onError?: (error: Error) => void }) => {
        opts?.onError?.(new Error(realError))
      }
    )
    vi.mocked(usePipelineRun).mockReturnValue(makeMutationMock(mockMutate))

    renderPage()

    const dropZone = screen.getByTestId("dropzone")
    const input = dropZone.querySelector('input[type="file"]') as HTMLInputElement
    const file = makePdfFile()
    
    // Use fireEvent to simulate file selection
    Object.defineProperty(input, "files", { 
      value: [file], 
      configurable: true 
    })
    fireEvent.change(input)

    await waitFor(() => expect(screen.getByRole("button", { name: /Run takeoff/i })).toBeInTheDocument())

    await user.click(screen.getByRole("button", { name: /Run takeoff/i }))

    await waitFor(() => expect(screen.getByText(realError)).toBeInTheDocument())

    expect(screen.queryByText(/Couldn't read this PDF's structure/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Couldn't complete the takeoff/i)).toBeInTheDocument()

    expect(mockMutate).toHaveBeenCalledTimes(1)
  })
})