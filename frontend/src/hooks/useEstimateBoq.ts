import { useQuery } from "@tanstack/react-query"
import { apiGet } from "@/lib/api"
import type { EstimateBoq } from "@/types/estimate"

export function useEstimateBoq(id: string) {
  return useQuery<EstimateBoq, Error>({
    queryKey: ["estimate", id, "boq"],
    queryFn: () => apiGet<EstimateBoq>(`/api/estimates/${id}/boq`),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  })
}
