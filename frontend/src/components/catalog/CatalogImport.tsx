"use client"

import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useDropzone, type FileRejection } from "react-dropzone"
import { FileSpreadsheet, UploadCloud } from "lucide-react"

import { apiPostForm } from "@/lib/api"
import type { CatalogImportError, CatalogImportResult } from "@/types/catalog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ErrorState } from "@/components/common/ErrorState"
import { LoadingSpinner } from "@/components/common/LoadingSpinner"
import { cn } from "@/lib/utils"

export const CATALOG_IMPORT_CARD_ID = "catalog-import"

const ACCEPTED_FILES = {
  "text/csv": [".csv"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
}

const REJECTION_COPY = "Only CSV or Excel (.xlsx) files are accepted. Select a different file."

export interface NormalizedImportError {
  row: number | null
  message: string
}

export function normalizeImportError(error: CatalogImportError): NormalizedImportError {
  const rawRow =
    typeof error.row === "number" ? error.row : typeof error.index === "number" ? error.index : null
  return {
    row: rawRow !== null && rawRow > 0 ? rawRow : null,
    message: error.message ?? error.reason ?? error.detail ?? "This row was skipped.",
  }
}

function buildTemplateCsv(): string {
  return [
    "material_name,unit,unit_price,category,effective_from,effective_to,source",
    "<name>,<ea|m|nr|...>,<unit_price>,<category>,YYYY-MM-DD,,spreadsheet_import",
    "",
    "rate_name,productivity_rate,hourly_rate,category,effective_from,effective_to,source",
    "<name>,<units per labor-hour>,<hourly_rate>,<category>,YYYY-MM-DD,,spreadsheet_import",
    "",
  ].join("\n")
}

function downloadTemplate() {
  const blob = new Blob([buildTemplateCsv()], { type: "text/csv" })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = "catalog-template.csv"
  anchor.click()
  URL.revokeObjectURL(url)
}

function formatImportLine({ row, message }: NormalizedImportError): string {
  return row === null ? message : `Row ${row}: ${message}`
}

export function CatalogImport() {
  const queryClient = useQueryClient()
  const [rejectionCopy, setRejectionCopy] = useState<string | null>(null)
  const [lastFile, setLastFile] = useState<File | null>(null)

  const mutation = useMutation<CatalogImportResult, Error, File>({
    mutationFn: (file) => {
      const form = new FormData()
      form.append("file", file)
      return apiPostForm<CatalogImportResult>("/api/catalog/import", form)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["catalog"] })
    },
  })

  const onDrop = (accepted: File[], rejections: FileRejection[]) => {
    if (accepted.length > 0) {
      setRejectionCopy(null)
      setLastFile(accepted[0])
      mutation.mutate(accepted[0])
    } else if (rejections.length > 0) {
      setRejectionCopy(REJECTION_COPY)
    }
  }

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: ACCEPTED_FILES,
    multiple: false,
    disabled: mutation.isPending,
  })

  const result = mutation.data
  const errors = (result?.errors ?? []).map(normalizeImportError)
  const errorCount = errors.length
  const importedCount = result?.successful ?? result?.imported ?? 0

  return (
    <Card data-testid="catalog-import">
      <CardHeader>
        <CardTitle>Import</CardTitle>
        <CardDescription>
          Add material prices and labor rates from a CSV or Excel export. Rows that fail validation
          are listed after upload — nothing is silently dropped.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {mutation.isPending ? (
          <div className="flex items-center gap-2 rounded-lg border border-dashed border-border p-6 text-sm text-ink-500">
            <LoadingSpinner />
            Importing rates…
          </div>
        ) : (
          <div
            {...getRootProps()}
            id={CATALOG_IMPORT_CARD_ID}
            tabIndex={-1}
            aria-label="Upload catalog spreadsheet"
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-8 text-center outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
              isDragActive && !isDragReject && "border-primary bg-primary/5",
              isDragReject && "border-error bg-error/5",
            )}
          >
            <input {...getInputProps()} />
            <UploadCloud className="size-6 text-ink-300" aria-hidden="true" />
            <p className="text-sm text-ink-700">
              Drop a CSV or Excel file here, or click to browse.
            </p>
            <p className="flex items-center gap-1 text-xs text-ink-500">
              <FileSpreadsheet className="size-3" aria-hidden="true" />
              Accepted: .csv, .xlsx
            </p>
          </div>
        )}

        <p className="text-xs text-ink-500">
          Template:{" "}
          <Button variant="link" size="xs" onClick={downloadTemplate}>
            Download starter CSV
          </Button>
        </p>

        {rejectionCopy && (
          <p role="alert" className="text-sm text-error">
            {rejectionCopy}
          </p>
        )}

        {mutation.isError && (
          <ErrorState
            title="Couldn't import this file."
            description={
              mutation.error.message ||
              "The server rejected the upload. Check the file and try again."
            }
            action={
              lastFile && (
                <Button variant="outline" size="sm" onClick={() => mutation.mutate(lastFile)}>
                  Try again
                </Button>
              )
            }
          />
        )}

        {mutation.isSuccess && result && (
          <div
            role="status"
            data-testid="import-result"
            className="rounded-lg border border-border bg-surface p-4"
          >
            <p className="text-sm font-medium text-ink-900">
              {errorCount > 0 ? `Import complete — ${errorCount} errors found` : "Import complete"}
            </p>
            {errorCount > 0 && (
              <ul data-testid="import-errors" className="mt-2 list-none space-y-1 pl-2">
                {errors.map((line, index) => (
                  <li key={`${line.row ?? "file"}-${index}`} className="text-sm text-ink-700">
                    {formatImportLine(line)}
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-sm text-ink-500">{importedCount} rows imported successfully.</p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
