"use client"

import { Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"

import { Button } from "@/components/ui/button"

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const isDark = resolvedTheme === "dark"
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label="Toggle theme"
      title="Toggle theme"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className="text-paper/70 hover:bg-white/10 hover:text-paper"
    >
      <Moon className="size-4 dark:hidden" />
      <Sun className="hidden size-4 dark:block" />
    </Button>
  )
}
