import { expect, test } from "./fixtures"

test("catalog lists rates and search filters them", async ({ page, consoleErrors }) => {
  await page.goto("/catalog")
  await expect(page.getByTestId("catalog-table")).toBeVisible()
  await expect(page.getByRole("cell", { name: "LED Floodlight 150 W" })).toBeVisible()

  await page.getByLabel("Search catalog").fill("nothing-matches-this")
  await expect(page.getByText("No rates match your filters.")).toBeVisible()
  expect(consoleErrors.filter((line) => !line.includes("favicon"))).toEqual([])
})
