import type { Page } from "@playwright/test"

import type { CatalogEntry } from "@/types/catalog"
import type { DrawingQualityCheck } from "@/types/drawing"
import type { EstimateBoq, EstimateListResponse, NarrationResponse } from "@/types/estimate"

export const ESTIMATE_ID = "est-e2e-1"

const QUALITY_CHECK: DrawingQualityCheck & { drawing_id: string } = {
  verdict: "layered_vector",
  metrics: {
    distinct_ocg_count: 45,
    tagged_paths: 1188,
    total_paths: 3417,
    tagged_path_fraction: 0.3474,
    has_extractable_text: true,
  },
  image_count: 0,
  loop_back_message: null,
  drawing_id: "draw-e2e-1",
}

const ESTIMATE_LIST: EstimateListResponse = {
  items: [
    {
      estimate_id: ESTIMATE_ID,
      project_name: "MMC-JVC Tower — Electrical Takeoff",
      total_material_cost: 1553.0,
      total_labor_cost: 420.0,
      total_cost: 1973.0,
    },
  ],
  total: 1,
  page: 1,
  per_page: 20,
}

const BOQ: EstimateBoq = {
  estimate_id: ESTIMATE_ID,
  totals: { materials: 1553.0, labor: 420.0, grand: 1973.0 },
  routes: [
    {
      material_name: "Cable Tray 600 mm",
      quantity: 12.5,
      unit: "m",
      unit_cost: 45.2,
      unit_price: 45.2,
      total_cost: 565.0,
      unpriced: false,
      confidence_status: "MEASURED",
      size_source: "schedule",
      route_type: "tray",
      length_m: 12.5,
      size_json: null,
    },
  ],
  materials: [
    {
      material_name: "LED Floodlight 150 W",
      quantity: 26,
      unit: "each",
      unit_cost: 38.0,
      unit_price: 38.0,
      total_cost: 988.0,
      unpriced: false,
      confidence_status: "MEASURED",
      size_source: null,
    },
    {
      material_name: "Junction Box 100x100",
      quantity: 14,
      unit: "each",
      unit_cost: 12.0,
      unit_price: null,
      total_cost: null,
      unpriced: true,
      confidence_status: "ASSUMED",
      size_source: "assumed_default",
    },
  ],
}

const CATALOG: CatalogEntry[] = [
  {
    id: "1",
    name: "LED Floodlight 150 W",
    unit: "each",
    category: "Electrical",
    latest_unit_price: 38.0,
    effective_from: "2026-01-01",
  },
]

const NARRATION: NarrationResponse = {
  estimate_id: ESTIMATE_ID,
  provider: "template",
  narrative: "Scope of work placeholder narrative for e2e.",
}

// Minimal single-page blank PDF (exact xref offsets) so pdf.js renders the
// workspace viewer without console errors on mocked mounts.
const SOURCE_PDF =
  "%PDF-1.4\n" +
  "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n" +
  "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n" +
  "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >> endobj\n" +
  "xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n" +
  "trailer << /Size 4 /Root 1 0 R >>\nstartxref\n186\n%%EOF\n"

const RUN_RESULT = {
  status: "vector",
  scale: "1:100",
  routes_measured: 1,
  components_found: 27,
  estimate_id: ESTIMATE_ID,
  boq_items: [],
  unmapped_items: [],
}

function fulfill(data: unknown, status = 200) {
  return { status, contentType: "application/json", body: JSON.stringify(data) }
}

export async function installApiMocks(page: Page): Promise<void> {
  await page.route("**/api/**", async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const method = request.method()

    if (method === "POST" && url.pathname === "/api/drawings/check") {
      return route.fulfill(fulfill(QUALITY_CHECK))
    }
    if (method === "GET" && /^\/api\/drawings\/[^/]+\/quality$/.test(url.pathname)) {
      return route.fulfill(fulfill(QUALITY_CHECK))
    }
    if (method === "POST" && url.pathname === "/api/e2e/run") {
      return route.fulfill(fulfill(RUN_RESULT))
    }
    if (method === "GET" && url.pathname === "/api/estimates") {
      return route.fulfill(fulfill(ESTIMATE_LIST))
    }
    if (method === "GET" && url.pathname === `/api/estimates/${ESTIMATE_ID}/boq`) {
      return route.fulfill(fulfill(BOQ))
    }
    if (method === "GET" && /^\/api\/estimates\/[^/]+\/file$/.test(url.pathname)) {
      return route.fulfill({ status: 200, contentType: "application/pdf", body: SOURCE_PDF })
    }
    if (method === "GET" && url.pathname === `/api/narration/estimates/${ESTIMATE_ID}`) {
      return route.fulfill(fulfill(NARRATION))
    }
    if (method === "GET" && url.pathname === "/api/catalog/") {
      return route.fulfill(fulfill(CATALOG))
    }
    if (method === "POST" && url.pathname === "/api/review/sessions") {
      return route.fulfill(fulfill({ session_id: "sess-e2e-1" }))
    }
    if (
      method === "POST" &&
      /^\/api\/review\/sessions\/[^/]+\/(close|actions)$/.test(url.pathname)
    ) {
      return route.fulfill(fulfill({}))
    }

    throw new Error(`Unmocked API call in mocked mode: ${method} ${url.toString()}`)
  })
}
