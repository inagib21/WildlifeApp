"use client"

import * as React from "react"
import { Detection } from "@/types/api"
import { getDetections, getDetectionsCount, getDetectionsChunked, exportDetections, ExportOptions, deleteDetection, bulkDeleteDetections } from "@/lib/api"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import Image from "next/image"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogClose } from "@/components/ui/dialog"
import { toast } from "sonner"
import { Download, Wifi, WifiOff } from "lucide-react"
import { useDetectionsRealtime } from "@/hooks/use-realtime"

// Utility function to generate media URL from image path
function generateMediaUrl(imagePath: string): string {
  if (!imagePath) return "/file.svg"
  
  try {
    // Normalize path for both Windows and Linux
    const path = imagePath.replace(/\\/g, "/")
    const parts = path.split("/")
    
    // Look for motioneye_media/CameraX/date/filename
    if (path.includes("motioneye_media")) {
      const idx = parts.indexOf("motioneye_media")
      if (parts.length > idx + 3) {
        const camera = parts[idx + 1]
        const date = parts[idx + 2]
        const filename = parts[idx + 3]
        return `/media/${camera}/${date}/${filename}`
      }
    }
    
    // Look for archived_photos/species/camera/date/filename
    if (path.includes("archived_photos")) {
      const idx = parts.indexOf("archived_photos")
      if (parts.length > idx + 4) {
        const species = parts[idx + 1]
        const camera = parts[idx + 2]
        const date = parts[idx + 3]
        const filename = parts[idx + 4]
        return `/archived_photos/${species}/${camera}/${date}/${filename}`
      }
    }
    
    return "/file.svg"
  } catch (error) {
    console.error("Error generating media URL:", error)
    return "/file.svg"
  }
}

const PAGE_SIZE = 12

