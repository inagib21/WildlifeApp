import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { Toaster } from "sonner"
import { ThemeProvider } from "@/components/theme-provider"
import { SidebarProvider } from "@/components/ui/sidebar"
import { NavMain } from "@/components/nav-main"
import { NavSecondary } from "@/components/nav-secondary"
import { NavUser } from "@/components/nav-user"
import { ThemeToggle } from "@/components/theme-toggle"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "Wildlife Camera System",
  description: "A system for managing wildlife cameras and detecting animals",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
          storageKey="wildlife-theme"
        >
          <SidebarProvider>
            <div className="flex min-h-screen">
              <div className="w-64 border-r bg-background">
                <div className="flex h-full flex-col gap-2 p-4">
                  <div className="flex items-center justify-between mb-4">
                    <h1 className="text-xl font-bold">Wildlife</h1>
                    <ThemeToggle />
                  </div>
                  <NavMain />
                  <div className="mt-auto space-y-4">
                    <NavSecondary />
                    <NavUser
                      user={{
                        name: "Admin User",
                        email: "admin@example.com",
                        avatar: "/avatars/01.png"
                      }}
                    />
                  </div>
                </div>
              </div>
              <div className="flex-1">
                <main className="p-6">
                  {children}
                </main>
              </div>
            </div>
            <Toaster />
          </SidebarProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
