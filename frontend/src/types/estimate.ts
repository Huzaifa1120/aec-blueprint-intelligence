import type { MeasurementStatus, SourceQuality } from "./api"

export type ConfidenceStatus = MeasurementStatus | "UNMAPPED"

export type ReviewStatus = "pending" | "accepted" | "rejected" | "corrected"

export type Discipline = "Electrical" | "Architectural" | "Mechanical" | "Envelope"

export interface BoqTotals {
  materials: number | null
  labor: number | null
  grand: number | null
}

export interface BoqLine {
  material_name: string
  quantity: number
  unit: string | null
  unit_cost: number
  unit_price: number | null
  total_cost: number | null
  unpriced: boolean
  confidence_status: ConfidenceStatus
  size_source: string | null
}

export interface BoqRouteLine extends BoqLine {
  route_type: string
  length_m: number
  size_json: Record<string, unknown> | null
}

export interface EstimateSummary {
  estimate_id: string
  project_name: string
  total_material_cost: number
  total_labor_cost: number
  total_cost: number
}

export interface EstimateBoq {
  estimate_id: string
  totals: BoqTotals
  routes: BoqRouteLine[]
  materials: BoqLine[]
}

export interface BoqSourceRegion {
  page?: number
  bbox?: { x1: number; y1: number; x2: number; y2: number }
  layer?: string
  calculation_method?: string
}

export interface BoqItem {
  key: string
  id?: string
  description: string
  quantity: number
  unit: string | null
  unit_price: number | null
  total_price: number | null
  unpriced?: boolean
  confidence_status: ConfidenceStatus
  source_quality?: SourceQuality
  discipline?: Discipline
  size_source?: string | null
  route_type?: string
  length_m?: number
  source?: BoqSourceRegion
  review_status?: ReviewStatus
}

export interface E2eBoqItem {
  assembly_type: string
  material_name: string
  quantity: number
  unit_price: number | null
  total_cost: number | null
  unpriced: boolean
  confidence_status: string
  confidence_score: number
  source_quality: string
  source_path_ids: string[]
  derivation: unknown
  size_source: string | null
}

export interface E2eUnmappedItem {
  layer: string
  count: number
  source_path_ids: string[]
}

export interface E2eRunResult {
  status?: string
  detail?: string
  scale?: string | null
  routes_measured?: number
  components_found?: number
  estimate_id?: string
  boq_items?: E2eBoqItem[]
  unmapped_items?: E2eUnmappedItem[]
}

export interface NarrationResponse {
  estimate_id: string
  provider: string
  narrative: string
}
