"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ThemeProvider } from "next-themes"
import { useState } from "react"
import type { ReactNode } from "react"
import { TooltipProvider } from "@/components/ui/tooltip"

export default function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 2,
            refetchOnWindowFocus: false,
          },
        },
      }),
  )
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider delayDuration={200}>{children}</TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
