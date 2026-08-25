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
import { GoggleLineDivider } from "@/components/ui/GoggleLineDivider"
import { HazardStripe } from "@/components/ui/HazardStripe"
import { ProtocolCard } from "@/components/ui/ProtocolCard"
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
    group: "Core palette",
    swatches: [
      { token: "ink-black", hex: "#12130f", swatchClass: "bg-ink-black" },
      { token: "safety-amber", hex: "#f5a623", swatchClass: "bg-safety-amber" },
      { token: "guard-green", hex: "#1f7a53", swatchClass: "bg-guard-green" },
      { token: "paper", hex: "#faf9f5", swatchClass: "bg-paper border border-outline-variant" },
      { token: "steel", hex: "#5b6660", swatchClass: "bg-steel" },
      { token: "hazard-red", hex: "#c43b2e", swatchClass: "bg-hazard-red" },
    ],
  },
  {
    group: "Extended palette",
    swatches: [
      { token: "surface-dim", hex: "#dbdad6", swatchClass: "bg-surface-dim" },
      { token: "surface-container", hex: "#efeeea", swatchClass: "bg-surface-container" },
      { token: "surface-high", hex: "#e9e8e4", swatchClass: "bg-surface-high" },
      { token: "outline", hex: "#777870", swatchClass: "bg-outline" },
      { token: "outline-variant", hex: "#c7c7bf", swatchClass: "bg-outline-variant" },
      { token: "green-tint", hex: "#e7f2ec", swatchClass: "bg-green-tint" },
    ],
  },
  {
    group: "Confidence tiers",
    swatches: [
      { token: "measured → guard", hex: "#1f7a53", swatchClass: "bg-measured" },
      { token: "derived → amber", hex: "#f5a623", swatchClass: "bg-derived" },
      { token: "assumed → hazard", hex: "#c43b2e", swatchClass: "bg-assumed" },
      { token: "unmapped → outline", hex: "#777870", swatchClass: "bg-unmapped" },
    ],
  },
]

const TYPE_SCALE = [
  {
    role: "Headline XL",
    spec: "Archivo Black · 52px · -0.01em",
    className:
      "font-heading text-[38px] leading-[40px] tracking-[-0.01em] text-ink-black md:text-[52px] md:leading-[54px]",
    sample: "Sheet E-102 takeoff",
  },
  {
    role: "Headline LG",
    spec: "Archivo Black · 32px",
    className: "font-heading text-[32px] leading-[36px] tracking-[-0.01em] text-ink-black",
    sample: "Feeder route summary",
  },
  {
    role: "Headline SM",
    spec: "Archivo Black · 17px",
    className: "font-heading text-[17px] leading-[22px] text-ink-black",
    sample: "Circuit allocation by zone",
  },
  {
    role: "Body LG",
    spec: "Inter · 18px",
    className: "text-[18px] leading-[28px] text-ink-black",
    sample: "Every quantity traces back to a deterministic geometry calculation.",
  },
  {
    role: "Body MD",
    spec: "Inter · 14px",
    className: "text-sm leading-[22px] text-ink-black",
    sample: "Review each row before it becomes an estimate.",
  },
  {
    role: "Label mono",
    spec: "IBM Plex Mono · 12px · 0.08em caps",
    className: "label-mono text-steel",
    sample: "Quality check",
  },
  {
    role: "Data mono",
    spec: "IBM Plex Mono · 13px",
    className: "font-mono text-[13px] leading-[26px] tabular-nums text-ink-black",
    sample: "12,400.00 m",
  },
]

const QUANTITY_SAMPLES = ["1,284.50m", "999.99m", "12,400.00m"]

const SHADOW_LEVELS = [
  {
    label: "Flat + border",
    usage: "Default state — Steel outlines carry depth (§5)",
    className: "border border-steel",
  },
  {
    label: "Hover elevation",
    usage: "Service-card hover — subtle lift",
    className: "border border-steel shadow-md",
  },
  {
    label: "Heavy drop-shadow",
    usage: "Large visuals and modals only — 0 12px 24px rgba(0,0,0,.4)",
    className: "shadow-lg",
  },
]

const BUTTON_VARIANTS = [
  { variant: "default", label: "Primary" },
  { variant: "outline", label: "Outline" },
  { variant: "secondary", label: "Secondary" },
  { variant: "ghost", label: "Ghost" },
  { variant: "destructive", label: "Danger" },
  { variant: "link", label: "Link" },
] as const

const BUTTON_SIZES = [
  { size: "xs", label: "Extra small" },
  { size: "sm", label: "Small" },
  { size: "default", label: "Medium" },
  { size: "lg", label: "Large" },
] as const

