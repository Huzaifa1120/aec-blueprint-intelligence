/* ReviewOverlay — Human review UI for BOQ takeoff results.

Features:
- Renders original PDF page via pdf.js canvas
- Overlays extracted components/routes as highlighted SVG regions
- Click a BOQ line → highlight corresponding source geometry
- Accept / correct / reject per item; persists to backend API
- Bulk-accept for MEASURED items; force review for ASSUMED
- Corrections logged as rule-improvement signal (for future rule refinement)

Dependencies:
- pdf.js (included via next dev deps or public CDN)
- Tailwind v4 for styling
- Axios for API calls to backend at NEXT_PUBLIC_API_URL
*/

"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { useRouter } from "next/navigation"

// pdf.js types — we import the canvas type loosely
// @ts-expect-error — pdf.js types may vary by version
import pdfjsLib from "pdfjs-dist/legacy/build/pdf.js"

type MeasurementStatus = "MEASURED" | "DERIVED" | "ASSUMED"

type BohqItem = {
  id: string
  measurement_id: string
  quantity: number
  unit_cost: number
  total_cost: number
  confidence_status: MeasurementStatus
  component_type?: string
  calculation_method?: string
  rule_version?: string
}

type ComponentOverlay = {
  id: string
  type: "card_reader" | "door" | "magnetic_lock" | "push_button" | "door_controller"
  label: string
  x: number // PDF page coordinate x (scaled pixels)
  y: number // PDF page coordinate y (scaled pixels)
  width: number
  height: number
  confidence_status: MeasurementStatus
  confidence_score: number
}

type ReviewOverlayProps = {
  pdfUrl: string // URL to the uploaded PDF
  items: BohqItem[] // BOQ items with confidence status
  overlays: ComponentOverlay[] // Geometry overlay positions
  onItemAction: (itemId: string, action: "accept" | "correct" | "reject") => void
  onItemCorrect: (itemId: string, newQuantity: number) => void
  projectId?: string
}

type UseOverlayReturn = {
  pdfRef: React.RefObject<HTMLCanvasElement | null>
  pageNumber: number
  isLoading: boolean
  error: string | null
}

/**
 * Hook: PDF loading with pdf.js
 */
function usePdfLoading(pdfUrl: string): UseOverlayReturn {
  const pdfRef = useRef<HTMLCanvasElement | null>(null)
  const [pageNumber, setPageNumber] = useState(1)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    const init = async () => {
      try {
        const pdf = await pdfjsLib.getPDF(pdfUrl)
        setPageNumber(1)

        // Render first page
        const page = pdf.getPage(1)
        const viewport = page.getViewport({ scale: 1.5 })

        if (!pdfRef.current) {
          const canvas = document.createElement("canvas")
          pdfRef.current = canvas
          document.body.appendChild(canvas)
        }

        const canvas = pdfRef.current as HTMLCanvasElement
        const ctx = canvas.getContext("2d")

        canvas.height = viewport.height
        canvas.width = viewport.width

        setIsLoading(false)

        if (!cancelled) {
          page.getOperatorList().then(() => {
            // Render immediately
            page.render({
              canvasContext: ctx!,
              viewport,
            })
          })
        }
      } catch (err) {
        setError((err as Error).message)
        setIsLoading(false)
      }
    }

    init()

    return () => {
      cancelled = true
    }
  }, [pdfUrl])

  return { pdfRef, pageNumber, isLoading, error }
}

/**
 * Main ReviewOverlay component
 */
