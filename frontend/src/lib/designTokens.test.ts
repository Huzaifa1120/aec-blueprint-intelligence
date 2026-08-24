import { readFile } from "node:fs/promises"
import path from "node:path"
import { beforeAll, describe, expect, it } from "vitest"

const HEX_SWATCH_RE = /hex:\s*"(#[0-9a-fA-F]{6})"/g

const ANCHOR_HEXES = ["#0b1929", "#0072cf", "#0da56a", "#6b4ff8", "#d97706", "#e85d3a", "#c41e3a"]

let tokensCss = ""
let pageSource = ""

beforeAll(async () => {
  tokensCss = await readFile(path.resolve(process.cwd(), "src/styles/tokens.css"), "utf8")
  pageSource = await readFile(path.resolve(process.cwd(), "src/app/design-system/page.tsx"), "utf8")
})

function missingFromTokens(hexes: string[]): string[] {
  return hexes.filter((hex) => !tokensCss.toLowerCase().includes(hex))
}

describe("design tokens parity", () => {
  it("resolves every styleguide swatch color in tokens.css", () => {
    const swatchHexes = [
      ...new Set([...pageSource.matchAll(HEX_SWATCH_RE)].map((match) => match[1].toLowerCase())),
    ]
    expect(swatchHexes.length).toBeGreaterThan(0)
    const missing = missingFromTokens(swatchHexes)
    expect(missing, `Swatch colors missing from tokens.css: ${missing.join(", ")}`).toEqual([])
  })

  it("anchors the core palette in tokens.css", () => {
    const missing = missingFromTokens(ANCHOR_HEXES.map((hex) => hex.toLowerCase()))
    expect(missing, `Anchor colors missing from tokens.css: ${missing.join(", ")}`).toEqual([])
  })
})
