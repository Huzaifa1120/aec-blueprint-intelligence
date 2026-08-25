import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useCallback, useEffect, useRef, useState } from "react"
import { apiGet, apiPost } from "@/lib/api"
import type { CatalogEntry } from "@/types/catalog"
import type { MeasurementStatus } from "@/types/api"

export function useCatalog() {
  return useQuery<CatalogEntry[], Error>({
    queryKey: ["catalog"],
    queryFn: () => apiGet<CatalogEntry[]>("/api/catalog/"),
  })
}

export type ReviewActionKind = "accept" | "reject" | "correct"

export interface ReviewAction {
  action: ReviewActionKind
  boq_item_id: string
  confidence_tier: MeasurementStatus | "UNMAPPED"
  reason?: string
  corrected_value?: number
}

interface SessionResponse {
  session_id?: string
  id?: string
}

interface ActionPayload {
  item_id: string
  action: string
  confidence_tier: string
  boq_item_id?: string
  reason?: string
  corrected_value?: number
}

export function useReviewSession(estimateId: string | undefined) {
  const queryClient = useQueryClient()
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [reviewedCount, setReviewedCount] = useState(0)
  const sessionRef = useRef<string | null>(null)
  useEffect(() => {
    sessionRef.current = sessionId
  }, [sessionId])

  const createSession = useMutation({
    mutationFn: () =>
      apiPost<SessionResponse>("/api/review/sessions", {
        sheet_label: estimateId ? `estimate:${estimateId}` : "workspace",
        project_id: estimateId ?? null,
      }),
    onSuccess: (data) => setSessionId(data.session_id ?? data.id ?? null),
  })

  useEffect(() => {
    if (estimateId) void createSession.mutate()
    return () => {
      const sid = sessionRef.current
      if (sid) void apiPost(`/api/review/sessions/${sid}/close`).catch(() => {})
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [estimateId])

  const logAction = useCallback(
    async (action: ReviewAction) => {
      let sid = sessionId
      if (!sid) {
        const created = await createSession.mutateAsync()
        sid = created.session_id ?? created.id ?? null
      }
      if (!sid) throw new Error("No review session")
      const payload: ActionPayload = {
        item_id: action.boq_item_id,
        action: action.action,
        confidence_tier: action.confidence_tier,
      }
      if (action.boq_item_id !== undefined) payload.boq_item_id = action.boq_item_id
      if (action.reason !== undefined) payload.reason = action.reason
      if (action.corrected_value !== undefined) payload.corrected_value = action.corrected_value
      await apiPost(`/api/review/sessions/${sid}/actions`, payload)
      setReviewedCount((n) => n + 1)
    },
    [sessionId, createSession],
  )

  const closeSession = useCallback(async () => {
    if (!sessionId) return
    await apiPost(`/api/review/sessions/${sessionId}/close`)
    queryClient.invalidateQueries({ queryKey: ["estimate", estimateId, "boq"] })
  }, [sessionId, estimateId, queryClient])

  return {
    sessionId,
    createError: createSession.error as Error | null,
    logAction,
    closeSession,
    reviewedCount,
  }
}
