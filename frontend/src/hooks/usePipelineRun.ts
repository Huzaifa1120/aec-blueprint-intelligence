import { useMutation } from "@tanstack/react-query"
import { apiPostForm } from "@/lib/api"
import type { E2eRunResult } from "@/types/estimate"

export function usePipelineRun() {
  return useMutation<E2eRunResult, Error, { file: File; persist?: boolean }>({
    // `persist` is a FastAPI query parameter on POST /api/e2e/run — sending
    // it as a multipart form field is silently ignored and the response then
    // carries no estimate_id.
    mutationFn: ({ file, persist = true }) => {
      const form = new FormData()
      form.append("file", file)
      const query = persist ? "?persist=true" : ""
      return apiPostForm<E2eRunResult>(`/api/e2e/run${query}`, form)
    },
  })
}
