import { expect, test } from "./fixtures"
import { ESTIMATE_ID } from "./mocks/api"

test("estimates index lists takeoffs and links to workspace", async ({ page, consoleErrors }) => {
  await page.goto("/estimates")
  await expect(page.getByRole("heading", { name: "Estimates" })).toBeVisible()

  const rowLink = page.getByRole("link", { name: "MMC-JVC Tower — Electrical Takeoff" })
  await expect(rowLink).toBeVisible()
  await expect(page.getByText("1,973.00")).toBeVisible() // Total cost column

  await rowLink.click()
  await expect(page).toHaveURL(new RegExp(`/estimates/${ESTIMATE_ID}$`))
  expect(consoleErrors.filter((line) => !line.includes("favicon"))).toEqual([])
})

test("workspace shows BOQ rows, discipline tabs and export menu", async ({
  page,
  consoleErrors,
}) => {
  await page.goto(`/estimates/${ESTIMATE_ID}`)
  await expect(page.getByRole("heading", { name: "Takeoff workspace" })).toBeVisible()
  await expect(page.getByTestId("boq-table")).toBeVisible()
  await expect(page.getByTestId("boq-row").first()).toBeVisible()
  await expect(page.getByText("Cable Tray 600 mm")).toBeVisible()
  await expect(page.getByText("ASSUMED").first()).toBeVisible()
  await expect(page.getByTestId("discipline-tabs")).toBeVisible()
  await expect(page.getByLabel("Export format")).toBeVisible()
  expect(consoleErrors.filter((line) => !line.includes("favicon"))).toEqual([])
})
