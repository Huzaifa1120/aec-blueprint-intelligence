"use client"

import { useState, type FormEvent } from "react"

import { apiPost } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { LoadingSpinner } from "@/components/common/LoadingSpinner"

export const REEXPORT_MESSAGE =
  "The tool we're using for quantity takeoff requires the PDF to be exported with layers preserved. In AutoCAD: File → Export → PDF → 'Include Layer Information' checked."

const INVALID_EMAIL_COPY = "Enter a valid email address."
const SEND_FAILED_COPY = "Couldn't send the request. Check the recipient address and try again."

type SendPhase = "idle" | "sending" | "sent"

export interface ReexportRequestProps {
  drawingId: string
}

export function ReexportRequest({ drawingId }: ReexportRequestProps) {
  const [recipient, setRecipient] = useState("")
  const [message, setMessage] = useState(REEXPORT_MESSAGE)
  const [phase, setPhase] = useState<SendPhase>("idle")
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!/^\S+@\S+\.\S+$/.test(recipient.trim())) {
      setError(INVALID_EMAIL_COPY)
      return
    }
    setError(null)
    setPhase("sending")
    try {
      await apiPost(`/api/drawings/${drawingId}/request-reexport`, {
        recipient: recipient.trim(),
        message,
      })
      setPhase("sent")
    } catch {
      setPhase("idle")
      setError(SEND_FAILED_COPY)
    }
  }

  if (phase === "sent") {
    return (
      <div
        role="status"
        data-testid="reexport-sent"
        className="rounded-lg border border-border bg-canvas p-4"
      >
        <p className="text-sm font-semibold text-success">Request sent.</p>
        <p className="mt-1 text-sm text-ink-500">
          You can continue while you wait for the re-exported PDF.
        </p>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3" noValidate>
      <div className="flex flex-col gap-1">
        <label htmlFor="reexport-recipient" className="text-xs font-medium text-ink-700">
          Recipient email
        </label>
        <input
          id="reexport-recipient"
          type="email"
          required
          value={recipient}
          onChange={(event) => setRecipient(event.target.value)}
          placeholder="author@company.com"
          aria-invalid={error === INVALID_EMAIL_COPY || undefined}
          className="h-9 rounded-lg border border-input bg-surface px-3 text-sm text-ink-900 outline-none placeholder:text-ink-300 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="reexport-message" className="text-xs font-medium text-ink-700">
          Message to the author
        </label>
        <textarea
          id="reexport-message"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          rows={4}
          className="resize-y rounded-lg border border-input bg-surface px-3 py-2 text-sm leading-relaxed text-ink-900 outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        />
      </div>
      {error && (
        <p role="alert" className="text-sm text-error">
          {error}
        </p>
      )}
      <div>
        <Button type="submit" disabled={phase === "sending"}>
          {phase === "sending" ? <LoadingSpinner className="text-primary-foreground" /> : null}
          Request re-export
        </Button>
      </div>
    </form>
  )
}
