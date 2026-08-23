import { screen } from "@testing-library/dom"
import { describe, expect, it } from "vitest"

describe("test harness", () => {
  it("runs with jest-dom matchers and alias imports", () => {
    const el = document.createElement("div")
    el.textContent = "harness"
    document.body.appendChild(el)
    expect(screen.getByText("harness")).toBeInTheDocument()
  })
})
