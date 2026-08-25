import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { AssumedScaleBanner } from "./AssumedScaleBanner"

describe("AssumedScaleBanner", () => {
  it("renders warning when scale assumed", () => {
    render(<AssumedScaleBanner status="assumed" />)
    expect(screen.getByRole("status")).toHaveTextContent(/1:100/)
  })
  it("renders nothing when detected", () => {
    const { container } = render(<AssumedScaleBanner status="detected" />)
    expect(container).toBeEmptyDOMElement()
  })
})
