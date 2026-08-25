import { cn } from "@/lib/utils"

export interface HazardStripeProps {
  className?: string
}

export function HazardStripe({ className }: HazardStripeProps) {
  return (
    <div
      aria-hidden="true"
      className={cn("h-3.5 w-full", className)}
      style={{
        backgroundImage:
          "repeating-linear-gradient(-45deg, var(--safety-amber) 0px, var(--safety-amber) 14px, var(--ink-black) 14px, var(--ink-black) 28px)",
      }}
    />
  )
}
