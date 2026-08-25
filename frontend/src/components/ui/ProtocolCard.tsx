import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

export interface ProtocolRow {
  label: ReactNode
  value: ReactNode
  valueTone?: "default" | "verified"
}

export interface ProtocolCardProps {
  title?: ReactNode
  rows: ProtocolRow[]
  footer?: ReactNode
  className?: string
}

export function ProtocolCard({ title, rows, footer, className }: ProtocolCardProps) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-2xl border border-ink-black bg-ink-black font-mono text-[13px] leading-[26px] dark:border-outline-variant",
        className,
      )}
    >
      {title && (
        <p className="border-b border-white/10 px-5 py-3 text-xs tracking-[0.08em] text-paper uppercase">
          {title}
        </p>
      )}
      <dl className="px-5">
        {rows.map((row, index) => (
          <div
            key={index}
            className={cn(
              "flex items-baseline justify-between gap-4",
              index > 0 && "border-t border-white/10",
            )}
          >
            <dt className="text-paper/70">{row.label}</dt>
            <dd
              className={cn(
                "text-right tabular-nums",
                row.valueTone === "verified" ? "text-guard-green" : "text-paper",
              )}
            >
              {row.value}
            </dd>
          </div>
        ))}
      </dl>
      {footer && <div className="border-t border-white/10 px-5 py-3">{footer}</div>}
    </div>
  )
}
