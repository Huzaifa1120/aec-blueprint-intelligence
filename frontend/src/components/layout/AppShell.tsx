"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import type { ReactNode } from "react"

import { cn } from "@/lib/utils"
import { GoggleLineDivider } from "@/components/ui/GoggleLineDivider"
import { HazardStripe } from "@/components/ui/HazardStripe"
import { ThemeToggle } from "./ThemeToggle"

export interface AppShellProps {
  children: ReactNode
  right?: ReactNode
}

const NAV_LINKS = [
  { href: "/estimates", label: "Estimates" },
  { href: "/catalog", label: "Catalog" },
] as const

export function AppShell({ children, right }: AppShellProps) {
  const pathname = usePathname() ?? "/"
  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="sticky top-0 z-40 bg-ink-black text-paper shadow-sm">
        <HazardStripe />
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-white/10 px-4">
          <Link href="/" className="group flex items-center gap-2.5" aria-label="Huzaifa AEC home">
            <span
              aria-hidden="true"
              className="block size-3 rounded-[2px] bg-safety-amber transition-transform group-hover:rotate-45"
            />
            <span className="font-heading text-[17px] leading-[22px] tracking-normal text-paper">
              Huzaifa AEC
            </span>
          </Link>
          <nav className="flex items-center gap-1">
            {NAV_LINKS.map((link) => {
              const active = pathname === link.href || pathname.startsWith(`${link.href}/`)
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "rounded-md px-2.5 py-1.5 font-mono text-xs tracking-[0.08em] uppercase transition-colors",
                    active
                      ? "bg-safety-amber text-ink-black"
                      : "text-paper/70 hover:bg-white/10 hover:text-paper",
                  )}
                >
                  {link.label}
                </Link>
              )
            })}
            <ThemeToggle />
            {right}
          </nav>
        </div>
        <GoggleLineDivider className="h-1 opacity-80" />
      </header>
      <main className="flex-1">{children}</main>
      <footer className="bg-ink-black">
        <GoggleLineDivider className="h-1 opacity-40" />
        <div className="flex items-center justify-between px-4 py-4">
          <p className="label-mono text-paper/50">Huzaifa AEC · Quantity takeoff</p>
          <p className="label-mono text-paper/50">AI proposes · Geometry calculates</p>
        </div>
        <HazardStripe />
      </footer>
    </div>
  )
}
