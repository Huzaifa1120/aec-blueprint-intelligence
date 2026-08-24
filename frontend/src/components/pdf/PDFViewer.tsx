"use client"

import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react"
import * as pdfjsLib from "pdfjs-dist"
import type { PDFDocumentLoadingTask, PDFDocumentProxy, RenderTask } from "pdfjs-dist"
import { Minus, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import SourceHighlight, {
  bboxToCanvasRect,
  clearCanvas,
  drawSourceHighlight,
  type HighlightBBox,
} from "./SourceHighlight"

pdfjsLib.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs"

export interface PDFViewerHandle {
  navigateTo: (page: number) => void
  drawHighlight: (bbox: HighlightBBox) => void
  clearHighlight: () => void
}

export interface PDFViewerProps {
  src?: string | null
  highlightMessage?: string | null
}

const MIN_ZOOM = 25
const MAX_ZOOM = 400
const ZOOM_STEP = 20

type Status = "idle" | "loading" | "ready" | "error"

function clampPage(page: number, pageCount: number): number {
  return Math.min(Math.max(page, 1), Math.max(pageCount, 1))
}

interface ViewportSnapshot {
  scale: number
  height: number
  viewBox: number[]
}

const PDFViewer = forwardRef<PDFViewerHandle, PDFViewerProps>(function PDFViewer(
  { src = null, highlightMessage = null },
  ref,
) {
  const scrollAreaRef = useRef<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const overlayRef = useRef<HTMLCanvasElement | null>(null)
  const docRef = useRef<PDFDocumentProxy | null>(null)
  const loadingTaskRef = useRef<PDFDocumentLoadingTask | null>(null)
  const viewportRef = useRef<ViewportSnapshot | null>(null)
  const renderTaskRef = useRef<RenderTask | null>(null)
  const cancelHighlightRef = useRef<(() => void) | null>(null)
  const pendingBBoxRef = useRef<HighlightBBox | null>(null)
  const fitScaleRef = useRef<number>(0)
  const docVersionRef = useRef(0)

  const [docVersion, setDocVersion] = useState(0)
  const [page, setPage] = useState(1)
  const [numPages, setNumPages] = useState(0)
  const [zoomPct, setZoomPct] = useState(100)
  const [status, setStatus] = useState<Status>("idle")
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const cancelActiveHighlight = useCallback(() => {
    cancelHighlightRef.current?.()
    cancelHighlightRef.current = null
    clearCanvas(overlayRef.current)
  }, [])

  const paintHighlight = useCallback(
    (bbox: HighlightBBox) => {
      const overlay = overlayRef.current
      const viewport = viewportRef.current
      if (!overlay || !viewport) return
      cancelActiveHighlight()
      const rect = bboxToCanvasRect(bbox, viewport)
      if (rect.x2 <= rect.x1 || rect.y2 <= rect.y1) return
      cancelHighlightRef.current = drawSourceHighlight(overlay, rect)
    },
    [cancelActiveHighlight],
  )

  const renderPage = useCallback(
    async (pageNumber: number, zoom: number): Promise<void> => {
      const doc = docRef.current
      const canvas = canvasRef.current
      const scrollArea = scrollAreaRef.current
      if (!doc || !canvas || !scrollArea) return

      renderTaskRef.current?.cancel()
      const nextPage = await doc.getPage(clampPage(pageNumber, doc.numPages))
      if (canvasRef.current !== canvas) return

      const unitViewport = nextPage.getViewport({ scale: 1 })
      if (fitScaleRef.current === 0 && unitViewport.width > 0) {
        fitScaleRef.current = Math.max((scrollArea.clientWidth - 32) / unitViewport.width, 0.05)
      }
      const scale = Math.max(fitScaleRef.current * (zoom / 100), 0.05)
      const viewport = nextPage.getViewport({ scale })
      viewportRef.current = {
        scale,
        height: viewport.height,
        viewBox: [...viewport.viewBox],
      }

      const dpr = typeof window === "undefined" ? 1 : window.devicePixelRatio || 1
      canvas.width = Math.max(Math.floor(viewport.width * dpr), 1)
      canvas.height = Math.max(Math.floor(viewport.height * dpr), 1)
      canvas.style.width = `${Math.floor(viewport.width)}px`
      canvas.style.height = `${Math.floor(viewport.height)}px`

      const overlay = overlayRef.current
      if (overlay) {
        overlay.width = canvas.width
        overlay.height = canvas.height
        overlay.style.width = canvas.style.width
        overlay.style.height = canvas.style.height
      }

      const task = nextPage.render({
        canvas,
        viewport,
        transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined,
      })
      renderTaskRef.current = task
      try {
        await task.promise
      } catch (error) {
        if (error instanceof pdfjsLib.RenderingCancelledException) return
        throw error
      }
      const pending = pendingBBoxRef.current
      if (pending && canvasRef.current === canvas) {
        pendingBBoxRef.current = null
        paintHighlight(pending)
      }
    },
    [paintHighlight],
  )

  useEffect(() => {
    let disposed = false
    pendingBBoxRef.current = null
    cancelActiveHighlight()
    viewportRef.current = null
    fitScaleRef.current = 0

    async function load() {
      if (!src) {
        void loadingTaskRef.current?.destroy()
        loadingTaskRef.current = null
        docRef.current = null
        docVersionRef.current += 1
        setDocVersion(docVersionRef.current)
        setNumPages(0)
        setPage(1)
        setStatus("idle")
        return
      }
      setStatus("loading")
      setErrorMessage(null)
      hasRenderErrorRef.current = false
      try {
        const loadingTask = pdfjsLib.getDocument({ url: src })
        loadingTaskRef.current = loadingTask
        const doc = await loadingTask.promise
        if (disposed) {
          void loadingTask.destroy()
          return
        }
        if (loadingTaskRef.current !== loadingTask) void loadingTaskRef.current?.destroy()
        docRef.current = doc
        fitScaleRef.current = 0
        docVersionRef.current += 1
        setDocVersion(docVersionRef.current)
        setNumPages(doc.numPages)
        setPage(1)
        setStatus("ready")
      } catch (error) {
        if (disposed) return
        setStatus("error")
        setErrorMessage(error instanceof Error ? error.message : "Couldn't render this PDF.")
      }
    }
    void load()

    return () => {
      disposed = true
      renderTaskRef.current?.cancel()
      cancelActiveHighlight()
    }
  }, [src, cancelActiveHighlight])

  const hasRenderErrorRef = useRef(false)

  useEffect(() => {
    if (!docRef.current || hasRenderErrorRef.current) return
    let active = true
    renderPage(page, zoomPct).catch((error: unknown) => {
      if (active) {
        hasRenderErrorRef.current = true
        setStatus("error")
        setErrorMessage(error instanceof Error ? error.message : "Couldn't render this PDF.")
      }
    })
    return () => {
      active = false
      renderTaskRef.current?.cancel()
    }
  }, [docVersion, page, zoomPct, renderPage])

  useEffect(() => {
    return () => {
      renderTaskRef.current?.cancel()
      cancelActiveHighlight()
      void loadingTaskRef.current?.destroy()
      loadingTaskRef.current = null
      docRef.current = null
    }
  }, [cancelActiveHighlight])

  useImperativeHandle(
    ref,
    (): PDFViewerHandle => ({
      navigateTo(target: number) {
        setPage((current) => clampPage(target, numPages || current))
      },
      drawHighlight(bbox: HighlightBBox) {
        pendingBBoxRef.current = bbox
        if (viewportRef.current) paintHighlight(bbox)
      },
      clearHighlight() {
        pendingBBoxRef.current = null
        cancelActiveHighlight()
      },
    }),
    [numPages, paintHighlight, cancelActiveHighlight],
  )

  const stepZoom = (delta: number) =>
    setZoomPct((z) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z + delta)))

  return (
    <div className="flex h-full min-h-0 flex-col bg-canvas">
      <div
        ref={scrollAreaRef}
        className="flex min-h-0 flex-1 items-start justify-center overflow-auto p-4"
      >
        <div className="relative" data-testid="pdf-stage">
          <canvas
            data-testid="pdf-render"
            id="pdf-render"
            className={numPages === 0 ? "hidden" : "block shadow-sm"}
          />
          <SourceHighlight canvasRef={overlayRef} />
          {status === "idle" && (
            <p className="max-w-xs text-sm text-ink-500">
              Drawing preview unavailable. The source file is not connected to this workspace yet.
            </p>
          )}
          {status === "loading" && (
            <Skeleton className="absolute inset-0 rounded-md" aria-label="Loading drawing" />
          )}
          {status === "error" && (
            <p role="alert" className="text-sm text-error">
              Couldn&apos;t render this PDF{errorMessage ? `: ${errorMessage}` : "."}
            </p>
          )}
          {highlightMessage && (
            <div className="pointer-events-none absolute inset-x-0 bottom-3 left-1/2 w-max max-w-full -translate-x-1/2 px-2">
              <p className="mx-auto w-fit rounded-md bg-surface/95 px-3 py-1.5 text-xs text-ink-500 shadow-sm">
                {highlightMessage}
              </p>
            </div>
          )}
        </div>
      </div>
      <footer className="flex h-10 shrink-0 items-center justify-center gap-2 border-t border-border bg-surface px-4">
        <span className="font-mono text-xs tabular-nums text-ink-500" data-testid="pdf-page-label">
          {numPages > 0 ? `p.${page} of ${numPages}` : "p.– of –"}
        </span>
        <span aria-hidden="true" className="h-px w-6 bg-border" />
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label="Zoom out"
          disabled={zoomPct <= MIN_ZOOM || numPages === 0}
          onClick={() => stepZoom(-ZOOM_STEP)}
        >
          <Minus />
        </Button>
        <span className="w-12 text-center font-mono text-xs tabular-nums text-ink-700">
          {zoomPct}%
        </span>
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label="Zoom in"
          disabled={zoomPct >= MAX_ZOOM || numPages === 0}
          onClick={() => stepZoom(ZOOM_STEP)}
        >
          <Plus />
        </Button>
      </footer>
    </div>
  )
})

export default PDFViewer
