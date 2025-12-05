"use client"

import { useEffect, useRef } from "react"
import { useRouter } from "next/navigation"
import { toast } from "sonner"

interface Shortcut {
  key: string
  ctrl?: boolean
  shift?: boolean
  alt?: boolean
  doubleKey?: boolean // For double-key sequences like "gg", "dd"
  action: () => void
  description: string
  category?: string
}

// Track last key press for double-key sequences
let lastKeyPress: { key: string; timestamp: number } | null = null
const DOUBLE_KEY_TIMEOUT = 500 // 500ms window for double-key sequences

export function useKeyboardShortcuts(shortcuts: Shortcut[]) {
  const router = useRouter()
  const shortcutsRef = useRef(shortcuts)
  shortcutsRef.current = shortcuts

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger shortcuts when typing in inputs, textareas, or contenteditable elements
      const target = e.target as HTMLElement
      
      // More robust check - also check if we're inside an input/textarea/contenteditable
      // This prevents shortcuts from firing when user is typing in search boxes or other inputs
      const isInputElement = 
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable ||
        target.closest("input") !== null ||
        target.closest("textarea") !== null ||
        target.closest("[contenteditable='true']") !== null ||
        target.closest("[contenteditable]") !== null ||
        (target as HTMLInputElement).type === "text" ||
        (target as HTMLInputElement).type === "search" ||
        (target as HTMLInputElement).type === "email" ||
        (target as HTMLInputElement).type === "password" ||
        (target as HTMLInputElement).type === "number" ||
        target.getAttribute("role") === "textbox"
      
      // Also check if any modifier keys are pressed - if so, allow shortcuts (e.g., Ctrl+K)
      const hasModifier = e.ctrlKey || e.metaKey || e.altKey
      
      // If typing in an input and no modifier keys, don't trigger shortcuts
      if (isInputElement && !hasModifier) {
        return
      }

      const currentKey = e.key.toLowerCase()
      const now = Date.now()

      // Check for double-key sequences
      if (lastKeyPress && 
          lastKeyPress.key === currentKey && 
          (now - lastKeyPress.timestamp) < DOUBLE_KEY_TIMEOUT) {
        // This is a double-key press
        shortcutsRef.current.forEach((shortcut) => {
          if (shortcut.doubleKey && shortcut.key.toLowerCase() === currentKey) {
            const ctrlMatch = shortcut.ctrl ? e.ctrlKey || e.metaKey : !e.ctrlKey && !e.metaKey
            const shiftMatch = shortcut.shift ? e.shiftKey : !e.shiftKey
            const altMatch = shortcut.alt ? e.altKey : !e.altKey

            if (ctrlMatch && shiftMatch && altMatch) {
              e.preventDefault()
              shortcut.action()
              lastKeyPress = null // Reset after action
              return
            }
          }
        })
        lastKeyPress = null // Reset after checking
        return
      }

      // Update last key press for double-key detection
      lastKeyPress = { key: currentKey, timestamp: now }

      // Check regular shortcuts
      shortcutsRef.current.forEach((shortcut) => {
        // Skip double-key shortcuts in regular check
        if (shortcut.doubleKey) {
          return
        }

        const keyMatch = currentKey === shortcut.key.toLowerCase()
        const ctrlMatch = shortcut.ctrl ? e.ctrlKey || e.metaKey : !e.ctrlKey && !e.metaKey
        const shiftMatch = shortcut.shift ? e.shiftKey : !e.shiftKey
        const altMatch = shortcut.alt ? e.altKey : !e.altKey

        if (keyMatch && ctrlMatch && shiftMatch && altMatch) {
          e.preventDefault()
          shortcut.action()
        }
      })
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [])
}

// Common shortcuts for the app
export function useAppShortcuts() {
  const router = useRouter()

  useKeyboardShortcuts([
    {
      key: "k",
      ctrl: true,
      action: () => {
        // Focus search (if available)
        const searchInput = document.querySelector('input[type="text"][placeholder*="Search"]') as HTMLInputElement
        if (searchInput) {
          searchInput.focus()
          searchInput.select()
        }
      },
      description: "Focus search",
      category: "Search"
    },
    {
      key: "d",
      doubleKey: true,
      action: () => router.push("/detections"),
      description: "Go to Detections (double-press D)",
      category: "Navigation"
    },
    {
      key: "c",
      doubleKey: true,
      action: () => router.push("/cameras"),
      description: "Go to Cameras (double-press C)",
      category: "Navigation"
    },
    {
      key: "a",
      doubleKey: true,
      action: () => router.push("/analytics"),
      description: "Go to Analytics (double-press A)",
      category: "Navigation"
    },
    {
      key: "g",
      doubleKey: true,
      action: () => router.push("/dashboard"),
      description: "Go to Dashboard (double-press G)",
      category: "Navigation"
    },
    {
      key: "?",
      shift: true,
      action: () => {
        const shortcuts = [
          "Navigation: DD (Detections), CC (Cameras), AA (Analytics), GG (Dashboard)",
          "Search: Ctrl+K (Focus search)",
          "General: Ctrl+R (Refresh), B (Back), F (Forward)",
          "Help: Shift+? (Show this help), Ctrl+Shift+? (Full docs)"
        ]
        toast.info("Keyboard Shortcuts", {
          description: shortcuts.join("\n"),
          duration: 8000
        })
      },
      description: "Show shortcuts help",
      category: "Help"
    },
    {
      key: "?",
      ctrl: true,
      shift: true,
      action: () => {
        // Open keyboard shortcuts documentation
        window.open("/KEYBOARD_SHORTCUTS.md", "_blank")
      },
      description: "Open keyboard shortcuts documentation",
      category: "Help"
    },
    {
      key: "r",
      ctrl: true,
      action: () => {
        // Refresh current page
        window.location.reload()
      },
      description: "Refresh page",
      category: "General"
    },
    {
      key: "b",
      action: () => {
        // Go back in browser history
        window.history.back()
      },
      description: "Go back",
      category: "Navigation"
    },
    {
      key: "f",
      action: () => {
        // Go forward in browser history
        window.history.forward()
      },
      description: "Go forward",
      category: "Navigation"
    }
  ])
}
