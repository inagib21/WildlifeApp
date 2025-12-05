"use client"

import { useAppShortcuts } from "@/hooks/use-keyboard-shortcuts"

export function KeyboardShortcutsProvider({ children }: { children: React.ReactNode }) {
  useAppShortcuts()
  return <>{children}</>
}

