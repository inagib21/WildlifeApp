"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { formatDistanceToNow, format } from "date-fns"
import Image from "next/image"

interface DetectionCardProps {
  id: number
  timestamp: string
  species: string
  confidence: number
  imageUrl: string
  cameraName: string
}

export function DetectionCard({
  id,
  timestamp,
  species,
  confidence,
  imageUrl,
  cameraName,
}: DetectionCardProps) {
  const timeAgo = formatDistanceToNow(new Date(timestamp), { addSuffix: true })
  const formattedDate = format(new Date(timestamp), "yyyy-MM-dd h:mm:ss a")
  const confidencePercentage = Math.round(confidence * 100)

  return (
    <Card className="overflow-hidden">
      <CardHeader className="p-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Detection #{id}</CardTitle>
          <Badge variant="secondary">
            {formattedDate}
          </Badge>
        </div>
        <div className="text-sm text-muted-foreground">
          Camera: {cameraName}
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="relative aspect-video">
          <Image
            src={imageUrl}
            alt={`Detection ${id}`}
            fill
            className="object-cover"
          />
        </div>
        <div className="p-4 space-y-2">
          <div className="flex items-center justify-between">
            <div className="font-medium">{species}</div>
            <Badge variant={confidencePercentage > 80 ? "default" : "secondary"}>
              {confidencePercentage}% confidence
            </Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  )
} 