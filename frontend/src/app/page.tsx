"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

import { AppShell } from "@/components/layout/AppShell"
import { ErrorState } from "@/components/common/ErrorState"
import { LoadingSpinner } from "@/components/common/LoadingSpinner"
import { Button } from "@/components/ui/button"
import { DropZone } from "@/components/upload/DropZone"
import { QualityGateBadge } from "@/components/upload/QualityGateBadge"
import { ReexportRequest } from "@/components/upload/ReexportRequest"
import { GoggleLineDivider } from "@/components/ui/GoggleLineDivider"
import { HazardStripe } from "@/components/ui/HazardStripe"
import { usePipelineRun } from "@/hooks/usePipelineRun"
import { apiGet, apiPostForm } from "@/lib/api"
import type { DrawingQualityCheck, QualityVerdict } from "@/types/drawing"

const QUALITY_CHECK_FAILED_COPY =
  "Couldn't read this PDF's structure. The file may be corrupted. Try re-exporting from your CAD application."

type Phase = "idle" | "checking" | "ready" | "running"

interface CheckedQuality {
  verdict: QualityVerdict
  metrics: DrawingQualityCheck["metrics"]
}

function newCorrelationId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID()
  }
  return "10000000-2000-4000-8000-100000000000".replace(/[08]/g, (char) => {
    const value = crypto.getRandomValues(new Uint8Array(1))[0] & 0xf
    const digit = char === "8" ? value : (value & 0x3) | 0x8
    return digit.toString(16)
  })
}

export default function UploadPage() {
  const router = useRouter()
  const [phase, setPhase] = useState<Phase>("idle")
  const [file, setFile] = useState<File | null>(null)
  const [quality, setQuality] = useState<CheckedQuality | null>(null)
  const [checkFailed, setCheckFailed] = useState(false)
  const [drawingId, setDrawingId] = useState<string>("")
  const [continueAnyway, setContinueAnyway] = useState(false)
  const [runFailureDetail, setRunFailureDetail] = useState<string | null>(null)

  const pipeline = usePipelineRun()

  const isDegraded = quality?.verdict === "degraded_vector"
  const showRunButton =
    quality !== null && !checkFailed && phase === "ready" && (!isDegraded || continueAnyway)

  async function checkFile(selected: File) {
    setFile(selected)
    setCheckFailed(false)
    setRunFailureDetail(null)
    setQuality(null)
    setContinueAnyway(false)
    setPhase("checking")
    try {
      const form = new FormData()
      form.append("file", selected)
      const check = await apiPostForm<DrawingQualityCheck & { drawing_id?: string }>(
        "/api/drawings/check",
        form,
      )
      let result: DrawingQualityCheck & { drawing_id?: string } = check
      if (check.drawing_id) {
        result = await apiGet<DrawingQualityCheck & { drawing_id: string }>(
          `/api/drawings/${check.drawing_id}/quality`,
        )
      }
      setQuality({ verdict: result.verdict, metrics: result.metrics })
      setDrawingId(result.drawing_id ?? newCorrelationId())
      setPhase("ready")
    } catch {
      setQuality(null)
      setCheckFailed(true)
      setPhase("ready")
    }
  }

  function startRun() {
    if (!file || !quality) return
    setRunFailureDetail(null)
    setPhase("running")
    pipeline.mutate(
      { file, persist: true },
      {
        onSuccess: (result) => {
          if (result.status === "raster") {
            setRunFailureDetail(
              result.detail ?? "The drawing could not be processed by the vector pipeline.",
            )
            setPhase("ready")
            return
          }
          if (result.estimate_id) {
            router.push(`/estimates/${result.estimate_id}`)
            return
          }
          setRunFailureDetail(
            result.detail ?? "The pipeline finished without producing an estimate.",
          )
          setPhase("ready")
        },
        onError: (error: Error) => {
          setRunFailureDetail(error.message)
          setPhase("ready")
        },
      },
    )
  }

  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-xl flex-col gap-8 px-4 py-12">
        <section
          aria-labelledby="upload-heading"
          className="overflow-hidden rounded-2xl bg-ink-black p-8 pt-0"
        >
          <HazardStripe className="-mx-8 mb-6" />
          <p className="label-mono text-safety-amber">Huzaifa AEC · Takeoff</p>
          <h1
            id="upload-heading"
            className="mt-3 font-heading text-[32px] leading-[36px] tracking-[-0.01em] text-paper"
          >
            Upload a drawing to begin
          </h1>
          <GoggleLineDivider className="mt-4 w-44" />
        </section>

        <DropZone onFile={checkFile} disabled={phase === "checking"} />

        {phase === "checking" && (
          <p className="flex items-center gap-2 text-sm text-ink-500">
            <LoadingSpinner />
            Checking drawing structure...
          </p>
        )}

        {(phase === "ready" || phase === "running") && (
          <section aria-label="Quality check" className="flex flex-col gap-6">
            <div className="flex items-center gap-3" aria-hidden="true">
              <GoggleLineDivider className="flex-1 opacity-50" />
              <span className="label-mono text-steel">Quality check</span>
              <GoggleLineDivider className="flex-1 scale-x-[-1] opacity-50" />
            </div>

            {checkFailed ? (
              <ErrorState description={QUALITY_CHECK_FAILED_COPY} />
            ) : (
              quality && (
                <>
                  <QualityGateBadge quality={quality} />

                  {isDegraded && drawingId && <ReexportRequest drawingId={drawingId} />}
                  {isDegraded && !continueAnyway && phase === "ready" && (
                    <div>
                      <Button variant="outline" onClick={() => setContinueAnyway(true)}>
                        Continue anyway →
                      </Button>
                    </div>
                  )}

                  {showRunButton && (
                    <div className="flex justify-end">
                      <Button size="lg" onClick={startRun}>
                        Run takeoff →
                      </Button>
                    </div>
                  )}
                </>
              )
            )}
          </section>
        )}

        {phase === "running" && (
          <p className="flex items-center gap-2 text-sm text-ink-500">
            <LoadingSpinner />
            Running takeoff…
          </p>
        )}

        {runFailureDetail && (
          <ErrorState title="Couldn't complete the takeoff" description={runFailureDetail} />
        )}
      </div>
    </AppShell>
  )
}
