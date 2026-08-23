import Link from "next/link"
import type { ReactNode } from "react"

export interface AppShellProps {
  children: ReactNode
  right?: ReactNode
}

export function AppShell({ children, right }: AppShellProps) {
  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center justify-between border-b border-border bg-surface px-4 shadow-sm">
        <Link href="/" className="flex items-center gap-2 text-sm font-semibold text-ink-900">
          <span aria-hidden="true" className="block size-3 bg-primary" />
          AEC Blueprint
        </Link>
        <nav className="flex items-center gap-2">{right}</nav>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  )
}
