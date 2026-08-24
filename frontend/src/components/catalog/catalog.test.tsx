import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactElement } from "react"
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPostForm: vi.fn(),
}))

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {
    constructor(
      message: string,
      readonly status: number,
    ) {
      super(message)
    }
  },
  apiGet: mocks.apiGet,
  apiPostForm: mocks.apiPostForm,
}))

import { buildTemplateCsv, CATALOG_IMPORT_CARD_ID, CatalogImport } from "./CatalogImport"
import { CatalogTable, formatEffective, formatRate } from "./CatalogTable"

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
}

function renderWithClient(ui: ReactElement) {
  const queryClient = makeQueryClient()
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

const ENTRIES = [
  {
    id: "1",
    name: "Control Cable 2×2.5mm",
    unit: "m",
    category: "electrical",
    latest_unit_price: 420,
    effective_from: "2026-08-01",
  },
  {
    id: "2",
    name: "Magnetic Lock",
    unit: "nr",
    category: null,
    latest_unit_price: null,
  },
]

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

beforeAll(() => {
  Element.prototype.hasPointerCapture = () => false
  Element.prototype.setPointerCapture = () => {}
  Element.prototype.releasePointerCapture = () => {}
  Element.prototype.scrollIntoView = () => {}
})

beforeEach(() => {
  mocks.apiGet.mockReset()
  mocks.apiPostForm.mockReset()
})

describe("catalog formatting helpers", () => {
  it("formats rates with thousands separators and two decimals", () => {
    expect(formatRate(1850)).toBe("1,850.00")
    expect(formatRate(420)).toBe("420.00")
    expect(formatRate(null)).toBe("—")
    expect(formatRate(undefined)).toBe("—")
  })

  it("formats effective dates as short month + year", () => {
    expect(formatEffective("2026-08-01")).toBe("Aug 2026")
    expect(formatEffective(null)).toBe("—")
    expect(formatEffective(undefined)).toBe("—")
    expect(formatEffective("not-a-date")).toBe("—")
  })
})

describe("CatalogTable", () => {
  it("renders rows with monospaced right-aligned rate cells", async () => {
    mocks.apiGet.mockResolvedValue(ENTRIES)
    renderWithClient(<CatalogTable />)

    expect(await screen.findByText("Control Cable 2×2.5mm")).toBeInTheDocument()

    const rateCell = screen.getByText("420.00").closest("td")
    expect(rateCell).toHaveClass("font-mono", "tabular-nums", "text-right")

    const unpricedCells = screen.getAllByText("—")
    expect(unpricedCells.length).toBeGreaterThan(0)
    for (const cell of unpricedCells) {
      expect(cell.closest("td")).toHaveClass("font-mono", "tabular-nums", "text-right")
    }

    expect(screen.getByText("Aug 2026")).toBeInTheDocument()
    expect(mocks.apiGet).toHaveBeenCalledWith("/api/catalog/")
  })

  it("omits the category filter when no categories exist in the data", async () => {
    mocks.apiGet.mockResolvedValue([
      { id: "3", name: "Cable Tie", unit: "nr", category: null, latest_unit_price: 5 },
    ])
    renderWithClient(<CatalogTable />)

    await screen.findByText("Cable Tie")
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument()
  })

  it("shows the category filter when category data exists and filters by it", async () => {
    const user = userEvent.setup()
    mocks.apiGet.mockResolvedValue(ENTRIES)
    renderWithClient(<CatalogTable />)

    await screen.findByText("Magnetic Lock")
    const combo = screen.getByRole("combobox", { name: "Filter by category" })
    expect(combo).toBeInTheDocument()
    await user.click(combo)
    await user.click(await screen.findByRole("option", { name: "electrical" }))
    await waitFor(() => {
      expect(screen.queryByText("Magnetic Lock")).not.toBeInTheDocument()
    })
    expect(screen.getByText("Control Cable 2×2.5mm")).toBeInTheDocument()
  })

  it("filters rows by search substring", async () => {
    const user = userEvent.setup()
    mocks.apiGet.mockResolvedValue(ENTRIES)
    renderWithClient(<CatalogTable />)

    await screen.findByText("Magnetic Lock")
    await user.type(screen.getByRole("searchbox"), "cable")
    expect(screen.queryByText("Magnetic Lock")).not.toBeInTheDocument()
    expect(screen.getByText("Control Cable 2×2.5mm")).toBeInTheDocument()
  })

  it("renders the §8 empty state with an action that focuses the import card", async () => {
    const scrollIntoView = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoView
    mocks.apiGet.mockResolvedValue([])
    renderWithClient(
      <>
        <div id={CATALOG_IMPORT_CARD_ID} tabIndex={-1} />
        <CatalogTable />
      </>,
    )

    const user = userEvent.setup()
    expect(await screen.findByText("No rates added yet.")).toBeInTheDocument()
    expect(screen.getByText("Import a CSV to start pricing your estimates.")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Import CSV" }))
    expect(scrollIntoView).toHaveBeenCalled()
    expect(document.activeElement?.id).toBe(CATALOG_IMPORT_CARD_ID)
  })

  it("renders an error state with retry when the fetch fails", async () => {
    mocks.apiGet.mockRejectedValue(new Error("backend offline"))
    renderWithClient(<CatalogTable />)

    const alert = await screen.findByRole("alert")
    expect(alert).toHaveTextContent("Couldn't load the price catalog.")
    expect(alert).toHaveTextContent("backend offline")
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument()
  })

  it("renders skeleton rows while loading", () => {
    mocks.apiGet.mockReturnValue(new Promise(() => {}))
    renderWithClient(<CatalogTable />)
    expect(screen.getByTestId("catalog-table-loading")).toBeInTheDocument()
  })
})

describe("CatalogImport", () => {
  function uploadFile(container: HTMLElement) {
    const input = container.querySelector('input[type="file"]')
    if (!(input instanceof HTMLInputElement)) {
      throw new Error("file input not found")
    }
    return input
  }

  it("uploads via POST /api/catalog/import with multipart field 'file'", async () => {
    const user = userEvent.setup()
    mocks.apiPostForm.mockResolvedValue({
      successful: 46,
      failed: 0,
      errors: [],
    })
    const { container } = renderWithClient(<CatalogImport />)

    const file = new File(["material_name,unit,unit_price"], "rates.csv", {
      type: "text/csv",
    })
    await user.upload(uploadFile(container), file)

    await screen.findByText("Import complete")
    expect(mocks.apiPostForm).toHaveBeenCalledOnce()
    const [path, form] = mocks.apiPostForm.mock.calls[0] as [string, FormData]
    expect(path).toBe("/api/catalog/import")
    const sent = form.get("file")
    expect(sent).toBeInstanceOf(File)
    expect((sent as File).name).toBe("rates.csv")
    expect(screen.getByText("46 rows imported successfully.")).toBeInTheDocument()
    expect(screen.queryByTestId("import-errors")).not.toBeInTheDocument()
  })

  it("lists per-row errors in the spec §5.4 format with a count summary", async () => {
    const user = userEvent.setup()
    mocks.apiPostForm.mockResolvedValue({
      successful: 43,
      failed: 3,
      errors: [
        { row: 12, reason: 'Unit "sqm" not recognised.' },
        { row: 17, reason: "Rate is missing. This row was skipped." },
        { index: 23, message: 'Effective date "2026-13-01" is not a valid date.' },
      ],
    })
    const { container } = renderWithClient(<CatalogImport />)

    const file = new File(["a,b,c"], "rates.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    })
    await user.upload(uploadFile(container), file)

    const result = await screen.findByTestId("import-result")
    expect(result).toHaveTextContent("Import complete — 3 errors found")
    expect(result).toHaveTextContent('Row 12: Unit "sqm" not recognised.')
    expect(result).toHaveTextContent("Row 17: Rate is missing. This row was skipped.")
    expect(result).toHaveTextContent('Row 23: Effective date "2026-13-01" is not a valid date.')
    expect(result).toHaveTextContent("43 rows imported successfully.")
  })

  it("maps alternate error shapes defensively (missing row → bare message)", async () => {
    const user = userEvent.setup()
    mocks.apiPostForm.mockResolvedValue({
      successful: 0,
      failed: 1,
      errors: [{ detail: "openpyxl not installed — cannot parse .xlsx files" }],
    })
    const { container } = renderWithClient(<CatalogImport />)

    const file = new File(["x"], "broken.xlsx", { type: "text/plain" })
    await user.upload(uploadFile(container), file)

    const result = await screen.findByTestId("import-result")
    expect(result).toHaveTextContent("Import complete — 1 errors found")
    expect(result).toHaveTextContent("openpyxl not installed — cannot parse .xlsx files")
    expect(result).toHaveTextContent("0 rows imported successfully.")
  })

  it("rejects non-CSV/XLSX files without calling the API", async () => {
    mocks.apiPostForm.mockResolvedValue({ successful: 1, failed: 0, errors: [] })
    const { container } = renderWithClient(<CatalogImport />)

    const input = uploadFile(container)
    const pdf = new File(["drawing"], "plan.pdf", { type: "application/pdf" })
    Object.defineProperty(input, "files", { value: [pdf] })
    fireEvent.change(input)

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Only CSV or Excel (.xlsx) files are accepted. Select a different file.",
    )
    expect(mocks.apiPostForm).not.toHaveBeenCalled()
  })

  it("shows an error state when the upload request fails", async () => {
    const user = userEvent.setup()
    mocks.apiPostForm.mockRejectedValue(new Error("network down"))
    const { container } = renderWithClient(<CatalogImport />)

    const file = new File(["a"], "rates.csv", { type: "text/csv" })
    await user.upload(uploadFile(container), file)

    const alert = await screen.findByRole("alert")
    expect(alert).toHaveTextContent("Couldn't import this file.")
    expect(alert).toHaveTextContent("network down")
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument()
  })

  it("offers separate materials and labor template downloads", async () => {
    const user = userEvent.setup()
    const clickSpy = vi.fn()
    const createObjectURLSpy = vi.fn(() => "blob:template")
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: createObjectURLSpy,
      revokeObjectURL: vi.fn(),
    })
    HTMLAnchorElement.prototype.click = clickSpy
    renderWithClient(<CatalogImport />)

    await user.click(screen.getByRole("button", { name: "Materials CSV" }))
    let anchor = clickSpy.mock.instances[0] as HTMLAnchorElement
    expect(anchor.download).toBe("catalog-materials-template.csv")

    await user.click(screen.getByRole("button", { name: "Labor rates CSV" }))
    anchor = clickSpy.mock.instances[1] as HTMLAnchorElement
    expect(anchor.download).toBe("catalog-labor-rates-template.csv")
  })

  it("builds single-schema, importable template CSVs", () => {
    for (const kind of ["materials", "labor"] as const) {
      const csv = buildTemplateCsv(kind)
      const lines = csv.trimEnd().split("\n")
      expect(lines.length).toBeGreaterThan(1)
      expect(csv).not.toContain("<")
      const header = lines[0]
      for (const line of lines.slice(1)) {
        expect(line.split(",").length).toBe(header.split(",").length)
      }
    }
    expect(buildTemplateCsv("materials").split("\n")[0]).toBe(
      "material_name,unit,unit_price,category,effective_from,effective_to,source",
    )
    expect(buildTemplateCsv("labor").split("\n")[0]).toBe(
      "rate_name,productivity_rate,hourly_rate,category,effective_from,effective_to,source",
    )
  })
})
