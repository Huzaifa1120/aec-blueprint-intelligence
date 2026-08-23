import { render, screen, fireEvent } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { BOQTable, formatMoney, formatQuantity } from "./BOQTable"
import type { BoqItem } from "@/types/estimate"

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: (options: { count: number }) => fakeVirtualizer(options.count),
}))

function fakeVirtualizer(count: number) {
  const items = Array.from({ length: count }, (_, index) => ({
    index,
    key: index,
    start: index * 44,
    size: 44,
  }))
  return {
    getTotalSize: () => count * 44,
    getVirtualItems: () => items,
    measure: () => undefined,
  }
}

function makeItem(overrides: Partial<BoqItem> & Pick<BoqItem, "key">): BoqItem {
  return {
    description: overrides.key,
    quantity: 1,
    unit: "nr",
    unit_price: null,
    total_price: null,
    unpriced: false,
    confidence_status: "MEASURED",
    ...overrides,
  }
}

const mockRows: BoqItem[] = [
  makeItem({
    key: "material-0",
    description: "conduit_pipe",
    quantity: 1284,
    unit: "m",
    unit_price: 12.5,
    total_price: 16050,
    confidence_status: "MEASURED",
    discipline: "Electrical",
  }),
  makeItem({
    key: "material-1",
    description: "door_controller",
    quantity: 21,
    unit: "nr",
    unit_price: 680,
    total_price: 14280,
    confidence_status: "ASSUMED",
    discipline: "Electrical",
  }),
  makeItem({
    key: "route-0",
    description: "cable_tray_section",
    quantity: 410,
    unit: "m",
    unpriced: true,
    confidence_status: "UNMAPPED",
    discipline: "Electrical",
    route_type: "CABLE_TRAY",
    length_m: 41.2,
  }),
]

const noop = () => {}

function renderTable(overrides?: Partial<Parameters<typeof BOQTable>[0]>) {
  const props = {
    rows: mockRows,
    reviewStatuses: {},
    selectedKey: null,
    bulkAcceptableCount: 2,
    assumedPendingCount: 1,
    onSelectRow: noop,
    onAccept: noop,
    onReset: noop,
    onReject: noop,
    onEdit: noop,
    onAcceptAll: noop,
    ...overrides,
  }
  return render(<BOQTable {...props} />)
}

describe("BOQTable", () => {
  it("groups rows under discipline headers", () => {
    renderTable()
    expect(screen.getAllByTestId("discipline-group").map((node) => node.textContent)).toContain(
      "Electrical",
    )
  })

  it("renders quantity cells with mono tabular formatting and thousands separators", () => {
    renderTable()
    expect(formatQuantity(1284)).toBe("1,284")
    const qtyCell = screen.getByText("1,284")
    expect(qtyCell).toHaveClass("font-mono")
    expect(qtyCell).toHaveClass("tabular-nums")
  })

  it("shows the [no rate] chip linking to the catalog and a dash total for unpriced rows", () => {
    renderTable()
    const chip = screen.getByText("[no rate]")
    expect(chip.closest("a")).toHaveAttribute("href", "/catalog")
    const dash = screen.getAllByText("—").length
    expect(dash).toBeGreaterThan(0)
  })

  it("marks assumed rows with the pulse hook attribute", () => {
    const { container } = renderTable()
    const row = container.querySelector<HTMLElement>("[data-row-key='material-1']")
    expect(row).not.toBeNull()
    expect(row).toHaveAttribute("data-assumed-pulse", "true")
  })

  it("disables Accept All when no rows are bulk-acceptable", () => {
    const allAssumed = mockRows.map((row) => ({
      ...row,
      confidence_status: "ASSUMED" as const,
    }))
    renderTable({ rows: allAssumed, bulkAcceptableCount: 0 })
    expect(screen.getByTestId("accept-all")).toBeDisabled()
  })

  it("enables Accept All when pending measured or derived rows exist", () => {
    renderTable({ bulkAcceptableCount: 2 })
    expect(screen.getByTestId("accept-all")).toBeEnabled()
  })

  it("reports row selection upward on click", () => {
    const onSelectRow = vi.fn()
    const { container } = renderTable({ onSelectRow })
    const row = container.querySelector<HTMLElement>("[data-row-key='material-0']")
    expect(row).not.toBeNull()
    fireEvent.click(row as HTMLElement)
    expect(onSelectRow).toHaveBeenCalledWith(expect.objectContaining({ key: "material-0" }))
  })

  it("formats money with two decimals", () => {
    expect(formatMoney(128450)).toBe("128,450.00")
    expect(formatMoney(12.5)).toBe("12.50")
  })

  it("renders the empty state when the filter matches nothing", () => {
    renderTable({ rows: [] })
    expect(screen.getByText("Nothing matches this filter.", { selector: "p" })).toBeInTheDocument()
  })
})
