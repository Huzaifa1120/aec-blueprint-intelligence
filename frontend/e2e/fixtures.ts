import { test as base, expect } from "@playwright/test"

import { installApiMocks } from "./mocks/api"

export const test = base.extend<{
  mockApi: void
  consoleErrors: string[]
}>({
  mockApi: [
    async ({ page }, use, testInfo) => {
      // Phase switch: identical specs run against mocks ("mocked") or the
      // real stack ("live"); only the project decides.
      if (testInfo.project.name !== "live") {
        await installApiMocks(page)
      }
      await use()
    },
    { auto: true },
  ],
  consoleErrors: [
    async ({ page }, use) => {
      const errors: string[] = []
      page.on("console", (message) => {
        if (message.type() === "error") errors.push(message.text())
      })
      page.on("pageerror", (error) => errors.push(String(error)))
      await use(errors)
    },
    { auto: true },
  ],
})

export { expect }
