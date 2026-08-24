import { expect, test } from "@playwright/test"

test("home page renders the upload flow", async ({ page }) => {
  await page.goto("/")

  await expect(page.getByRole("heading", { name: "Upload a drawing to begin" })).toBeVisible()

  const dropzone = page.getByLabel("Upload drawing PDF")
  await expect(dropzone).toBeVisible()
  await expect(dropzone.locator('input[type="file"]')).toBeAttached()
})
