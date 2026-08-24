"use client"

import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import type { BoqItem } from "@/types/estimate"

export interface CorrectionResult {
  reason?: string
  correctedValue?: number
}

export interface CorrectionDialogProps {
  item: BoqItem | null
  mode: "reject" | "edit"
  open: boolean
  submitting?: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (result: CorrectionResult) => void
}

const inputClasses =
  "w-full rounded-lg border border-input bg-surface px-3 py-2 font-mono text-sm text-ink-900 outline-none transition-colors placeholder:text-ink-300 focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"

export function CorrectionDialog({
  item,
  mode,
  open,
  submitting = false,
  onOpenChange,
  onSubmit,
}: CorrectionDialogProps) {
  const [reason, setReason] = useState("")
  const [correctedValue, setCorrectedValue] = useState(() =>
    mode === "edit" && item ? String(item.quantity) : "",
  )

  const parsedValue = Number.parseFloat(correctedValue)
  const hasValidValue = correctedValue !== "" && Number.isFinite(parsedValue)
  const canSubmit = Boolean(item) && (mode === "edit" ? true : reason.trim().length > 0)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{mode === "reject" ? "Reject and correct" : "Correct quantity"}</DialogTitle>
          <DialogDescription>
            {item
              ? `Record what is wrong with “${item.description}” so the takeoff can be fixed at the source.`
              : "Record the correction for this line."}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-ink-700">
              Reason{mode === "reject" ? "" : " (optional)"}
            </span>
            <textarea
              className={`${inputClasses} min-h-20 resize-y font-sans`}
              placeholder={
                mode === "reject"
                  ? "Why is this quantity wrong?"
                  : "Anything the next reviewer should know"
              }
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              required={mode === "reject"}
            />
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-ink-700">Corrected value</span>
            <input
              type="number"
              inputMode="decimal"
              step="any"
              className={inputClasses}
              placeholder={item?.quantity != null ? String(item.quantity) : ""}
              value={correctedValue}
              onChange={(event) => setCorrectedValue(event.target.value)}
            />
            <span className="text-xs text-ink-300">
              Leave empty to keep {item ? `${item.quantity.toLocaleString("en-US")}` : "the"}{" "}
              current quantity.
            </span>
          </label>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            disabled={!canSubmit || submitting}
            onClick={() =>
              onSubmit({
                reason: reason.trim() || undefined,
                correctedValue:
                  hasValidValue && parsedValue !== item?.quantity ? parsedValue : undefined,
              })
            }
          >
            {mode === "reject" ? "Reject item" : "Save correction"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