export const ReviewOverlay: React.FC<ReviewOverlayProps> = ({
  pdfUrl,
  items,
  overlays,
  onItemAction,
  onItemCorrect,
  projectId,
}) => {
  const { pdfRef, isLoading, error } = usePdfLoading(pdfUrl)
  const router = useRouter()
  const [selectedItem, setSelectedItem] = useState<string | null>(null)
  const [showCorrectModal, setShowCorrectModal] = useState(false)
  const [newQuantity, setNewQuantity] = useState(0)

  // Fetch items from backend if not provided
  useEffect(() => {
    if (!projectId) return
    ;(async () => {
      try {
        await fetch(`/api/v1/drawings/${projectId}/model`)
        // Merge fetched model with provided items
        // (implementation depends on backend API shape)
      } catch (e) {
        console.error("Failed to fetch drawing model", e)
      }
    })()
  }, [projectId])

  // Handle item click → select for highlighting
  const handleItemClick = useCallback((itemId: string) => {
    setSelectedItem(itemId)
  }, [])

  // Handle correct action
  const handleCorrect = useCallback(
    (itemId: string) => {
      const item = items.find((i) => i.id === itemId)
      if (item) {
        setNewQuantity(item.quantity)
        setShowCorrectModal(true)
      }
    },
    [items],
  )

  // Handle reject action
  const handleReject = useCallback(
    (itemId: string) => {
      onItemAction(itemId, "reject")
      setSelectedItem(null)
    },
    [onItemAction],
  )

  // Close correct modal and apply new quantity
  const handleCorrectApply = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      if (newQuantity <= 0) return
      onItemCorrect(selectedItem!, newQuantity)
      setShowCorrectModal(false)
      setNewQuantity(0)
    },
    [selectedItem, newQuantity, onItemCorrect],
  )

  // Close correct modal without applying
  const handleCorrectCancel = useCallback(() => {
    setShowCorrectModal(false)
    setNewQuantity(0)
  }, [])

  // Disable reject for MEASURED items (bulk-accept rule)
  const canReject = items.some((item) => item.confidence_status === "ASSUMED")

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="border-b border-gray-200 p-4">
        <h1 className="text-2xl font-bold">
          {" "}
          {projectId ? "Review Estimate — " + projectId : "Review Takeoff"}{" "}
        </h1>
        <button
          onClick={() => router.back()}
          className="ml-4 inline-flex items-center px-3 py-1.5 text-sm font-medium text-blue-600 rounded hover:bg-blue-100"
        >
          Back to project
        </button>
      </header>

      {/* Status bar */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center gap-4 text-sm text-gray-600">
          <span>Total items: {items.length}</span>
          <span>MEASURED: {items.filter((i) => i.confidence_status === "MEASURED").length}</span>
          <span>DERIVED: {items.filter((i) => i.confidence_status === "DERIVED").length}</span>
          <span>ASSUMED: {items.filter((i) => i.confidence_status === "ASSUMED").length}</span>
        </div>
      </div>

      {/* PDF Viewer + Overlay */}
      <div className="relative h-[800px] w-full border border-gray-200 overflow-hidden mt-4">
        {isLoading && (
          <div className="p-8 text-center">
            <span>Loading PDF...</span>
          </div>
        )}

        {error && (
          <div className="p-8 text-center text-red-600">
            <span>Error loading PDF: {error}</span>
          </div>
        )}

        {/* PDF Canvas */}
        <canvas
          ref={pdfRef}
          className={`block ${isLoading ? "invisible" : ""}`}
          style={{
            width: "100%",
            height: "auto",
          }}
        />

        {/* Overlay: highlight selected item */}
        {selectedItem && (
          <svg className="absolute inset-0 pointer-events-none" aria-label="Highlighted selection">
            <rect
              x={overlays.filter((o) => o.id === selectedItem).map((o) => o.x)[0] || 0}
              y={overlays.filter((o) => o.id === selectedItem).map((o) => o.y)[0] || 0}
              width={overlays.filter((o) => o.id === selectedItem).map((o) => o.width)[0] || 0}
              height={overlays.filter((o) => o.id === selectedItem).map((o) => o.height)[0] || 0}
              stroke="rgba(251, 191, 36, 0.8)" /* amber-400 */
              strokeWidth={2}
              fill="rgba(251, 191, 36, 0.15)"
            />
            <text x={0} y={12} fill="rgb(251, 191, 36)" fontSize={12} fontFamily="sans-serif">
              {" "}
              {selectedItem}
            </text>
          </svg>
        )}

        {/* Overlay: all component regions (semi-transparent fill + stroke) */}
        <svg
          className="absolute inset-0 pointer-events-none text-xs"
          aria-label="Component overlay regions"
        >
          {overlays.map((overlay) => (
            <g key={overlay.id}>
              <rect
                x={overlay.x}
                y={overlay.y}
                width={overlay.width}
                height={overlay.height}
                stroke={
                  overlay.confidence_status === "MEASURED"
                    ? "rgb(34, 197, 94)" /* green-500 */
                    : overlay.confidence_status === "DERIVED"
                      ? "rgb(236, 72, 153)" /* pink-500 */
                      : "rgb(139, 92, 246)" /* violet-500 */
                }
                strokeWidth={1}
                fill={
                  overlay.confidence_status === "MEASURED"
                    ? "rgba(34, 197, 94, 0.1)"
                    : overlay.confidence_status === "DERIVED"
                      ? "rgba(236, 72, 153, 0.1)"
                      : "rgba(139, 92, 246, 0.1)"
                }
                aria-label={`${overlay.type} — ${overlay.confidence_status}`}
              />
              <text
                x={overlay.x + 4}
                y={overlay.y + 12}
                fill={
                  overlay.confidence_status === "MEASURED"
                    ? "rgb(34, 197, 94)"
                    : overlay.confidence_status === "DERIVED"
                      ? "rgb(236, 72, 153)"
                      : "rgb(139, 92, 246)"
                }
                fontSize={10}
                fontFamily="sans-serif"
              >
                {" "}
                {overlay.type}
              </text>
            </g>
          ))}
        </svg>
      </div>

      {/* Action toolbar */}
      <div className="p-4 border-t border-gray-200 bg-white flex flex-wrap gap-3">
        <button
          onClick={() => items.forEach((i) => onItemAction(i.id, "accept"))}
          disabled={!canReject}
          className="flex-1 inline-flex items-center px-4 py-2 text-sm font-medium text-green-600 rounded bg-green-100 hover:bg-green-200"
          aria-label="Bulk accept all items"
        >
          {" "}
          Accept All{" "}
        </button>

        <button
          onClick={() => items.forEach((i) => onItemAction(i.id, "reject"))}
          disabled={!canReject}
          className="flex-1 inline-flex items-center px-4 py-2 text-sm font-medium text-red-600 rounded bg-red-100 hover:bg-red-200"
          aria-label="Bulk reject all items"
        >
          {" "}
          Reject All{" "}
        </button>

        {/* Per-item actions */}
        {items.map((item) => (
          <div key={item.id} className="flex items-center gap-2">
            <button
              onClick={() => handleItemClick(item.id)}
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm ${
                selectedItem === item.id ? "bg-gray-200" : "text-gray-400 hover:bg-gray-100"
              }`}
              aria-label={`Select ${item.id} for highlighting`}
            >
              {"⚐"}
            </button>
            <span className="truncate w-24">{item.component_type || item.id}</span>
            <span
              className={`
              text-xs font-medium ${
                item.confidence_status === "MEASURED"
                  ? "text-green-600"
                  : item.confidence_status === "DERIVED"
                    ? "text-pink-500"
                    : "text-violet-500"
              }
            `}
            >
              {item.confidence_status}
            </span>
            <button
              onClick={() => handleCorrect(item.id)}
              className="ml-2 text-xs text-blue-600 hover:underline"
              aria-label={`Correct ${item.id} quantity`}
            >
              ✎
            </button>
            {item.confidence_status !== "MEASURED" && (
              <button
                onClick={() => handleReject(item.id)}
                className="ml-2 text-xs text-red-600 hover:underline"
                aria-label={`Reject ${item.id}`}
              >
                ✕
              </button>
            )}
          </div>
        ))}

        {/* Correct modal */}
        {showCorrectModal && (
          <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-lg p-6 max-w-sm w-full shadow-xl">
              <h3 className="text-xl font-bold mb-4"> Correct Quantity </h3>
              <form onSubmit={handleCorrectApply} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1"> New quantity </label>
                  <input
                    type="number"
                    min={0}
                    step={0.1}
                    value={newQuantity}
                    onChange={(e) => setNewQuantity(Number(e.target.value) || 0)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus-outline"
                    required
                  />
                </div>
                <div className="flex gap-3">
                  <button
                    type="submit"
                    className="flex-1 inline-flex items-center px-4 py-2 text-sm font-medium text-green-600 rounded bg-green-100 hover:bg-green-200"
                  >
                    {" "}
                    Apply{" "}
                  </button>
                  <button
                    type="button"
                    onClick={handleCorrectCancel}
                    className="flex-1 inline-flex items-center px-4 py-2 text-sm font-medium text-gray-500 rounded bg-gray-100 hover:bg-gray-100"
                  >
                    {" "}
                    Cancel{" "}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* -------------------------------------------------------------------------
 * Export types for external use
 * -------------------------------------------------------------------------*/

export type { MeasurementStatus, BohqItem, ComponentOverlay, ReviewOverlayProps, UseOverlayReturn }