export function DetectionsList() {
  const [detections, setDetections] = React.useState<Detection[]>([])
  const [totalCount, setTotalCount] = React.useState<number>(0)
  const [loading, setLoading] = React.useState(true)
  const [page, setPage] = React.useState(0)
  const [sortBy, setSortBy] = React.useState<'timestamp' | 'confidence' | 'species' | 'camera'>('timestamp')
  const [sortDir, setSortDir] = React.useState<'asc' | 'desc'>('desc')
  const [selectedDetection, setSelectedDetection] = React.useState<Detection | null>(null)
  const [searchQuery, setSearchQuery] = React.useState("")
  const [exporting, setExporting] = React.useState(false)
  const [selectedDetections, setSelectedDetections] = React.useState<Set<number>>(new Set())
  const [deleting, setDeleting] = React.useState(false)

  React.useEffect(() => {
    setLoading(true)
    const fetchPage = async () => {
      const offset = page * PAGE_SIZE
      const data = await getDetections({
        limit: PAGE_SIZE,
        offset: offset,
        search: searchQuery || undefined
      })
      setDetections(data)
      const count = await getDetectionsCount()
      setTotalCount(count)
      setLoading(false)
    }
    fetchPage()
  }, [page, searchQuery])

  // Subscribe to real-time detection updates via SSE using the hook
  const { isConnected: sseConnected, error: sseError } = useDetectionsRealtime((newDetection) => {
    // Handle new detection from SSE
    if (newDetection && newDetection.id) {
      // Add the new detection to the list if we're on the first page and it matches search
      if (page === 0) {
        // Check if detection matches search query
        const matchesSearch = !searchQuery || 
          newDetection.species?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          newDetection.camera_name?.toLowerCase().includes(searchQuery.toLowerCase())
        
        if (matchesSearch) {
          setDetections((prev) => {
            // Avoid duplicates
            if (prev.some(d => d.id === newDetection.id)) {
              return prev
            }
            return [newDetection, ...prev].slice(0, PAGE_SIZE)
          })
        }
      }
      
      // Update the total count
      setTotalCount((prev) => prev + 1)
      
      // Show toast notification for high-confidence detections
      if (newDetection.confidence && newDetection.confidence >= 0.7) {
        toast.success(
          `New detection: ${newDetection.species || 'Unknown'} (${(newDetection.confidence * 100).toFixed(0)}% confidence)`,
          {
            description: `Camera: ${newDetection.camera_name || newDetection.camera_id}`
          }
        )
      }
    }
  })

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

  const handleExport = async (format: 'csv' | 'json' = 'csv') => {
    try {
      setExporting(true)
      const blob = await exportDetections({ format })
      
      // Create download link
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `detections_export_${new Date().toISOString().split('T')[0]}.${format}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
      
      toast.success(`Exported ${format.toUpperCase()} file successfully`)
    } catch (error: any) {
      console.error('Export error:', error)
      toast.error(error.message || 'Failed to export detections')
    } finally {
      setExporting(false)
    }
  }

  const handleDelete = async (detectionId: number) => {
    if (!confirm(`Are you sure you want to delete detection #${detectionId}?`)) {
      return
    }

    try {
      await deleteDetection(detectionId)
      toast.success('Detection deleted successfully')
      // Refresh the list
      const offset = page * PAGE_SIZE
      const data = await getDetections({
        limit: PAGE_SIZE,
        offset: offset,
        search: searchQuery || undefined
      })
      setDetections(data)
      const count = await getDetectionsCount()
      setTotalCount(count)
    } catch (error: any) {
      console.error('Delete error:', error)
      toast.error(error.message || 'Failed to delete detection')
    }
  }

  const handleBulkDelete = async () => {
    if (selectedDetections.size === 0) {
      toast.error('No detections selected')
      return
    }

    if (!confirm(`Are you sure you want to delete ${selectedDetections.size} detection(s)?`)) {
      return
    }

    try {
      setDeleting(true)
      const result = await bulkDeleteDetections(Array.from(selectedDetections))
      toast.success(`Deleted ${result.deleted_count} detection(s) successfully`)
      setSelectedDetections(new Set())
      // Refresh the list
      const offset = page * PAGE_SIZE
      const data = await getDetections({
        limit: PAGE_SIZE,
        offset: offset,
        search: searchQuery || undefined
      })
      setDetections(data)
      const count = await getDetectionsCount()
      setTotalCount(count)
    } catch (error: any) {
      console.error('Bulk delete error:', error)
      toast.error(error.message || 'Failed to delete detections')
    } finally {
      setDeleting(false)
    }
  }

  const toggleSelection = (detectionId: number) => {
    const newSelection = new Set(selectedDetections)
    if (newSelection.has(detectionId)) {
      newSelection.delete(detectionId)
    } else {
      newSelection.add(detectionId)
    }
    setSelectedDetections(newSelection)
  }

  const toggleSelectAll = () => {
    if (selectedDetections.size === sortedDetections.length) {
      setSelectedDetections(new Set())
    } else {
      setSelectedDetections(new Set(sortedDetections.map(d => d.id)))
    }
  }

  // Show SSE connection status indicator
  const sseStatusIndicator = (
    <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
      {sseConnected ? (
        <>
          <Wifi className="h-4 w-4 text-green-500" />
          <span>Real-time updates active</span>
        </>
      ) : (
        <>
          <WifiOff className="h-4 w-4 text-yellow-500" />
          <span>Real-time updates disconnected</span>
          {sseError && <span className="text-xs">({sseError})</span>}
        </>
      )}
    </div>
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Detections</h1>
        <div className="flex items-center gap-2">
          <div className="text-sm text-muted-foreground">
            {totalCount} total detections | Page {page + 1} of {pageCount}
          </div>
        </div>
      </div>
      
      {sseStatusIndicator}
      
      {/* Search and Export Controls */}
      <div className="flex items-center gap-4">
        <div className="flex-1">
          <Input
            type="text"
            placeholder="Search detections (species, camera, path)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="max-w-md"
          />
        </div>
        <div className="flex gap-2">
          {selectedDetections.size > 0 && (
            <Button
              onClick={handleBulkDelete}
              disabled={deleting}
              variant="destructive"
              size="sm"
            >
              {deleting ? 'Deleting...' : `Delete ${selectedDetections.size} Selected`}
            </Button>
          )}
          <Button
            onClick={() => handleExport('csv')}
            disabled={exporting}
            variant="outline"
            size="sm"
          >
            <Download className="w-4 h-4 mr-2" />
            {exporting ? 'Exporting...' : 'Export CSV'}
          </Button>
          <Button
            onClick={() => handleExport('json')}
            disabled={exporting}
            variant="outline"
            size="sm"
          >
            <Download className="w-4 h-4 mr-2" />
            {exporting ? 'Exporting...' : 'Export JSON'}
          </Button>
        </div>
      </div>
      <div className="rounded-md border overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">
                <input
                  type="checkbox"
                  checked={selectedDetections.size === sortedDetections.length && sortedDetections.length > 0}
                  onChange={toggleSelectAll}
                  className="cursor-pointer"
                />
              </TableHead>
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
                <TableCell colSpan={7} className="text-center">No detections found.</TableCell>
              </TableRow>
            ) : (
              sortedDetections.map((detection) => {
                // Debug logging to see what we're getting
                console.log(`Detection ${detection.id}:`, {
                  media_url: detection.media_url,
                  image_path: detection.image_path,
                  species: detection.species
                })
                
                // Use backend media_url if available, otherwise generate from image_path
                let validImageUrl = detection.media_url && (detection.media_url.startsWith("/") || detection.media_url.startsWith("http")) 
                  ? detection.media_url 
                  : generateMediaUrl(detection.image_path)
                
                // If media_url starts with "/", prepend the backend URL
                if (validImageUrl && validImageUrl.startsWith("/") && !validImageUrl.startsWith("http")) {
                  validImageUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'}${validImageUrl}`
                }
                const commonName = detection.species && detection.species.includes(';') ? detection.species.split(';').pop()?.trim() : detection.species
                const isSelected = selectedDetections.has(detection.id)
                return (
                  <TableRow key={detection.id} className={isSelected ? "bg-muted" : ""}>
                    <TableCell>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelection(detection.id)}
                        className="cursor-pointer"
                      />
                    </TableCell>
                    <TableCell>
                      <div className="relative w-24 h-16 cursor-pointer" onClick={() => setSelectedDetection(detection)}>
                        <Image src={validImageUrl} alt={`Detection ${detection.id}`} fill className="object-cover rounded" />
                      </div>
                    </TableCell>
                    <TableCell>{new Date(detection.timestamp).toLocaleString()}</TableCell>
                    <TableCell>
                      <div className="group relative">
                        <span>{commonName}</span>
                        {detection.full_taxonomy && detection.full_taxonomy !== detection.species && (
                          <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block bg-black text-white text-xs rounded px-2 py-1 whitespace-nowrap z-10">
                            {detection.full_taxonomy}
                          </div>
                        )}
                      </div>
                    </TableCell>
                    <TableCell><Badge>{Math.round(detection.confidence * 100)}%</Badge></TableCell>
                    <TableCell>{detection.camera_name || detection.camera_id}</TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <a href={validImageUrl} target="_blank" rel="noopener noreferrer">
                          <Button size="sm" variant="outline">View</Button>
                        </a>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => handleDelete(detection.id)}
                        >
                          Delete
                        </Button>
                      </div>
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
                  Detection captured on {new Date(selectedDetection.timestamp).toLocaleString()}
                </DialogDescription>
              </DialogHeader>
              <div className="relative w-full h-64 mb-4">
                <Image 
                  src={(selectedDetection.media_url && (selectedDetection.media_url.startsWith("/") || selectedDetection.media_url.startsWith("http")) 
                    ? (selectedDetection.media_url.startsWith("/") 
                        ? `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'}${selectedDetection.media_url}` 
                        : selectedDetection.media_url)
                    : generateMediaUrl(selectedDetection.image_path))}
                  alt={`Detection ${selectedDetection.id}`} 
                  fill 
                  className="object-contain rounded" 
                />
              </div>
              <div className="space-y-2 text-sm">
                <div><b>Species:</b> {selectedDetection.species}</div>
                {selectedDetection.full_taxonomy && selectedDetection.full_taxonomy !== selectedDetection.species && (
                  <div><b>Full Taxonomy:</b> <span className="text-xs text-muted-foreground">{selectedDetection.full_taxonomy}</span></div>
                )}
                <div><b>Confidence:</b> {Math.round(selectedDetection.confidence * 100)}%</div>
                <div><b>Camera:</b> {selectedDetection.camera_name || selectedDetection.camera_id}</div>
                <div><b>File size:</b> {selectedDetection.file_size ? `${selectedDetection.file_size} bytes` : 'N/A'}</div>
                <div><b>Dimensions:</b> {selectedDetection.image_width && selectedDetection.image_height ? `${selectedDetection.image_width}x${selectedDetection.image_height}` : 'N/A'}</div>
                <div><b>Image path:</b> {selectedDetection.image_path}</div>
                <div><b>Backend media_url:</b> {selectedDetection.media_url || 'None'}</div>
                <div><b>Generated media_url:</b> {generateMediaUrl(selectedDetection.image_path)}</div>
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