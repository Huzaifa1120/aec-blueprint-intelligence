"use client"

import { FileText, Info, Plus, RotateCcw } from "lucide-react"
import type { ReactNode } from "react"

import { EmptyState } from "@/components/common/EmptyState"
import { ErrorState } from "@/components/common/ErrorState"
import { LoadingSpinner } from "@/components/common/LoadingSpinner"
import { PageHeader } from "@/components/common/PageHeader"
import { ConfidenceBadge } from "@/components/estimate/ConfidenceBadge"
import { AppShell } from "@/components/layout/AppShell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { TIER_ORDER } from "@/lib/confidenceTier"
import { cn } from "@/lib/utils"
import type { SourceQuality } from "@/types/api"

interface Swatch {
  token: string
  hex: string
  swatchClass: string
}

const COLOR_GROUPS: { group: string; swatches: Swatch[] }[] = [
  {
    group: "Ink scale",
    swatches: [
      { token: "ink-900", hex: "#0b1929", swatchClass: "bg-ink-900" },
      { token: "ink-700", hex: "#1a3050", swatchClass: "bg-ink-700" },
      { token: "ink-500", hex: "#3e618a", swatchClass: "bg-ink-500" },
      { token: "ink-300", hex: "#7a9fbf", swatchClass: "bg-ink-300" },
      { token: "ink-100", hex: "#c8d8ea", swatchClass: "bg-ink-100" },
      { token: "ink-50", hex: "#e8eef5", swatchClass: "bg-ink-50" },
    ],
  },
  {
    group: "Surfaces",
    swatches: [
      { token: "canvas", hex: "#f2f5f9", swatchClass: "bg-canvas" },
      { token: "surface", hex: "#ffffff", swatchClass: "bg-surface" },
    ],
  },
  {
    group: "Accent",
    swatches: [
      { token: "accent-base", hex: "#0072cf", swatchClass: "bg-accent-base" },
      { token: "accent-wash", hex: "#e0f0ff", swatchClass: "bg-accent-wash" },
    ],
  },
  {
    group: "Confidence tiers",
    swatches: [
      { token: "measured", hex: "#0da56a", swatchClass: "bg-measured" },
      { token: "derived", hex: "#6b4ff8", swatchClass: "bg-derived" },
      { token: "assumed", hex: "#d97706", swatchClass: "bg-assumed" },
      { token: "unmapped", hex: "#7a9fbf", swatchClass: "bg-unmapped" },
    ],
  },
  {
    group: "Semantic",
    swatches: [
      { token: "raster", hex: "#e85d3a", swatchClass: "bg-raster" },
      { token: "error", hex: "#c41e3a", swatchClass: "bg-error" },
    ],
  },
]

const TYPE_SCALE = [
  {
    role: "Display",
    spec: "text-4xl semibold",
    className: "text-4xl font-semibold text-ink-900",
    sample: "Panel E-102 takeoff",
  },
  {
    role: "Heading",
    spec: "text-2xl semibold",
    className: "text-2xl font-semibold text-ink-900",
    sample: "Feeder route summary",
  },
  {
    role: "Subheading",
    spec: "text-base medium",
    className: "text-base font-medium text-ink-700",
    sample: "Circuit allocation by zone",
  },
  {
    role: "Body",
    spec: "text-sm regular",
    className: "text-sm text-ink-700",
    sample: "Every quantity traces back to a deterministic geometry calculation.",
  },
  {
    role: "Caption",
    spec: "text-xs regular",
    className: "text-xs text-ink-500",
    sample: "Source: MMC-JVC-CD-ELEC-3902 · layer E-CIRC-NEW",
  },
]

const QUANTITY_SAMPLES = ["1,284.50m", "999.99m", "12,400.00m"]

const SHADOW_LEVELS = [
  { label: "shadow-sm", usage: "Cards, sticky headers", className: "shadow-sm" },
  { label: "shadow-md", usage: "Popovers, dropdown menus", className: "shadow-md" },
  { label: "shadow-lg", usage: "Modals, command palettes", className: "shadow-lg" },
]

const BUTTON_VARIANTS = [
  { variant: "default", label: "Primary" },
  { variant: "secondary", label: "Secondary" },
  { variant: "outline", label: "Outline" },
  { variant: "ghost", label: "Ghost" },
  { variant: "destructive", label: "Destructive" },
  { variant: "link", label: "Link" },
] as const

const BUTTON_SIZES = [
  { size: "xs", label: "Extra small" },
  { size: "sm", label: "Small" },
  { size: "default", label: "Medium" },
  { size: "lg", label: "Large" },
] as const

const BADGE_VARIANTS = [
  { variant: "default", label: "Default" },
  { variant: "secondary", label: "Secondary" },
  { variant: "outline", label: "Outline" },
  { variant: "destructive", label: "Destructive" },
] as const

