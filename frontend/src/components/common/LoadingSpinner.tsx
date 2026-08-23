import { LoaderCircle } from "lucide-react"
import { cn } from "@/lib/utils"

export interface LoadingSpinnerProps {
  className?: string
}

export function LoadingSpinner({ className }: LoadingSpinnerProps) {
  return (
    <span role="status" aria-label="Loading" className={cn("inline-flex text-primary", className)}>
      <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
    </span>
  )
}
