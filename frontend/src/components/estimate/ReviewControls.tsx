"use client"

import { Check, Pencil, TriangleAlert, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { BoqItem, ReviewStatus } from "@/types/estimate"

export interface ReviewControlsProps {
  item: BoqItem
  status: ReviewStatus
  onAccept: (item: BoqItem) => void
  onReset: (item: BoqItem) => void
  onReject: (item: BoqItem) => void
  onEdit: (item: BoqItem) => void
}

export function ReviewControls({
  item,
  status,
  onAccept,
  onReset,
  onReject,
  onEdit,
}: ReviewControlsProps) {
  if (status === "accepted") {
    return (
      <div className="flex items-center justify-end gap-0.5">
        {item.confidence_status === "ASSUMED" && (
          <TriangleAlert
            aria-label="Assumed value — individual review required"
            className="size-3.5 text-warning"
          />
        )}
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label={`Accepted ${item.description} — click to reset to pending`}
          aria-pressed="true"
          title="Accepted — click to reset"
          className="text-measured"
          onClick={() => onReset(item)}
        >
          <Check />
        </Button>
      </div>
    )
  }

  if (status === "rejected" || status === "corrected") {
    return (
      <div className="flex items-center justify-end gap-0.5">
        {item.confidence_status === "ASSUMED" && (
          <TriangleAlert
            aria-label="Assumed value — individual review required"
            className="size-3.5 text-warning"
          />
        )}
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label={`${status === "rejected" ? "Rejected" : "Corrected"} ${
            item.description
          } — click to reset to pending`}
          aria-pressed="true"
          title={status === "rejected" ? "Rejected — click to reset" : "Corrected — click to reset"}
          className={status === "rejected" ? "text-error" : "text-info"}
          onClick={() => onReset(item)}
        >
          <X />
        </Button>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-end gap-0.5">
      {item.confidence_status === "ASSUMED" && (
        <TriangleAlert
          aria-label="Assumed value — individual review required"
          className="size-3.5 text-warning"
        />
      )}
      <Button
        variant="ghost"
        size="icon-xs"
        aria-label={`Accept ${item.description}`}
        title="Accept"
        className="hover:text-measured"
        onClick={() => onAccept(item)}
      >
        <Check />
      </Button>
      <Button
        variant="ghost"
        size="icon-xs"
        aria-label={`Reject ${item.description}`}
        title="Reject"
        className="hover:text-error"
        onClick={() => onReject(item)}
      >
        <X />
      </Button>
      <Button
        variant="ghost"
        size="icon-xs"
        aria-label={`Edit ${item.description}`}
        title="Edit"
        onClick={() => onEdit(item)}
      >
        <Pencil />
      </Button>
    </div>
  )
}