const BADGE_VARIANTS = [
  { variant: "default", label: "Certified chip" },
  { variant: "secondary", label: "Secondary" },
  { variant: "outline", label: "Outline" },
  { variant: "destructive", label: "Hazard" },
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
        <h2 className="font-heading text-[17px] leading-[22px] text-ink-black">{title}</h2>
        <GoggleLineDivider className="mt-1.5 w-24" />
        {note && <p className="mt-2 max-w-2xl text-sm text-steel">{note}</p>}
      </div>
      {children}
    </section>
  )
}

export default function DesignSystemPage() {
  return (
    <AppShell right={<Badge variant="outline">Dev reference</Badge>}>
      <div className="mx-auto w-full max-w-5xl px-4 py-10">
        <PageHeader
          eyebrow="Huzaifa AEC · Design System"
          title="The Safety Authority"
          description="Reference surface for docs/DESIGN.md — the avant-garde technical-manual world: Ink Black authority on Paper, Safety Amber action, IBM Plex Mono data. Dev-only route."
        />

        <div className="space-y-12">
          <Section
            title="Colors"
            note="docs/DESIGN.md §2 mirrored to tokens.css. Components must never hardcode hex values — consume the utility class shown beneath each swatch."
          >
            <div className="space-y-6">
              {COLOR_GROUPS.map((group) => (
                <div key={group.group}>
                  <p className="label-mono mb-2 text-steel">{group.group}</p>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-5 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
                    {group.swatches.map((swatch) => (
                      <div key={swatch.token}>
                        <div
                          aria-hidden
                          className={cn(
                            "h-14 rounded-lg border border-outline-variant",
                            swatch.swatchClass,
                          )}
                        />
                        <p className="mt-1.5 font-mono text-xs font-medium text-ink-black">
                          {swatch.token}
                        </p>
                        <p className="font-mono text-[11px] tracking-[0.08em] text-steel uppercase">
                          {swatch.hex}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <ul className="space-y-1 rounded-lg border border-outline-variant bg-surface-container p-4 text-sm">
              <li>
                <strong className="font-medium">Primary buttons:</strong> Safety Amber on Ink Black
              </li>
              <li>
                <strong className="font-medium">Guard Green:</strong> reassurance indicators only —
                never buttons
              </li>
              <li>
                <strong className="font-medium">Hazard Red:</strong> emergency only
              </li>
              <li>
                <strong className="font-medium">Paper:</strong> default page background ·{" "}
                <strong className="font-medium">Ink Black:</strong> heroes, protocol cards, footer
              </li>
            </ul>
          </Section>

          <Section
            title="Typography"
            note="DESIGN.md §3 — Archivo Black headlines (sentence case), Inter UI text, IBM Plex Mono with tabular figures for every BOQ number, right-aligned so decimals align."
          >
            <div className="space-y-1 rounded-2xl border border-steel bg-paper p-6">
              {TYPE_SCALE.map((row) => (
                <div key={row.role} className="flex items-baseline justify-between gap-6 py-2">
                  <span className="w-56 shrink-0 font-mono text-xs text-steel">{row.spec}</span>
                  <span className={cn("min-w-0 truncate", row.className)}>{row.sample}</span>
                </div>
              ))}
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-2xl border border-steel bg-paper p-6">
                <p className="label-mono text-steel">Inter · proportional figures</p>
                <div className="mt-3 space-y-1 text-right text-sm text-ink-black">
                  {QUANTITY_SAMPLES.map((quantity) => (
                    <div key={quantity}>{quantity}</div>
                  ))}
                </div>
                <p className="mt-3 text-xs text-error">Digits drift — never use for BOQ numbers.</p>
              </div>
              <div className="rounded-2xl border border-steel bg-paper p-6">
                <p className="label-mono text-steel">IBM Plex Mono · tabular-nums</p>
                <div className="mt-3 space-y-1 text-right font-mono text-sm tabular-nums text-ink-black">
                  {QUANTITY_SAMPLES.map((quantity) => (
                    <div key={quantity}>{quantity}</div>
                  ))}
                </div>
                <p className="mt-3 text-xs text-success">Decimals align down the right edge.</p>
              </div>
            </div>

            <div className="rounded-2xl border border-steel bg-paper p-4">
              <p className="label-mono mb-3 text-steel">BOQ line pattern</p>
              <div className="flex items-center justify-between gap-4 py-1">
                <span className="text-sm text-ink-black">EMT conduit, 25 mm · route C-12</span>
                <span className="font-mono text-sm tabular-nums text-ink-black">1,284.50m</span>
              </div>
              <div className="flex items-center justify-between gap-4 border-t border-outline-variant pt-1">
                <span className="text-sm text-steel">Cable tray, 300 mm · route C-13</span>
                <span className="font-mono text-sm tabular-nums text-ink-black">999.99m</span>
              </div>
            </div>
          </Section>

          <Section
            title="Elevation & shape"
            note="DESIGN.md §5–6 — color blocking and low-contrast Steel outlines carry depth; the heavy drop-shadow belongs to large visuals only. Buttons 4px max, cards 6–8px, chips pill."
          >
            <div className="grid gap-4 sm:grid-cols-3">
              {SHADOW_LEVELS.map((level) => (
                <div key={level.label} className={cn("rounded-xl bg-paper p-6", level.className)}>
                  <p className="font-mono text-xs font-medium text-ink-black">{level.label}</p>
                  <p className="mt-1 text-xs text-steel">{level.usage}</p>
                </div>
              ))}
            </div>
          </Section>

          <Section
            title="Signature components"
            note="DESIGN.md §7 — the goggle line divider, protocol card, service card, and certification chip."
          >
            <div className="space-y-4 rounded-2xl border border-steel bg-paper p-6">
              <p className="label-mono text-steel">Goggle line divider</p>
              <GoggleLineDivider className="max-w-md" />
              <p className="label-mono text-steel">Hazard stripe</p>
              <HazardStripe className="rounded-sm" />
              <p className="text-xs text-steel">
                Page-edge tape — bookends every Ink Black header, hero, and footer (§5 hazard
                overlays).
              </p>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <ProtocolCard
                title="Route C-12 · conduit run"
                rows={[
                  { label: "measured_length", value: "1,284.50 m" },
                  { label: "waste_factor", value: "×1.04" },
                  { label: "tier", value: "DERIVED", valueTone: "verified" },
                ]}
                footer={
                  <span className="text-xs text-guard-green">Rule ASY-EMT-25 · verified</span>
                }
              />

              <Card className="max-w-md">
                <CardHeader>
                  <CardTitle>Assembly rule · ASY-EMT-25</CardTitle>
                  <CardDescription>
                    EMT conduit 25 mm — measured length × 1.04 waste factor
                  </CardDescription>
                  <CardAction>
                    <Badge variant="default">v3</Badge>
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
            </div>
          </Section>

          <Section title="Components" note="shadcn primitives styled by the DESIGN.md theme.">
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-4 rounded-2xl border border-steel bg-paper p-6">
                <p className="label-mono text-steel">Buttons</p>
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

              <div className="space-y-4 rounded-2xl border border-steel bg-paper p-6">
                <p className="label-mono text-steel">Badges & tooltip</p>
                <div className="flex flex-wrap items-center gap-2">
                  {BADGE_VARIANTS.map((item) => (
                    <Badge key={item.variant} variant={item.variant}>
                      {item.label}
                    </Badge>
                  ))}
                </div>
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

              <div className="max-w-md rounded-2xl border border-steel bg-paper p-6">
                <p className="label-mono mb-4 text-steel">Skeleton</p>
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
            note="Hard product rule — Guard Green MEASURED · Safety Amber DERIVED · Hazard Red ASSUMED · Outline UNMAPPED, three redundant signals each. Hover any badge for its tooltip."
          >
            <div className="overflow-x-auto rounded-2xl border border-steel bg-paper">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead>
                  <tr className="border-b border-outline-variant">
                    <th scope="col" className="px-4 py-3 font-medium text-steel">
                      Tier
                    </th>
                    {BADGE_COMBOS.map((combo) => (
                      <th
                        key={comboHeading(combo)}
                        scope="col"
                        className="px-4 py-3 font-medium text-steel"
                      >
                        {comboHeading(combo)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {TIER_ORDER.map((tier) => (
                    <tr key={tier} className="border-b border-outline-variant last:border-b-0">
                      <th
                        scope="row"
                        className="px-4 py-3 font-mono text-xs font-medium text-ink-black"
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
            <p className="text-xs text-steel">
              The mono [R] superscript appears only when sourceQuality is raster; degraded_vector
              renders identically to layered_vector at the badge level.
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
            <div className="flex items-center gap-4 rounded-2xl border border-steel bg-paper p-6">
              <LoadingSpinner />
              <div>
                <p className="text-sm font-medium text-ink-black">LoadingSpinner</p>
                <p className="text-xs text-steel">Inline indicator shown while data loads.</p>
              </div>
            </div>
          </Section>
        </div>
      </div>
    </AppShell>
  )
}
