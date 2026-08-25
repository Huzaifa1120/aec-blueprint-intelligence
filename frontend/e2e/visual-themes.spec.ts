import { expect, test } from "./fixtures"

const PAGES = [
  { name: "home", path: "/" },
  { name: "estimates", path: "/estimates" },
  { name: "workspace", path: "/estimates/est-e2e-1" },
  { name: "catalog", path: "/catalog" },
  { name: "design-system", path: "/design-system" },
] as const

const THEMES = ["light", "dark"] as const

test.describe("themed page captures", () => {
  for (const theme of THEMES) {
    for (const target of PAGES) {
      test(`${target.name} renders in ${theme}`, async ({ page, consoleErrors }) => {
        await page.addInitScript((t) => {
          window.localStorage.setItem("theme", t)
        }, theme)
        await page.goto(target.path)
        await expect(page.locator("html")).toHaveClass(new RegExp(theme))
        await page.waitForTimeout(500)
        await page.screenshot({
          path: `e2e/shots/${target.name}-${theme}.png`,
          fullPage: true,
        })
        expect(consoleErrors.filter((line) => !line.includes("favicon"))).toEqual([])
      })
    }
  }

  test("header toggle flips light to dark", async ({ page, consoleErrors }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("theme", "light")
    })
    await page.goto("/")
    await page.getByRole("button", { name: "Toggle theme" }).click()
    await expect(page.locator("html")).toHaveClass(/dark/)
    await page.waitForTimeout(500)
    await page.screenshot({ path: "e2e/shots/home-toggle-dark.png", fullPage: true })
    expect(consoleErrors.filter((line) => !line.includes("favicon"))).toEqual([])
  })
})
