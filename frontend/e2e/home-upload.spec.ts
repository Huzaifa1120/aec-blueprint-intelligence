import { expect, test } from "./fixtures"
import { ESTIMATE_ID } from "./mocks/api"

test("home renders shell, heading and nav", async ({ page, consoleErrors }) => {
  await page.goto("/")
  await expect(page.getByRole("heading", { name: "Upload a drawing to begin" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Estimates" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Catalog" })).toBeVisible()
  await expect(page.getByText("Pipeline contract")).toBeVisible()
  await expect(page.getByText("Deterministic takeoff")).toBeVisible()
  expect(consoleErrors.filter((line) => !line.includes("favicon"))).toEqual([])
})

test("upload flow: check → quality verdict → run takeoff → workspace", async ({
  page,
  consoleErrors,
}) => {
  await page.goto("/")

  await page.locator('input[type="file"]').setInputFiles({
    name: "MMC-JVC-CD-ELEC-3902.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4\n%e2e-fixture\n"),
  })

  await expect(page.getByTestId("quality-gate-badge")).toContainText("45 layers · 3,417 paths")
  await page.getByRole("button", { name: "Run takeoff →" }).click()

  await expect(page).toHaveURL(new RegExp(`/estimates/${ESTIMATE_ID}$`))
  await expect(page.getByTestId("boq-table")).toBeVisible()
  expect(consoleErrors.filter((line) => !line.includes("favicon"))).toEqual([])
})
