import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Camera, Detection } from "@/types/api"

interface SectionCardsProps {
  cameras: Camera[]
  detections: Detection[]
  totalDetectionsCount: number
  totalUniqueSpecies: number
}

export function SectionCards({ cameras, detections, totalDetectionsCount, totalUniqueSpecies }: SectionCardsProps) {
  const activeCameras = cameras.filter(camera => camera.is_active).length
  const systemHealth = activeCameras === cameras.length ? "Healthy" : "Warning"

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Active Cameras</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{activeCameras}</div>
          <p className="text-xs text-muted-foreground">
            {cameras.length} total cameras
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total Detections</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{totalDetectionsCount}</div>
          <p className="text-xs text-muted-foreground">
            All time
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Species Identified</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{totalUniqueSpecies}</div>
          <p className="text-xs text-muted-foreground">
            Unique species detected
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">System Health</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{systemHealth}</div>
          <p className="text-xs text-muted-foreground">
            {systemHealth === "Healthy" ? "All systems operational" : "Some cameras offline"}
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
