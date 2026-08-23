"use client"

import { useEffect, useRef } from "react"
import { cn } from "@/lib/utils"

export interface HighlightBBox {
  x1: number
  y1: number
  x2: number
  y2: number
}

export interface HighlightRect {
  x1: number
  y1: number
  x2: number
  y2: number
}

export interface CanvasViewport {
  scale: number
  height: number
  viewBox: number[]
}

export function bboxToCanvasRect(bbox: HighlightBBox, viewport: CanvasViewport): HighlightRect {
  const pdfHeight = (viewport.viewBox[3] ?? 0) - (viewport.viewBox[1] ?? 0)
  return {
    x1: bbox.x1 * viewport.scale,
    y1: (pdfHeight - bbox.y2) * viewport.scale,
    x2: bbox.x2 * viewport.scale,
    y2: (pdfHeight - bbox.y1) * viewport.scale,
  }
}

function readToken(name: string, fallback: number): number {
  if (typeof window === "undefined") return fallback
  const value = Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name))
  return Number.isFinite(value) ? value : fallback
}

function readColor(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

export function clearCanvas(canvas: HTMLCanvasElement | null): void {
  if (!canvas) return
  canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height)
}

const SETTLED_FILL_MIN = 0.15
const SETTLED_FILL_MAX = 0.25
const PULSE_PERIOD_MS = 2000

export function drawSourceHighlight(canvas: HTMLCanvasElement, rect: HighlightRect): () => void {
  const ctx = canvas.getContext("2d")
  if (!ctx) return () => {}

  const cssWidth = canvas.clientWidth || canvas.width
  const dpr = cssWidth > 0 ? canvas.width / cssWidth : 1
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  clearCanvas(canvas)

  const accent = readColor("--engineering-blue", "#0072cf")
  const slow = readToken("--duration-slow", 380)
  const phase1 = Math.min(160, slow)
  const total = Math.max(slow, phase1)

  const x = Math.min(rect.x1, rect.x2)
  const y = Math.min(rect.y1, rect.y2)
  const w = Math.abs(rect.x2 - rect.x1)
  const h = Math.abs(rect.y2 - rect.y1)
  const cx = x + w / 2
  const cy = y + h / 2
  const corners: Array<[number, number]> = [
    [x, y],
    [x + w, y],
    [x + w, y + h],
    [x, y + h],
  ]

  let raf = 0
  const start = performance.now()

  const paintSettled = (fillAlpha: number) => {
    ctx.strokeStyle = accent
    ctx.lineWidth = 1.5
    ctx.globalAlpha = 0.9
    ctx.strokeRect(x, y, w, h)
    ctx.globalAlpha = fillAlpha
    ctx.fillStyle = accent
    ctx.fillRect(x, y, w, h)
    ctx.globalAlpha = 1
  }

  const drawCornerCrosshairs = (progress: number) => {
    const armLength = Math.min(14, w / 3, h / 3)
    ctx.strokeStyle = accent
    ctx.lineWidth = 1.5
    ctx.globalAlpha = 0.9
    for (const [tx, ty] of corners) {
      const px = cx + (tx - cx) * progress
      const py = cy + (ty - cy) * progress
      const dx = tx === cx ? 0 : Math.sign(tx - cx)
      const dy = ty === cy ? 0 : Math.sign(ty - cy)
      ctx.beginPath()
      ctx.moveTo(px - dx * armLength * progress, py)
      ctx.lineTo(px, py)
      ctx.lineTo(px, py - dy * armLength * progress)
      ctx.stroke()
    }
    ctx.globalAlpha = 1
  }

  if (total === 0) {
    paintSettled((SETTLED_FILL_MIN + SETTLED_FILL_MAX) / 2)
    return () => {}
  }

  const frame = (now: number) => {
    const elapsed = now - start
    clearCanvas(canvas)
    if (elapsed < phase1) {
      drawCornerCrosshairs(elapsed / phase1)
    } else if (elapsed < total) {
      const q = (elapsed - phase1) / Math.max(total - phase1, 1)
      drawCornerCrosshairs(1)
      ctx.globalAlpha = q
      ctx.fillStyle = accent
      ctx.fillRect(x, y, w, h)
      ctx.globalAlpha = Math.min(q * 1.5, 0.9)
      ctx.strokeStyle = accent
      ctx.lineWidth = 1.5
      ctx.strokeRect(x, y, w, h)
      ctx.globalAlpha = 1
    } else {
      const settledFor = elapsed - total
      const wave =
        SETTLED_FILL_MIN +
        ((SETTLED_FILL_MAX - SETTLED_FILL_MIN) *
          (Math.sin((2 * Math.PI * settledFor) / PULSE_PERIOD_MS) + 1)) /
          2
      paintSettled(wave)
    }
    raf = requestAnimationFrame(frame)
  }
  raf = requestAnimationFrame(frame)

  return () => cancelAnimationFrame(raf)
}

export interface SourceHighlightProps {
  canvasRef: React.RefObject<HTMLCanvasElement | null>
  className?: string
}

export default function SourceHighlight({ canvasRef, className }: SourceHighlightProps) {
  const localRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    return () => clearCanvas(localRef.current)
  }, [])

  return (
    <canvas
      ref={(node) => {
        localRef.current = node
        canvasRef.current = node
      }}
      aria-hidden="true"
      data-testid="source-highlight-overlay"
      className={cn("pointer-events-none absolute inset-0", className)}
    />
  )
}
