import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

const { setTheme, themeState } = vi.hoisted(() => ({
  setTheme: vi.fn(),
  themeState: { resolvedTheme: "light" as string | undefined },
}))

vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: themeState.resolvedTheme, setTheme }),
}))

import { ThemeToggle } from "./ThemeToggle"

describe("ThemeToggle", () => {
  beforeEach(() => {
    setTheme.mockClear()
    themeState.resolvedTheme = "light"
  })

  it("exposes an accessible name", () => {
    render(<ThemeToggle />)
    expect(screen.getByRole("button", { name: "Toggle theme" })).toBeInTheDocument()
  })

  it("requests dark when currently light", async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)
    await user.click(screen.getByRole("button", { name: "Toggle theme" }))
    expect(setTheme).toHaveBeenCalledWith("dark")
  })

  it("requests light when currently dark", async () => {
    themeState.resolvedTheme = "dark"
    const user = userEvent.setup()
    render(<ThemeToggle />)
    await user.click(screen.getByRole("button", { name: "Toggle theme" }))
    expect(setTheme).toHaveBeenCalledWith("light")
  })
})
