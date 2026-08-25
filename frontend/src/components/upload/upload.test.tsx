import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@/lib/api", () => ({
  apiPost: vi.fn(),
}))

import { apiPost } from "@/lib/api"
import {
  DropZone,
  FILE_TOO_LARGE_COPY,
  WRONG_FILE_TYPE_COPY,
  validateDrawingFile,
} from "./DropZone"
import { QualityGateBadge } from "./QualityGateBadge"
import { REEXPORT_MESSAGE, ReexportRequest } from "./ReexportRequest"

const LAYERED_METRICS = {
  distinct_ocg_count: 46,
  tagged_paths: 87000,
  total_paths: 88523,
  tagged_path_fraction: 0.983,
  has_extractable_text: true,
}

describe("validateDrawingFile", () => {
  it("returns the exact wrong-type copy for non-PDF files", () => {
    const file = new File(["x"], "plan.txt", { type: "text/plain" })
    expect(validateDrawingFile(file)).toBe(WRONG_FILE_TYPE_COPY)
    expect(WRONG_FILE_TYPE_COPY).toBe("Only PDF files are accepted. Select a different file.")
  })

  it("returns the exact size copy for files over 50 MB", () => {
    const file = new File(["x"], "big.pdf", { type: "application/pdf" })
    Object.defineProperty(file, "size", { value: 51 * 1024 * 1024 })
    expect(validateDrawingFile(file)).toBe(FILE_TOO_LARGE_COPY)
    expect(FILE_TOO_LARGE_COPY).toBe(
      "This file is larger than 50 MB. Split the drawing set and upload one sheet at a time.",
    )
  })

  it("accepts a valid PDF", () => {
    const file = new File(["x"], "sheet.pdf", { type: "application/pdf" })
    expect(validateDrawingFile(file)).toBeNull()
  })
})

describe("DropZone", () => {
  it("renders the wrong-type copy when a non-PDF is chosen and never emits the file", async () => {
    const onFile = vi.fn()
    const { container } = render(<DropZone onFile={onFile} />)
    const input = container.querySelector('input[type="file"]')
    expect(input).not.toBeNull()
    const file = new File(["x"], "scan.png", { type: "image/png" })
    Object.defineProperty(input, "files", { value: [file], configurable: true })
    fireEvent.change(input as Element)
    expect(await screen.findByText(WRONG_FILE_TYPE_COPY)).toBeInTheDocument()
    expect(onFile).not.toHaveBeenCalled()
  })

  it("emits a valid PDF without showing an error", async () => {
    const onFile = vi.fn()
    const { container } = render(<DropZone onFile={onFile} />)
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(["x"], "sheet.pdf", { type: "application/pdf" })
    Object.defineProperty(input, "files", { value: [file], configurable: true })
    fireEvent.change(input)
    await waitFor(() => expect(onFile).toHaveBeenCalledWith(file))
    expect(screen.queryByText(WRONG_FILE_TYPE_COPY)).not.toBeInTheDocument()
  })

  it("applies a custom className to the drop area", () => {
    const onFile = vi.fn()
    render(<DropZone onFile={onFile} className="min-h-64" />)
    expect(screen.getByTestId("dropzone")).toHaveClass("min-h-64")
  })
})

describe("QualityGateBadge", () => {
  it("renders the LAYERED_VECTOR variant with counts, READY chip and measured border", () => {
    const { container, getByText } = render(
      <QualityGateBadge quality={{ verdict: "layered_vector", metrics: LAYERED_METRICS }} />,
    )
    expect(getByText("46 layers · 88,523 paths")).toBeInTheDocument()
    expect(getByText(/preserves CAD layer data/)).toBeInTheDocument()
    expect(getByText("READY")).toBeInTheDocument()
    expect(container.firstElementChild?.className).toContain("border-measured")
    expect(container.textContent).toContain("\u25CF")
  })

  it("renders the DEGRADED_VECTOR variant with LOWER CONFIDENCE chip and assumed border", () => {
    const { container, getByText } = render(
      <QualityGateBadge quality={{ verdict: "degraded_vector", metrics: null }} />,
    )
    expect(getByText("Layer data not found")).toBeInTheDocument()
    expect(getByText("LOWER CONFIDENCE")).toBeInTheDocument()
    expect(getByText(/appears to have been flattened/)).toBeInTheDocument()
    expect(
      getByText("You can continue, or request a re-export from the author."),
    ).toBeInTheDocument()
    expect(container.firstElementChild?.className).toContain("border-assumed")
    expect(container.textContent).toContain("\u25D1")
  })

  it("renders the RASTER variant with CV PIPELINE chip and raster border", () => {
    const { container, getByText } = render(
      <QualityGateBadge quality={{ verdict: "raster", metrics: null }} />,
    )
    expect(getByText("No vector data")).toBeInTheDocument()
    expect(getByText("CV PIPELINE")).toBeInTheDocument()
    expect(getByText(/scanned or rasterised drawing/)).toBeInTheDocument()
    expect(container.firstElementChild?.className).toContain("border-raster")
    expect(container.textContent).toContain("\u25CB")
  })
})

describe("ReexportRequest", () => {
  beforeEach(() => {
    vi.mocked(apiPost).mockReset()
  })

  it("pre-fills the editable message verbatim and posts the re-export request", async () => {
    const user = userEvent.setup()
    vi.mocked(apiPost).mockResolvedValue({ status: "recorded" })
    render(<ReexportRequest drawingId="test-id-1" />)

    const textarea = screen.getByLabelText("Message to the author") as HTMLTextAreaElement
    expect(textarea.value).toBe(REEXPORT_MESSAGE)
    expect(REEXPORT_MESSAGE).toBe(
      "The tool we're using for quantity takeoff requires the PDF to be exported with layers preserved. In AutoCAD: File → Export → PDF → 'Include Layer Information' checked.",
    )

    await user.type(screen.getByLabelText("Recipient email"), "author@company.com")
    textarea.setSelectionRange(textarea.value.length, textarea.value.length)
    await user.type(textarea, " Sheet E-101 please.")
    await user.click(screen.getByRole("button", { name: "Request re-export" }))

    await waitFor(() => {
      expect(vi.mocked(apiPost)).toHaveBeenCalledWith("/api/drawings/test-id-1/request-reexport", {
        recipient: "author@company.com",
        message: `${REEXPORT_MESSAGE} Sheet E-101 please.`,
      })
    })
    expect(await screen.findByText("Request sent.")).toBeInTheDocument()
  })

  it("shows an inline error for an invalid recipient instead of posting", async () => {
    const user = userEvent.setup()
    render(<ReexportRequest drawingId="test-id-2" />)

    await user.type(screen.getByLabelText("Recipient email"), "not-an-email")
    await user.click(screen.getByRole("button", { name: "Request re-export" }))

    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument()
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled()
  })
})
