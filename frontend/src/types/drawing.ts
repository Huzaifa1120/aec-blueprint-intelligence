export type QualityVerdict = "LAYERED_VECTOR" | "DEGRADED_VECTOR" | "RASTER"

export interface DrawingQuality {
  verdict: QualityVerdict
  drawing_id?: string
  ocg_count?: number
  path_count?: number
  detail?: string
}
