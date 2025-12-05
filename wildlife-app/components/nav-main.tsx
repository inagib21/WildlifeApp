"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"
import { IconDashboard, IconCamera, IconAlertCircle, IconSettings, IconPlus, IconShield, IconFileText, IconChartBar } from "@tabler/icons-react"
import { cn } from "@/lib/utils"

const items = [
  {
    title: "Dashboard",
    href: "/dashboard",
    icon: IconDashboard,
  },
  {
    title: "Cameras",
    href: "/cameras",
    icon: IconCamera,
  },
  {
    title: "Detections",
    href: "/detections",
    icon: IconAlertCircle,
  },
  {
    title: "Admin",
    href: "/admin",
    icon: IconShield,
  },
  {
    title: "Audit Logs",
    href: "/audit-logs",
    icon: IconFileText,
  },
  {
    title: "Analytics",
    href: "/analytics",
    icon: IconChartBar,
  },
  {
    title: "Settings",
    href: "/config",
    icon: IconSettings,
  },
]

export function NavMain() {
  const pathname = usePathname()
  const [mounted, setMounted] = useState(false)

  // Prevent hydration mismatch by only using pathname after mount
  useEffect(() => {
    setMounted(true)
  }, [])

  return (
    <nav className="grid gap-1 px-2 group-[[data-collapsed=true]]:justify-center group-[[data-collapsed=true]]:px-2">
      {items.map((item, index) => {
        // Only check pathname match after component is mounted to avoid hydration mismatch
        const isActive = mounted && pathname === item.href
        
        return (
          <Link
            key={index}
            href={item.href}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground transition-colors",
              isActive ? "bg-accent" : ""
            )}
          >
            <item.icon className="h-4 w-4" />
            <span>{item.title}</span>
          </Link>
        )
      })}
    </nav>
  )
}
