import Link from "next/link"
import type { ReactNode } from "react"

export interface AppShellProps {
  children: ReactNode
  right?: ReactNode
}

const NAV_LINKS = [
  { href: "/estimates", label: "Estimates" },
  { href: "/catalog", label: "Catalog" },
] as const

export function AppShell({ children, right }: AppShellProps) {
  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center justify-between border-b border-border bg-surface px-4 shadow-sm">
        <Link href="/" className="flex items-center gap-2 text-sm font-semibold text-ink-900">
          <span aria-hidden="true" className="block size-3 bg-primary" />
          AEC Blueprint
        </Link>
        <nav className="flex items-center gap-2">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded px-2 py-1 text-sm text-ink-500 transition-colors hover:bg-muted hover:text-ink-900"
            >
              {link.label}
            </Link>
          ))}
          {right}
        </nav>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  )
}
