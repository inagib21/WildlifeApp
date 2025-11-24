"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
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
    href: "/settings",
    icon: IconSettings,
  },
]

export function NavMain() {
  const pathname = usePathname()

  return (
    <nav className="grid gap-1 px-2 group-[[data-collapsed=true]]:justify-center group-[[data-collapsed=true]]:px-2">
      {items.map((item, index) => (
        <Link
          key={index}
          href={item.href}
          className={cn(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground",
            pathname === item.href ? "bg-accent" : "transparent"
          )}
        >
          <item.icon className="h-4 w-4" />
          <span>{item.title}</span>
        </Link>
      ))}
    </nav>
  )
}
