export interface CatalogEntry {
  name: string
  unit: string
  rate: number
  effective_date?: string
  category?: string
}

export interface CatalogImportError {
  row: number
  message: string
}

export interface CatalogImportResult {
  imported: number
  errors: CatalogImportError[]
}
