import type { ReactNode } from "react"

import { GoggleLineDivider } from "@/components/ui/GoggleLineDivider"

export interface PageHeaderProps {
  title: string
  description?: string
  eyebrow?: string
  actions?: ReactNode
}

export function PageHeader({ title, description, eyebrow, actions }: PageHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4 pb-6">
      <div className="min-w-0">
        {eyebrow && <p className="label-mono mb-1.5 text-safety-amber">{eyebrow}</p>}
        <h1 className="font-heading text-[32px] leading-[36px] tracking-[-0.01em] text-ink-black">
          {title}
        </h1>
        <GoggleLineDivider className="mt-2 w-40" />
        {description && <p className="mt-3 max-w-prose text-sm text-steel">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  )
}
