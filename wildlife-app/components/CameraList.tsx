import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { CameraForm } from './CameraForm';
import { toast } from "sonner";

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

  const fetchCameras = async () => {
    try {
      const response = await axios.get('http://localhost:8001/cameras');
      setCameras(response.data);
    } catch (error) {
      console.error('Error fetching cameras:', error);
    }
  };

  useEffect(() => {
    fetchCameras();
    // Refresh camera list every 30 seconds
    const interval = setInterval(fetchCameras, 30000);
    return () => clearInterval(interval);
  }, []);

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
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Cameras</h1>
        <Dialog>
          <DialogTrigger asChild>
            <Button>Add Camera</Button>
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
      </div>

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
            <Card key={camera.id} className="overflow-hidden">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-xl font-bold">{camera.name}</CardTitle>
                <Badge variant={camera.is_active ? "default" : "destructive"}>
                  {camera.is_active ? "Active" : "Inactive"}
                </Badge>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <CameraStream
                    cameraId={camera.id.toString()}
                    title={camera.name}
                    width={640}
                    height={480}
                  />
                  <div className="flex justify-between items-center">
                    <Button
                      variant="outline"
                      onClick={() => {
                        setSelectedCamera(camera);
                        setIsConfigOpen(true);
                      }}
                    >
                      Configure
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={() => handleRemoveCamera(camera.id)}
                    >
                      Remove
                    </Button>
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