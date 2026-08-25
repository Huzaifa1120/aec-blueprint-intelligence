import { cn } from "@/lib/utils"

export interface GoggleLineDividerProps {
  className?: string
}

export function GoggleLineDivider({ className }: GoggleLineDividerProps) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 120 12"
      preserveAspectRatio="none"
      className={cn("h-3 w-full text-safety-amber", className)}
      fill="none"
    >
      <path
        d="M4 8C14 2 34 2 46 7C54 11 66 11 74 7C86 2 106 2 116 8"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}
