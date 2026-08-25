import { expect, test } from "./fixtures"

test("home renders shell, heading and nav", async ({ page, consoleErrors }) => {
  await page.goto("/")
  await expect(page.getByRole("heading", { name: "Upload a drawing to begin" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Estimates" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Catalog" })).toBeVisible()
  expect(consoleErrors.filter((line) => !line.includes("favicon"))).toEqual([])
})
