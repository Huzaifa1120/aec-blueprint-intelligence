import { useQuery } from "@tanstack/react-query"
import { apiGet } from "@/lib/api"
import type { EstimateSummary } from "@/types/estimate"

export function useEstimateList() {
  return useQuery<EstimateSummary[], Error>({
    queryKey: ["estimates"],
    queryFn: () => apiGet<EstimateSummary[]>("/api/estimates"),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  })
}
