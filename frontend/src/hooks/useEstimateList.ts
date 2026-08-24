import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { apiGet } from "@/lib/api"
import type { EstimateListResponse } from "@/types/estimate"

export const ESTIMATES_PER_PAGE = 20

export function useEstimateList(page: number = 1, perPage: number = ESTIMATES_PER_PAGE) {
  return useQuery<EstimateListResponse, Error>({
    queryKey: ["estimates", page, perPage],
    queryFn: () => apiGet<EstimateListResponse>(`/api/estimates?page=${page}&per_page=${perPage}`),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  })
}
