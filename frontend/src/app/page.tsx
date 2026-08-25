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
import { ProtocolCard } from "@/components/ui/ProtocolCard"
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

const STEPS = [
  {
    n: "01",
    title: "Quality gate",
    body: "Layer and text metrics classify the sheet as layered, degraded, or raster before anything runs.",
  },
  {
    n: "02",
    title: "Deterministic takeoff",
    body: "Geometry engines measure; rule assemblies derive quantities. No model ever guesses a number.",
  },
  {
    n: "03",
    title: "Human review",
    body: "Every line item carries provenance and a confidence tier you can accept or correct.",
  },
] as const

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
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-8">
        <section
          aria-labelledby="upload-heading"
          className="rise-in overflow-hidden rounded-2xl bg-ink-black p-8 pt-0 sm:p-10 sm:pt-0"
        >
          <HazardStripe className="-mx-8 mb-6 sm:-mx-10" />
          <p className="label-mono text-safety-amber">Huzaifa AEC · Takeoff</p>
          <h1
            id="upload-heading"
            className="mt-3 font-heading text-[40px] leading-[44px] tracking-[-0.01em] text-paper md:text-[52px] md:leading-[54px]"
          >
            Upload a drawing to begin
          </h1>
          <p className="mt-4 max-w-xl text-sm leading-6 text-paper/70">
            AI proposes · Geometry calculates · Rules derive · Humans approve. Every quantity traces
            back to a deterministic measurement on your drawing.
          </p>
          <GoggleLineDivider className="mt-5 w-44" />
        </section>

        <div className="rise-in rise-in-d1 grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="flex flex-col gap-6">
            <div className="rounded-lg border border-outline-variant bg-surface-container p-4">
              <DropZone
                onFile={checkFile}
                disabled={phase === "checking"}
                className="min-h-64 bg-canvas"
              />
            </div>

            {phase === "checking" && (
              <p className="flex items-center gap-2 text-sm text-ink-500 rise-in">
                <LoadingSpinner />
                Checking drawing structure...
              </p>
            )}

            {(phase === "ready" || phase === "running") && (
              <section aria-label="Quality check" className="flex flex-col gap-6 rise-in">
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
              <p className="flex items-center gap-2 text-sm text-ink-500 rise-in">
                <LoadingSpinner />
                Running takeoff…
              </p>
            )}

            {runFailureDetail && (
              <ErrorState title="Couldn't complete the takeoff" description={runFailureDetail} />
            )}
          </div>

          <aside aria-label="Pipeline contract">
            <ProtocolCard
              title="Pipeline contract"
              className="rise-in"
              rows={[
                { label: "Verdict rule", value: "measured > derived > assumed" },
                { label: "Input", value: "PDF ≤ 50 MB" },
                { label: "Scale", value: "auto · flagged if assumed" },
                { label: "Output", value: "BOQ → review" },
                { label: "Quantities", value: "deterministic only", valueTone: "verified" },
              ]}
              footer={<p className="label-mono text-paper/50">No model ever outputs a number</p>}
            />
          </aside>
        </div>

        <ol className="rise-in rise-in-d2 grid gap-4 sm:grid-cols-3">
          {STEPS.map((step) => (
            <li
              key={step.n}
              className="rounded-lg border border-outline-variant bg-paper p-5 transition-colors hover:border-safety-amber"
            >
              <p className="label-mono text-steel">Step {step.n}</p>
              <h2 className="mt-1 font-heading text-[17px] leading-[22px] text-ink-black">
                {step.title}
              </h2>
              <GoggleLineDivider className="mt-2 w-16" />
              <p className="mt-2 text-sm leading-[22px] text-ink-500">{step.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </AppShell>
  )
}
