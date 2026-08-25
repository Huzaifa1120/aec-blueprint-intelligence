"use client"

import { useCallback, useState } from "react"
import { useDropzone, type FileRejection } from "react-dropzone"
import { UploadCloud } from "lucide-react"

import { cn } from "@/lib/utils"

const MAX_PDF_BYTES = 50 * 1024 * 1024

export const WRONG_FILE_TYPE_COPY = "Only PDF files are accepted. Select a different file."

export const FILE_TOO_LARGE_COPY =
  "This file is larger than 50 MB. Split the drawing set and upload one sheet at a time."

export function validateDrawingFile(file: File): string | null {
  const isPdf = file.type === "application/pdf" || /\.pdf$/i.test(file.name)
  if (!isPdf) return WRONG_FILE_TYPE_COPY
  if (file.size > MAX_PDF_BYTES) return FILE_TOO_LARGE_COPY
  return null
}

export interface DropZoneProps {
  onFile: (file: File) => void
  disabled?: boolean
  className?: string
}

export function DropZone({ onFile, disabled = false, className }: DropZoneProps) {
  const [rejectionCopy, setRejectionCopy] = useState<string | null>(null)

  const onDrop = useCallback(
    (accepted: File[], rejections: FileRejection[]) => {
      const candidate = accepted[0] ?? rejections[0]?.file
      if (!candidate) return
      const error = validateDrawingFile(candidate)
      if (error) {
        setRejectionCopy(error)
        return
      }
      setRejectionCopy(null)
      onFile(candidate)
    },
    [onFile],
  )

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    multiple: false,
    disabled,
  })

  return (
    <div className="flex flex-col gap-2">
      <div
        {...getRootProps()}
        aria-label="Upload drawing PDF"
        data-testid="dropzone"
        className={cn(
          "flex min-h-48 cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-8 text-center outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
          className,
          isDragActive && !isDragReject && "border-primary bg-primary/5",
          isDragReject && "border-error bg-error/5",
          disabled && "pointer-events-none opacity-60",
        )}
      >
        <input {...getInputProps()} />
        <UploadCloud
          className={cn(
            "size-6 text-ink-300 transition-[color,transform] duration-(--duration-fast)",
            isDragActive && !isDragReject && "-translate-y-0.5 text-primary",
            isDragReject && "text-error",
          )}
          aria-hidden="true"
        />
        <p className="text-sm text-ink-700">Drop a PDF here, or click to browse</p>
        <p className="text-xs text-ink-500">Accepts: PDF (vector or raster)</p>
      </div>
      {rejectionCopy && (
        <p role="alert" className="text-sm text-error">
          {rejectionCopy}
        </p>
      )}
    </div>
  )
}
