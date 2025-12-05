import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { CameraForm } from './CameraForm';
import { toast } from "sonner";
import { getCameras, syncCamerasFromMotionEye } from '@/lib/api';

import { CameraStream } from './camera-stream';
import { CameraConfig } from './CameraConfig';

interface Camera {
  id: number;
  name: string;
  url: string;
  is_active: boolean;
  created_at: string;
}

const CameraList: React.FC = () => {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [selectedCamera, setSelectedCamera] = useState<Camera | null>(null);
  const [isConfigOpen, setIsConfigOpen] = useState(false);

  const fetchCameras = useCallback(async () => {
    try {
      // Use cache for faster page navigation
      const data = await getCameras(true);
      setCameras(data);
    } catch (error) {
      console.error('Error fetching cameras:', error);
    }
  }, []);

  const handleSyncCameras = useCallback(async () => {
    try {
      const response = await syncCamerasFromMotionEye();
      toast.success(response.message || `Synced ${response.synced || 0} cameras from MotionEye`);
      fetchCameras(); // Refresh the list after sync
    } catch (error: any) {
      console.error('Error syncing cameras:', error);
      // Provide more helpful error messages
      const errorMessage = error.message || error.response?.data?.detail || "Failed to sync cameras from MotionEye";
      toast.error(errorMessage);
    }
  }, [fetchCameras]);

  useEffect(() => {
    // Fetch cameras on initial load (don't auto-sync - let user trigger sync manually)
    fetchCameras();
    // Refresh camera list every 30 seconds
    const interval = setInterval(fetchCameras, 30000);
    return () => clearInterval(interval);
  }, [fetchCameras]);

  const handleCameraSelect = (camera: Camera) => {
    setSelectedCamera(camera);
  };

  const handleConfigClose = () => {
    setIsConfigOpen(false);
    fetchCameras(); // Refresh the list after configuration changes
  };

  const handleRemoveCamera = async (cameraId: number) => {
    try {
      await axios.delete(`http://localhost:8001/cameras/${cameraId}`);
      toast.success("Camera removed successfully");
      fetchCameras();
    } catch (error: any) {
      console.error('Error removing camera:', error);
      toast.error(error.response?.data?.detail || "Failed to remove camera");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
            Camera Dashboard
          </h1>
          <p className="text-muted-foreground mt-2">
            Monitor and manage your wildlife cameras
          </p>
          <div className="flex items-center gap-4 mt-3 text-sm">
            <span className="flex items-center gap-2">
              <span className="w-3 h-3 bg-green-500 rounded-full"></span>
              {cameras.filter(c => c.is_active).length} Active
            </span>
            <span className="flex items-center gap-2">
              <span className="w-3 h-3 bg-gray-400 rounded-full"></span>
              {cameras.filter(c => !c.is_active).length} Inactive
            </span>
            <span className="flex items-center gap-2">
              <span className="w-3 h-3 bg-blue-500 rounded-full"></span>
              {cameras.filter(c => c.id >= 9).length} Thingino
            </span>
          </div>
        </div>
        <div className="flex gap-3">
          <Button 
            variant="outline" 
            onClick={handleSyncCameras}
            className="flex items-center gap-2"
          >
            🔄 Sync from MotionEye
          </Button>
          <Button 
            variant="outline" 
            onClick={fetchCameras}
            className="flex items-center gap-2"
          >
            ↻ Refresh
          </Button>
          <Dialog>
            <DialogTrigger asChild>
              <Button className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700">
                📷 Add Camera
              </Button>
            </DialogTrigger>
          <DialogContent className="sm:max-w-[600px]">
            <DialogHeader>
              <DialogTitle>Add New Camera</DialogTitle>
              <DialogDescription>
                Add a new camera to your wildlife monitoring system. Supports RTSP cameras and Thingino devices.
              </DialogDescription>
            </DialogHeader>
            <CameraForm onSuccess={fetchCameras} />
          </DialogContent>
        </Dialog>
        </div>
      </div>

      {/* Camera Stats Cards */}
      {cameras.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-950/20 dark:to-emerald-950/20">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-green-600 dark:text-green-400">Active Cameras</p>
                  <p className="text-3xl font-bold text-green-700 dark:text-green-300">
                    {cameras.filter(c => c.is_active).length}
                  </p>
                </div>
                <div className="text-4xl">📷</div>
              </div>
            </CardContent>
          </Card>
          
          <Card className="bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-blue-600 dark:text-blue-400">Thingino Cameras</p>
                  <p className="text-3xl font-bold text-blue-700 dark:text-blue-300">
                    {cameras.filter(c => c.id >= 9).length}
                  </p>
                </div>
                <div className="text-4xl">📹</div>
              </div>
            </CardContent>
          </Card>
          
          <Card className="bg-gradient-to-br from-purple-50 to-violet-50 dark:from-purple-950/20 dark:to-violet-950/20">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-purple-600 dark:text-purple-400">MotionEye Cameras</p>
                  <p className="text-3xl font-bold text-purple-700 dark:text-purple-300">
                    {cameras.filter(c => c.id < 9).length}
                  </p>
                </div>
                <div className="text-4xl">🎥</div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {cameras.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <h3 className="text-lg font-semibold mb-2">No cameras found</h3>
            <p className="text-muted-foreground text-center mb-4">
              Add your first camera to start monitoring wildlife.
            </p>
            <Dialog>
              <DialogTrigger asChild>
                <Button>Add Your First Camera</Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[600px]">
                <DialogHeader>
                  <DialogTitle>Add New Camera</DialogTitle>
                  <DialogDescription>
                    Add a new RTSP camera to your wildlife monitoring system.
                  </DialogDescription>
                </DialogHeader>
                <CameraForm onSuccess={fetchCameras} />
              </DialogContent>
            </Dialog>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {cameras.map((camera) => (
            <Card key={camera.id} className="overflow-hidden shadow-lg hover:shadow-xl transition-shadow">
              <CardHeader className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 p-4">
                <div className="flex flex-row items-center justify-between">
                  <CardTitle className="text-lg font-bold text-gray-900 dark:text-gray-100">
                    {camera.name}
                  </CardTitle>
                  <Badge 
                    variant={camera.is_active ? "default" : "destructive"}
                    className="text-xs px-2 py-0.5"
                  >
                    {camera.is_active ? "🟢" : "🔴"}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="p-4">
                <div className="space-y-3">
                  {/* Camera Stream */}
                  <div className="border rounded-lg overflow-hidden bg-gray-50 dark:bg-gray-900 aspect-square">
                    <CameraStream
                      cameraId={camera.id.toString()}
                      title={camera.name}
                      width={400}
                      height={400}
                    />
                  </div>
                  
                  {/* Camera Actions */}
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1 text-xs"
                      onClick={() => {
                        setSelectedCamera(camera);
                        setIsConfigOpen(true);
                      }}
                    >
                      ⚙️ Config
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      className="flex-1 text-xs"
                      onClick={() => handleRemoveCamera(camera.id)}
                    >
                      🗑️ Remove
                    </Button>
                  </div>
                  
                  {/* Camera Type Indicator */}
                  <div className="text-center">
                    <Badge variant="secondary" className="text-xs">
                      {camera.id >= 9 ? "Thingino" : "MotionEye"}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {selectedCamera && (
        <Dialog open={isConfigOpen} onOpenChange={setIsConfigOpen}>
          <DialogContent className="sm:max-w-[800px]">
            <DialogHeader>
              <DialogTitle>Configure Camera: {selectedCamera.name}</DialogTitle>
              <DialogDescription>
                Configure camera settings, detection parameters, and stream options.
              </DialogDescription>
            </DialogHeader>
            <Tabs defaultValue="general">
              <TabsList>
                <TabsTrigger value="general">General</TabsTrigger>
                <TabsTrigger value="detection">Detection</TabsTrigger>
                <TabsTrigger value="stream">Stream</TabsTrigger>
              </TabsList>
              <TabsContent value="general">
                <CameraConfig
                  cameraId={selectedCamera.id}
                  onClose={handleConfigClose}
                />
              </TabsContent>
              <TabsContent value="detection">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Detection Settings</h3>
                  <p className="text-muted-foreground">
                    Motion detection settings are configured through MotionEye. 
                    Visit the MotionEye interface for advanced detection configuration.
                  </p>
                  <Button 
                    variant="outline" 
                    onClick={() => window.open('http://localhost:8765', '_blank')}
                  >
                    Open MotionEye Interface
                  </Button>
                </div>
              </TabsContent>
              <TabsContent value="stream">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Stream Settings</h3>
                  <p className="text-muted-foreground">
                    Stream settings are managed through MotionEye. 
                    Visit the MotionEye interface for advanced stream configuration.
                  </p>
                  <Button 
                    variant="outline" 
                    onClick={() => window.open('http://localhost:8765', '_blank')}
                  >
                    Open MotionEye Interface
                  </Button>
                </div>
              </TabsContent>
            </Tabs>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};

export default CameraList; 