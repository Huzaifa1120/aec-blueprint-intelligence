import { useMutation } from "@tanstack/react-query"
import { apiGet, apiPostForm } from "@/lib/api"
import type { E2eRunResult } from "@/types/estimate"

const POLL_INTERVAL_MS = 2000
const POLL_BACKOFF_MAX_MS = 10000
const POLL_TOTAL_TIMEOUT_MS = 120000

interface JobResponse {
  id: string
  status: "queued" | "running" | "done" | "failed"
  progress: string
  created_at: number
  started_at: number | null
  finished_at: number | null
  result: E2eRunResult | null
  error: string | null
}

async function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(resolve, ms)
    signal?.addEventListener("abort", () => {
      clearTimeout(timeout)
      reject(new Error("Aborted"))
    })
  })
}

async function pollUntilDone(jobId: string, signal: AbortSignal): Promise<E2eRunResult> {
  let interval = POLL_INTERVAL_MS
  const deadline = Date.now() + POLL_TOTAL_TIMEOUT_MS
  while (Date.now() < deadline) {
    const job = await apiGet<JobResponse>(`/api/jobs/${jobId}`, signal)
    if (job.status === "done" && job.result) return job.result
    if (job.status === "failed") throw new Error(job.error ?? "Pipeline failed")
    await sleep(interval, signal)
    interval = Math.min(interval * 1.5, POLL_BACKOFF_MAX_MS)
  }
  throw new Error("Pipeline still running after 120s")
}

export function usePipelineRun() {
  return useMutation<E2eRunResult, Error, { file: File; persist?: boolean }>({
    mutationFn: async ({ file, persist = true }) => {
      const ac = new AbortController()
      try {
        const form = new FormData()
        form.append("file", file)
        const query = persist ? "?persist=true" : ""
        const enqueue = await apiPostForm<{ job_id: string }>(`/api/e2e/run${query}`, form, ac.signal)
        return await pollUntilDone(enqueue.job_id, ac.signal)
      } finally {
        ac.abort()
      }
    },
  })
}
