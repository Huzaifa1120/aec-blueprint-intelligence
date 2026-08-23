import { useMutation } from "@tanstack/react-query"
import { apiPostForm } from "@/lib/api"
import type { E2eRunResult } from "@/types/estimate"

export function usePipelineRun() {
  return useMutation<E2eRunResult, Error, { file: File; persist?: boolean }>({
    mutationFn: ({ file, persist = true }) => {
      const form = new FormData()
      form.append("file", file)
      form.append("persist", String(persist))
      return apiPostForm<E2eRunResult>("/api/e2e/run", form)
    },
  })
}