const BADGE_COMBOS: { quality: SourceQuality; showLabel: boolean }[] = [
  { quality: "layered_vector", showLabel: false },
  { quality: "layered_vector", showLabel: true },
  { quality: "raster", showLabel: false },
  { quality: "raster", showLabel: true },
]

function comboHeading(combo: { quality: SourceQuality; showLabel: boolean }): string {
  const quality = combo.quality === "raster" ? "Raster" : "Layered vector"
  return `${quality} · ${combo.showLabel ? "with label" : "symbol only"}`
}

function Section({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-ink-900">{title}</h2>
        {note && <p className="mt-0.5 max-w-2xl text-sm text-ink-500">{note}</p>}
      </div>
      {children}
    </section>
  )
}

export default function DesignSystemPage() {
  return (
    <AppShell right={<Badge variant="outline">Dev reference</Badge>}>
      <div className="mx-auto w-full max-w-5xl px-4 py-8">
        <PageHeader
          title="Design system"
          description="Technical Daylight reference surface — tokens, typography, and primitives. Dev-only route; not part of production navigation."
        />

        <div className="space-y-12">
          <Section
            title="Colors"
            note="Extended palette mirroring tokens.css. Components must never hardcode hex values — consume the utility class shown beneath each swatch."
          >
            <div className="space-y-6">
              {COLOR_GROUPS.map((group) => (
                <div key={group.group}>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-500">
                    {group.group}
                  </p>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-5 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
                    {group.swatches.map((swatch) => (
                      <div key={swatch.token}>
                        <div
                          aria-hidden
                          className={cn("h-14 rounded-lg border border-border", swatch.swatchClass)}
                        />
                        <p className="mt-1.5 font-mono text-xs font-medium text-ink-700">
                          {swatch.token}
                        </p>
                        <p className="font-mono text-[11px] uppercase tracking-wide text-ink-300">
                          {swatch.hex}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Section>

          <Section
            title="Typography"
            note="Geist Sans for prose and headings; Geist Mono with tabular-nums for every BOQ number, right-aligned so decimals align."
          >
            <div className="space-y-1 rounded-xl border border-border bg-surface p-6">
              {TYPE_SCALE.map((row) => (
                <div key={row.role} className="flex items-baseline justify-between gap-6 py-2">
                  <span className="w-44 shrink-0 font-mono text-xs text-ink-500">
                    {row.role} · {row.spec}
                  </span>
                  <span className={cn("min-w-0 truncate", row.className)}>{row.sample}</span>
                </div>
              ))}
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-border bg-surface p-6">
                <p className="font-mono text-xs text-ink-500">Geist Sans · proportional figures</p>
                <div className="mt-3 space-y-1 text-right text-sm text-ink-700">
                  {QUANTITY_SAMPLES.map((quantity) => (
                    <div key={quantity}>{quantity}</div>
                  ))}
                </div>
                <p className="mt-3 text-xs text-error">Digits drift — never use for BOQ numbers.</p>
              </div>
              <div className="rounded-xl border border-border bg-surface p-6">
                <p className="font-mono text-xs text-ink-500">Geist Mono · tabular-nums</p>
                <div className="mt-3 space-y-1 text-right font-mono text-sm tabular-nums text-ink-900">
                  {QUANTITY_SAMPLES.map((quantity) => (
                    <div key={quantity}>{quantity}</div>
                  ))}
                </div>
                <p className="mt-3 text-xs text-measured">Decimals align down the right edge.</p>
              </div>
            </div>

            <div className="rounded-xl border border-border bg-surface p-4">
              <p className="mb-3 text-xs font-medium uppercase tracking-wide text-ink-500">
                BOQ line pattern
              </p>
              <div className="flex items-center justify-between gap-4 py-1">
                <span className="text-sm text-ink-700">EMT conduit, 25 mm · route C-12</span>
                <span className="font-mono text-sm tabular-nums text-ink-900">1,284.50m</span>
              </div>
              <div className="flex items-center justify-between gap-4 border-t border-border pt-1">
                <span className="text-sm text-ink-500">Cable tray, 300 mm · route C-13</span>
                <span className="font-mono text-sm tabular-nums text-ink-900">999.99m</span>
              </div>
            </div>
          </Section>

          <Section
            title="Shadows"
            note="Three elevation levels only (spec §1.4). Cards sit on canvas so each level reads clearly."
          >
            <div className="grid gap-4 sm:grid-cols-3">
              {SHADOW_LEVELS.map((level) => (
                <div key={level.label} className={cn("rounded-xl bg-surface p-6", level.className)}>
                  <p className="font-mono text-xs font-medium text-ink-700">{level.label}</p>
                  <p className="mt-1 text-xs text-ink-500">{level.usage}</p>
                </div>
              ))}
            </div>
          </Section>

          <Section
            title="Components"
            note="shadcn primitives styled by the Technical Daylight theme."
          >
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-4 rounded-xl border border-border bg-surface p-6">
                <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Buttons</p>
                <div className="flex flex-wrap items-center gap-2">
                  {BUTTON_VARIANTS.map((item) => (
                    <Button key={item.variant} variant={item.variant}>
                      {item.label}
                    </Button>
                  ))}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {BUTTON_SIZES.map((item) => (
                    <Button key={item.size} size={item.size}>
                      {item.label}
                    </Button>
                  ))}
                  <Button variant="outline" size="icon-sm" aria-label="Add rule">
                    <Plus />
                  </Button>
                  <Button disabled>Disabled</Button>
                </div>
              </div>

              <div className="space-y-4 rounded-xl border border-border bg-surface p-6">
                <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Badges</p>
                <div className="flex flex-wrap items-center gap-2">
                  {BADGE_VARIANTS.map((item) => (
                    <Badge key={item.variant} variant={item.variant}>
                      {item.label}
                    </Badge>
                  ))}
                </div>
                <p className="text-xs font-medium uppercase tracking-wide text-ink-500">Tooltip</p>
                <TooltipProvider delayDuration={200}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button variant="outline">
                        <Info />
                        Rule info
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>Derived quantities resolve through assembly YAML in data/assemblies/.</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>

              <Card className="max-w-md">
                <CardHeader>
                  <CardTitle>Assembly rule · ASY-EMT-25</CardTitle>
                  <CardDescription>
                    EMT conduit 25 mm — measured length × 1.04 waste factor
                  </CardDescription>
                  <CardAction>
                    <Badge variant="secondary">v3</Badge>
                  </CardAction>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Source layers</span>
                    <span className="font-mono tabular-nums">E-CIRC-NEW</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Unit price</span>
                    <span className="font-mono tabular-nums">12.40 AED/m</span>
                  </div>
                </CardContent>
                <CardFooter className="justify-between">
                  <ConfidenceBadge status="DERIVED" sourceQuality="layered_vector" showLabel />
                  <Button size="sm" variant="outline">
                    View rule
                  </Button>
                </CardFooter>
              </Card>

              <div className="max-w-md rounded-xl border border-border bg-surface p-6">
                <p className="mb-4 text-xs font-medium uppercase tracking-wide text-ink-500">
                  Skeleton
                </p>
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <Skeleton className="size-10 rounded-full" />
                    <div className="space-y-2">
                      <Skeleton className="h-4 w-40" />
                      <Skeleton className="h-3 w-24" />
                    </div>
                  </div>
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-4/5" />
                  <Skeleton className="h-4 w-2/3" />
                </div>
              </div>
            </div>
          </Section>

          <Section
            title="Confidence badges"
            note="All four tiers × layered_vector / raster × symbol-only and labeled variants. Hover any badge for its tooltip."
          >
            <div className="overflow-x-auto rounded-xl border border-border bg-surface">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th scope="col" className="px-4 py-3 font-medium text-ink-500">
                      Tier
                    </th>
                    {BADGE_COMBOS.map((combo) => (
                      <th
                        key={comboHeading(combo)}
                        scope="col"
                        className="px-4 py-3 font-medium text-ink-500"
                      >
                        {comboHeading(combo)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {TIER_ORDER.map((tier) => (
                    <tr key={tier} className="border-b border-border last:border-b-0">
                      <th
                        scope="row"
                        className="px-4 py-3 font-mono text-xs font-medium text-ink-700"
                      >
                        {tier}
                      </th>
                      {BADGE_COMBOS.map((combo) => (
                        <td
                          key={`${tier}-${combo.quality}-${String(combo.showLabel)}`}
                          className="px-4 py-3"
                        >
                          <ConfidenceBadge
                            status={tier}
                            sourceQuality={combo.quality}
                            showLabel={combo.showLabel}
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-ink-500">
              The terracotta [R] superscript appears only when sourceQuality is raster;
              degraded_vector renders identically to layered_vector at the badge level.
            </p>
          </Section>

          <Section
            title="States"
            note="Shared empty, error, and loading surfaces used across routes."
          >
            <div className="grid gap-4 md:grid-cols-2">
              <EmptyState
                icon={<FileText className="size-8" />}
                title="No drawings uploaded yet"
                description="Upload a vector PDF drawing to begin a takeoff."
                action={<Button size="sm">Upload drawing</Button>}
              />
              <ErrorState
                description="The takeoff engine returned HTTP 502 while processing sheet E-102."
                action={
                  <Button size="sm" variant="destructive">
                    <RotateCcw />
                    Retry
                  </Button>
                }
              />
            </div>
            <div className="flex items-center gap-4 rounded-xl border border-border bg-surface p-6">
              <LoadingSpinner />
              <div>
                <p className="text-sm font-medium text-ink-700">LoadingSpinner</p>
                <p className="text-xs text-ink-500">Inline indicator shown while data loads.</p>
              </div>
            </div>
          </Section>
        </div>
      </div>
    </AppShell>
  )
}
