import { RealtimeDashboard } from "@/components/realtime-dashboard"
import { Suspense } from "react"

type Params = Promise<{ slug: string }>
type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>

export async function generateMetadata(props: {
  params: Params
  searchParams: SearchParams
}) {
  const params = await props.params
  const searchParams = await props.searchParams
  return {
    title: "Dashboard - Wildlife App",
    description: "Wildlife detection and monitoring dashboard",
  }
}

export default async function Page(props: {
  params: Params
  searchParams: SearchParams
}) {
  const params = await props.params
  const searchParams = await props.searchParams

  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-64">
        <p className="text-lg text-muted-foreground">Loading dashboard...</p>
      </div>
    }>
      <RealtimeDashboard />
    </Suspense>
  )
} 