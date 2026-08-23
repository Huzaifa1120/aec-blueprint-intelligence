import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { ConfidenceBadge } from "./ConfidenceBadge"

describe("ConfidenceBadge", () => {
  it("renders the tier symbol with accessible label", () => {
    render(<ConfidenceBadge status="MEASURED" />)
    const root = screen.getByTestId("confidence-badge")
    expect(root).toHaveTextContent("Measured")
    expect(root.querySelector("svg[data-testid='confidence-badge-symbol']")).toBeInTheDocument()
  })

  it("switches color class per tier", () => {
    const { rerender } = render(<ConfidenceBadge status="ASSUMED" />)
    expect(screen.getByTestId("confidence-badge")).toHaveClass("text-assumed")
    rerender(<ConfidenceBadge status="DERIVED" />)
    expect(screen.getByTestId("confidence-badge")).toHaveClass("text-derived")
  })

  it("shows the [R] raster modifier only for raster source quality", () => {
    const { rerender } = render(
      <ConfidenceBadge status="MEASURED" sourceQuality="layered_vector" />,
    )
    expect(screen.queryByTestId("confidence-badge-raster")).not.toBeInTheDocument()
    rerender(<ConfidenceBadge status="MEASURED" sourceQuality="raster" />)
    expect(screen.getByTestId("confidence-badge-raster")).toHaveTextContent("[R]")
  })
})
