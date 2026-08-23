/**
 * Catalog API types — mirror backend/app/catalog/router.py.
 *
 * GET /api/catalog/ returns a plain JSON array of materials with their latest
 * price (list_materials). `effective_from` is optional-defensive: the current
 * backend omits it, and the EFFECTIVE column renders "—" when absent.
 */
export interface CatalogEntry {
  id?: string
  name: string
  unit: string
  category?: string | null
  latest_unit_price?: number | null
  effective_from?: string | null
}

/**
 * POST /api/catalog/import returns {successful, failed, errors:[{row, reason}]}
 * where `row` is the 1-indexed spreadsheet row (header = row 1). Fields are
 * optional so alternate shapes ({index}, {message|detail}) can be mapped
 * defensively on display.
 */
export interface CatalogImportError {
  row?: number
  index?: number
  message?: string
  reason?: string
  detail?: string
}

export interface CatalogImportResult {
  successful?: number
  failed?: number
  imported?: number
  errors?: CatalogImportError[]
}
