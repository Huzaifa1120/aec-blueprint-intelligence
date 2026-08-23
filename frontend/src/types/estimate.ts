import type { MeasurementStatus, SourceQuality } from "./api"

export interface BoqSourceRegion {
  page?: number
  bbox?: { x1: number; y1: number; x2: number; y2: number }
  layer?: string
  calculation_method?: string
}

export interface BoqItem {
  id: string
  description: string
  quantity: number
  unit: string
  unit_price: number | null
  total_price: number | null
  confidence_status: MeasurementStatus | "UNMAPPED"
  source_quality?: SourceQuality
  discipline?: string
  derivation_json?: string
  size_source?: string
  review_status?: "pending" | "accepted" | "rejected" | "corrected"
  source?: BoqSourceRegion
}

export interface EstimateBoq {
  estimate_id: string
  items: BoqItem[]
}

export interface E2eRunResult {
  status?: string
  detail?: string
  estimate_id?: string
  boq_items?: BoqItem[]
}
