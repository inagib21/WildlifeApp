"use client"

import * as React from "react"
import { Detection } from "@/types/api"
import { getDetections, getDetectionsCount, getDetectionsChunked } from "@/lib/api"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import Image from "next/image"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogClose } from "@/components/ui/dialog"

const PAGE_SIZE = 12

export function DetectionsList() {
  const [detections, setDetections] = React.useState<Detection[]>([])
  const [totalCount, setTotalCount] = React.useState<number>(0)
  const [loading, setLoading] = React.useState(true)
  const [page, setPage] = React.useState(0)
  const [sortBy, setSortBy] = React.useState<'timestamp' | 'confidence' | 'species' | 'camera'>('timestamp')
  const [sortDir, setSortDir] = React.useState<'asc' | 'desc'>('desc')
  const [selectedDetection, setSelectedDetection] = React.useState<Detection | null>(null)

  React.useEffect(() => {
    setLoading(true)
    const fetchPage = async () => {
      const offset = page * PAGE_SIZE
      const data = await getDetectionsChunked(undefined, PAGE_SIZE + offset)
      setDetections(data.slice(offset, offset + PAGE_SIZE))
      const count = await getDetectionsCount()
      setTotalCount(count)
      setLoading(false)
    }
    fetchPage()
  }, [page])

  const pageCount = Math.ceil(totalCount / PAGE_SIZE)

  // Sort detections in-memory (for now)
  const sortedDetections = [...detections].sort((a, b) => {
    let aVal, bVal
    switch (sortBy) {
      case 'timestamp':
        aVal = new Date(a.timestamp).getTime(); bVal = new Date(b.timestamp).getTime(); break
      case 'confidence':
        aVal = a.confidence; bVal = b.confidence; break
      case 'species':
        aVal = a.species || ''; bVal = b.species || ''; break
      case 'camera':
        aVal = a.camera_name || a.camera_id; bVal = b.camera_name || b.camera_id; break
      default:
        aVal = 0; bVal = 0
    }
    if (aVal < bVal) return sortDir === 'asc' ? -1 : 1
    if (aVal > bVal) return sortDir === 'asc' ? 1 : -1
    return 0
  })

  const handleSort = (col: typeof sortBy) => {
    if (sortBy === col) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(col)
      setSortDir('desc')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading detections...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Detections</h1>
        <div className="text-sm text-muted-foreground">
          {totalCount} total detections | Page {page + 1} of {pageCount}
        </div>
      </div>
      <div className="rounded-md border overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Photo</TableHead>
              <TableHead className="cursor-pointer" onClick={() => handleSort('timestamp')}>
                Timestamp {sortBy === 'timestamp' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
              </TableHead>
              <TableHead className="cursor-pointer" onClick={() => handleSort('species')}>
                Species {sortBy === 'species' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
              </TableHead>
              <TableHead className="cursor-pointer" onClick={() => handleSort('confidence')}>
                Confidence {sortBy === 'confidence' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
              </TableHead>
              <TableHead className="cursor-pointer" onClick={() => handleSort('camera')}>
                Camera {sortBy === 'camera' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
              </TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedDetections.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center">No detections found.</TableCell>
              </TableRow>
            ) : (
              sortedDetections.map((detection) => {
                const validImageUrl = (detection.media_url && (detection.media_url.startsWith("/") || detection.media_url.startsWith("http"))) ? detection.media_url : "/file.svg"
                const commonName = detection.species && detection.species.includes(';') ? detection.species.split(';').pop()?.trim() : detection.species
                return (
                  <TableRow key={detection.id}>
                    <TableCell>
                      <div className="relative w-24 h-16 cursor-pointer" onClick={() => setSelectedDetection(detection)}>
                        <Image src={validImageUrl} alt={`Detection ${detection.id}`} fill className="object-cover rounded" />
                      </div>
                    </TableCell>
                    <TableCell>{new Date(detection.timestamp).toLocaleString()}</TableCell>
                    <TableCell>{commonName}</TableCell>
                    <TableCell><Badge>{Math.round(detection.confidence * 100)}%</Badge></TableCell>
                    <TableCell>{detection.camera_name || detection.camera_id}</TableCell>
                    <TableCell>
                      <a href={validImageUrl} target="_blank" rel="noopener noreferrer">
                        <Button size="sm" variant="outline">View</Button>
                      </a>
                    </TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-between mt-2">
        <Button onClick={() => setPage(0)} disabled={page === 0} size="sm">First</Button>
        <Button onClick={() => setPage(page - 1)} disabled={page === 0} size="sm">Previous</Button>
        <span>Page {page + 1} of {pageCount}</span>
        <Button onClick={() => setPage(page + 1)} disabled={page + 1 >= pageCount} size="sm">Next</Button>
        <Button onClick={() => setPage(pageCount - 1)} disabled={page + 1 >= pageCount} size="sm">Last</Button>
      </div>

      {/* Photo detail modal */}
      <Dialog open={!!selectedDetection} onOpenChange={() => setSelectedDetection(null)}>
        <DialogContent className="max-w-lg">
          {selectedDetection && (
            <>
              <DialogHeader>
                <DialogTitle>Detection #{selectedDetection.id}</DialogTitle>
                <DialogDescription>
                  <div className="mb-2">{new Date(selectedDetection.timestamp).toLocaleString()}</div>
                </DialogDescription>
              </DialogHeader>
              <div className="relative w-full h-64 mb-4">
                <Image src={(selectedDetection.media_url && (selectedDetection.media_url.startsWith("/") || selectedDetection.media_url.startsWith("http"))) ? selectedDetection.media_url : "/file.svg"} alt={`Detection ${selectedDetection.id}`} fill className="object-contain rounded" />
              </div>
              <div className="space-y-2 text-sm">
                <div><b>Species:</b> {selectedDetection.species}</div>
                <div><b>Confidence:</b> {Math.round(selectedDetection.confidence * 100)}%</div>
                <div><b>Camera:</b> {selectedDetection.camera_name || selectedDetection.camera_id}</div>
                <div><b>File size:</b> {selectedDetection.file_size ? `${selectedDetection.file_size} bytes` : 'N/A'}</div>
                <div><b>Dimensions:</b> {selectedDetection.image_width && selectedDetection.image_height ? `${selectedDetection.image_width}x${selectedDetection.image_height}` : 'N/A'}</div>
                <div><b>Image path:</b> {selectedDetection.image_path}</div>
              </div>
              <div className="flex justify-end mt-4">
                <DialogClose asChild>
                  <Button variant="outline">Close</Button>
                </DialogClose>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
} 