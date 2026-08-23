export type QualityVerdict = "layered_vector" | "degraded_vector" | "raster"

export interface LayerRichnessMetrics {
  distinct_ocg_count: number
  tagged_paths: number
  total_paths: number
  tagged_path_fraction: number
  has_extractable_text: boolean
}

export interface DrawingQualityCheck {
  verdict: QualityVerdict
  metrics: LayerRichnessMetrics | null
  image_count?: number
  loop_back_message?: string | null
}

export interface DrawingQualityAssessment extends DrawingQualityCheck {
  drawing_id: string
}
