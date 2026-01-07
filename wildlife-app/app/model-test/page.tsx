"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Upload, Camera, Zap, AlertTriangle, CheckCircle, Clock, Image as ImageIcon, Video, Loader2 } from "lucide-react";

interface TestFile {
  filename: string;
  path: string;
  size: number;
  type: "image" | "video";
}

export default function ModelTestPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState<string>("");
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [testFiles, setTestFiles] = useState<{ images: TestFile[]; videos: TestFile[]; total: number }>({ images: [], videos: [], total: 0 });
  const [loadingFiles, setLoadingFiles] = useState(true);
  const [selectedTestFile, setSelectedTestFile] = useState<TestFile | null>(null);

  // Load test images and videos
  useEffect(() => {
    const loadTestFiles = async () => {
      try {
        setLoadingFiles(true);
        const response = await fetch("http://localhost:8001/api/ai/test-images");
        if (response.ok) {
          const data = await response.json();
          console.log("Loaded test files:", data);
          setTestFiles(data);
        } else {
          console.error("Failed to load test files:", response.status, response.statusText);
          const errorText = await response.text();
          console.error("Error response:", errorText);
        }
      } catch (err) {
        console.error("Failed to load test files:", err);
        // Show helpful error message
        setError(`Failed to connect to backend: ${err instanceof Error ? err.message : 'Unknown error'}. Make sure backend is running on port 8001.`);
      } finally {
        setLoadingFiles(false);
      }
    };
    loadTestFiles();
  }, []);

  // Handle selecting a test file
  const handleSelectTestFile = async (file: TestFile) => {
    try {
      setSelectedTestFile(file);
      setSelectedFile(null);
      setError(null);
      setResults(null);
      
      // For images, use direct URL instead of fetching as blob (faster and works better)
      if (file.type === "image") {
        // Use direct image URL for preview
        setPreviewUrl(`http://localhost:8001${file.path}`);
        
        // Still fetch to create File object for testing
        try {
          const response = await fetch(`http://localhost:8001${file.path}`);
          if (!response.ok) {
            console.warn(`Failed to fetch file for testing: ${response.status}`);
            // Continue anyway - we have the preview URL
          } else {
            const blob = await response.blob();
            const fileObj = new File([blob], file.filename, { type: blob.type || "image/jpeg" });
            setSelectedFile(fileObj);
          }
        } catch (fetchErr) {
          console.warn("Could not create File object, but preview should work:", fetchErr);
          // Create a dummy file object for testing
          setSelectedFile(new File([], file.filename, { type: "image/jpeg" }));
        }
      } else {
        // For videos, use direct URL for preview
        const videoUrl = `http://localhost:8001${file.path}`;
        setPreviewUrl(videoUrl);
        
        // Create a lightweight File object reference (backend will extract frame)
        // We don't need to download the entire video - backend handles frame extraction
        const fileObj = new File([], file.filename, { type: "video/mp4" });
        setSelectedFile(fileObj);
        
        // Store the path so backend can access it directly
        (fileObj as any).backendPath = file.path;
        (fileObj as any).isVideo = true;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load test file");
      console.error("Error loading test file:", err);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setSelectedTestFile(null);
      
      // Create preview
      if (file.type.startsWith("video/")) {
        // For videos, create object URL
        const url = URL.createObjectURL(file);
        setPreviewUrl(url);
        (file as any).isVideo = true;
      } else {
        // For images, use FileReader
        const reader = new FileReader();
        reader.onload = (e) => setPreviewUrl(e.target?.result as string);
        reader.readAsDataURL(file);
      }
      
      setResults(null);
      setError(null);
    }
  };

  const handleTest = async () => {
    if (!selectedFile) return;
    
    setLoading(true);
    setError(null);
    setResults(null);
    setLoadingProgress("Preparing...");
    
    try {
      // Check if this is a video from test_images - use direct path endpoint (much faster)
      const backendPath = (selectedFile as any).backendPath;
      if (backendPath && selectedFile.size === 0) {
        // This is a video from test_images - use direct path processing (no upload needed!)
        setLoadingProgress("Processing video from server...");
        
        const response = await fetch("http://localhost:8001/api/ai/compare-path", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ file_path: backendPath }),
        });
        
        if (!response.ok) {
          throw new Error(`Failed to process video: ${response.statusText}`);
        }
        
        setLoadingProgress("Analyzing results...");
        const data = await response.json();
        setResults(data);
        setLoadingProgress("");
        return;
      }
      
      // Regular file upload (images or uploaded videos)
      setLoadingProgress("Uploading file...");
      const formData = new FormData();
      formData.append("file", selectedFile);
      
      setLoadingProgress("Processing with AI models...");
      const response = await fetch("http://localhost:8001/api/ai/compare", {
        method: "POST",
        body: formData,
      });
      
      if (!response.ok) {
        throw new Error(`Failed to test models: ${response.statusText}`);
      }
      
      setLoadingProgress("Analyzing results...");
      const data = await response.json();
      setResults(data);
      setLoadingProgress("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unknown error occurred");
      setLoadingProgress("");
    } finally {
      setLoading(false);
    }
  };

  const getConfidenceColor = (score: number) => {
    if (score >= 0.8) return "text-green-600";
    if (score >= 0.5) return "text-yellow-600";
    return "text-red-600";
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight mb-2">AI Model Tester</h1>
        <p className="text-muted-foreground">
          Upload an image or select from sample images/videos to test against all available AI models and compare accuracy and speed.
        </p>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Upload/Select Column */}
        <div className="lg:col-span-1 space-y-6">
          <Tabs defaultValue="samples" className="w-full">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="samples">Sample Media</TabsTrigger>
              <TabsTrigger value="upload">Upload</TabsTrigger>
            </TabsList>
            
            <TabsContent value="samples" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Sample Images & Videos</CardTitle>
                  <CardDescription>
                    {testFiles.total > 0 
                      ? `${testFiles.images.length} images, ${testFiles.videos.length} videos available`
                      : "No sample files found"}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {loadingFiles ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                  ) : testFiles.total === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      <p className="mb-2">No sample files found</p>
                      <p className="text-sm">Run: <code className="bg-muted px-2 py-1 rounded">download_media.bat</code></p>
                    </div>
                  ) : (
                    <div className="space-y-4 max-h-[600px] overflow-y-auto">
                      {testFiles.images.length > 0 && (
                        <div>
                          <h3 className="text-sm font-semibold mb-2 flex items-center">
                            <ImageIcon className="h-4 w-4 mr-2" />
                            Images ({testFiles.images.length})
                          </h3>
                          <div className="grid grid-cols-2 gap-2">
                            {testFiles.images.map((file) => (
                              <div
                                key={file.filename}
                                onClick={() => handleSelectTestFile(file)}
                                className={`relative aspect-square rounded-lg overflow-hidden cursor-pointer border-2 transition-all ${
                                  selectedTestFile?.filename === file.filename
                                    ? "border-primary shadow-lg"
                                    : "border-muted hover:border-primary/50"
                                }`}
                              >
                                <img
                                  src={`http://localhost:8001${file.path}`}
                                  alt={file.filename}
                                  className="w-full h-full object-cover"
                                  loading="lazy"
                                  onError={(e) => {
                                    console.error(`Failed to load image: ${file.path}`);
                                    const img = e.target as HTMLImageElement;
                                    img.style.display = "none";
                                    const parent = img.parentElement;
                                    if (parent) {
                                      parent.innerHTML = `<div class="w-full h-full flex items-center justify-center bg-muted text-muted-foreground text-xs p-2 text-center">Failed to load<br/>${file.filename}</div>`;
                                    }
                                  }}
                                />
                                <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-xs p-1 truncate">
                                  {file.filename}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {testFiles.videos.length > 0 && (
                        <div>
                          <h3 className="text-sm font-semibold mb-2 flex items-center">
                            <Video className="h-4 w-4 mr-2" />
                            Videos ({testFiles.videos.length})
                          </h3>
                          <div className="grid grid-cols-2 gap-2">
                            {testFiles.videos.map((file) => (
                              <div
                                key={file.filename}
                                onClick={() => handleSelectTestFile(file)}
                                className={`relative aspect-square rounded-lg overflow-hidden cursor-pointer border-2 transition-all ${
                                  selectedTestFile?.filename === file.filename
                                    ? "border-primary shadow-lg"
                                    : "border-muted hover:border-primary/50"
                                }`}
                              >
                                <div className="w-full h-full bg-black flex items-center justify-center relative">
                                  <video 
                                    src={`http://localhost:8001${file.path}`}
                                    className="w-full h-full object-cover"
                                    preload="metadata"
                                    muted
                                    onLoadedMetadata={(e) => {
                                      // Seek to first frame for thumbnail
                                      const video = e.target as HTMLVideoElement;
                                      video.currentTime = 0.1;
                                    }}
                                    onError={() => {
                                      // Fallback to icon if video fails to load
                                      const parent = (event?.target as HTMLElement)?.parentElement;
                                      if (parent) {
                                        parent.innerHTML = `
                                          <div class="w-full h-full bg-muted flex items-center justify-center">
                                            <svg class="h-8 w-8 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                            </svg>
                                          </div>
                                        `;
                                      }
                                    }}
                                  />
                                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                                    <div className="bg-black/40 rounded-full p-2">
                                      <Video className="h-6 w-6 text-white" />
                                    </div>
                                  </div>
                                </div>
                                <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-xs p-1 truncate">
                                  {file.filename}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
            
            <TabsContent value="upload" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Upload Image</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div 
                      className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                        previewUrl ? "border-primary/50" : "border-muted-foreground/25 hover:border-primary/50"
                      }`}
                      onClick={() => document.getElementById("file-upload")?.click()}
                    >
                      {previewUrl ? (
                        <div className="relative aspect-video w-full overflow-hidden rounded-md">
                          {selectedFile?.type.startsWith("video/") ? (
                            <video src={previewUrl} className="w-full h-full object-contain" controls />
                          ) : (
                            <img 
                              src={previewUrl} 
                              alt="Preview" 
                              className="object-contain w-full h-full"
                            />
                          )}
                        </div>
                      ) : (
                        <div className="flex flex-col items-center py-6">
                          <Upload className="h-10 w-10 text-muted-foreground mb-4" />
                          <p className="text-sm font-medium">Click to upload image</p>
                          <p className="text-xs text-muted-foreground mt-1">JPG, PNG, MP4 supported</p>
                        </div>
                      )}
                      <input 
                        id="file-upload"
                        type="file" 
                        accept="image/*,video/*" 
                        className="hidden" 
                        onChange={handleFileSelect}
                      />
                    </div>
                    
                    {selectedFile && (
                      <div className="text-xs text-muted-foreground">
                        Selected: {selectedFile.name} ({formatFileSize(selectedFile.size)})
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
          
          <Button 
            onClick={handleTest} 
            disabled={!selectedFile || loading} 
            className="w-full"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                {loadingProgress || "Running Models..."}
              </>
            ) : (
              <>
                <Zap className="mr-2 h-4 w-4" />
                Test All Models
              </>
            )}
          </Button>
          
          {loading && loadingProgress && (
            <div className="text-xs text-muted-foreground text-center">
              {loadingProgress}
            </div>
          )}
          
          {error && (
            <div className="bg-red-50 text-red-600 p-3 rounded-md text-sm flex items-center">
              <AlertTriangle className="h-4 w-4 mr-2" />
              {error}
            </div>
          )}
        </div>

        {/* Results Column */}
        <div className="lg:col-span-2">
          {results ? (
            <div className="space-y-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-semibold">Comparison Results</h2>
                {results._behavioral_summary && results._behavioral_summary.consensus_behaviors?.length > 0 && (
                  <div className="text-sm">
                    <span className="text-muted-foreground">Consensus: </span>
                    <span className="font-medium text-green-600 dark:text-green-400">
                      {results._behavioral_summary.consensus_behaviors.join(", ")}
                    </span>
                  </div>
                )}
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(results).filter(([key]) => !key.startsWith("_")).map(([key, data]: [string, any]) => {
                  const isEnsemble = key === "ensemble";
                  const primaryPred = data.predictions?.[0];
                  
                  return (
                    <Card key={key} className={isEnsemble ? "border-primary border-2 shadow-lg" : ""}>
                      <CardHeader className="pb-2">
                        <div className="flex justify-between items-center">
                          <CardTitle className="text-lg flex items-center">
                            {isEnsemble && <Zap className="h-4 w-4 text-primary mr-2" />}
                            {data.name || key}
                          </CardTitle>
                          {isEnsemble && (
                            <span className="bg-primary/10 text-primary text-xs px-2 py-1 rounded-full font-medium">
                              Recommended
                            </span>
                          )}
                        </div>
                        <CardDescription className="flex items-center space-x-4">
                          <span className="flex items-center">
                            <Clock className="h-3 w-3 mr-1" />
                            {data.inference_time_ms}ms
                          </span>
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        {data.error ? (
                          <div className="text-red-500 text-sm">{data.error}</div>
                        ) : primaryPred ? (
                          <div className="space-y-3">
                            <div>
                              <div className="text-sm text-muted-foreground mb-1">Top Prediction</div>
                              <div className="flex justify-between items-baseline">
                                <span className="text-2xl font-bold capitalize">
                                  {primaryPred.prediction}
                                </span>
                                <span className={`text-lg font-mono font-bold ${getConfidenceColor(primaryPred.prediction_score)}`}>
                                  {(primaryPred.prediction_score * 100).toFixed(1)}%
                                </span>
                              </div>
                            </div>
                            
                            {/* Behavioral Information */}
                            {data.behaviors && data.behaviors.length > 0 && (
                              <div className="pt-2 border-t">
                                <div className="text-xs text-muted-foreground mb-2">Detected Behaviors</div>
                                <div className="flex flex-wrap gap-1">
                                  {data.behaviors.map((behavior: string, i: number) => {
                                    const isConsensus = data.consensus_behaviors?.includes(behavior);
                                    return (
                                      <span
                                        key={i}
                                        className={`text-xs px-2 py-1 rounded ${
                                          isConsensus
                                            ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                                            : "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
                                        }`}
                                        title={isConsensus ? "Detected by multiple models" : "Detected by this model only"}
                                      >
                                        {behavior}
                                        {isConsensus && " ✓"}
                                      </span>
                                    );
                                  })}
                                </div>
                              </div>
                            )}
                            
                            {data.predictions.length > 1 && (
                              <div className="pt-2 border-t">
                                <div className="text-xs text-muted-foreground mb-2">Alternatives</div>
                                <div className="space-y-1">
                                  {data.predictions.slice(1, 3).map((p: any, i: number) => (
                                    <div key={i} className="flex justify-between text-sm">
                                      <span className="capitalize">{p.prediction}</span>
                                      <span className="text-muted-foreground">
                                        {(p.prediction_score * 100).toFixed(1)}%
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {isEnsemble && data.models_used && (
                              <div className="pt-2 border-t mt-2">
                                <div className="text-xs text-muted-foreground">Contributing Models</div>
                                <div className="flex flex-wrap gap-1 mt-1">
                                  {data.models_used.map((m: string) => (
                                    <span key={m} className="bg-secondary text-secondary-foreground text-[10px] px-1.5 py-0.5 rounded">
                                      {m}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="text-muted-foreground text-sm italic">
                            No detections found
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed rounded-lg p-12 min-h-[400px]">
              <div className="bg-secondary/50 p-4 rounded-full mb-4">
                <Camera className="h-8 w-8 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-medium mb-1">Ready to Test</h3>
              <p className="text-sm max-w-sm text-center">
                Select a sample image/video or upload your own to see how different AI models analyze it.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
