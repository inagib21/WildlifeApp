import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

interface CameraConfigProps {
  cameraId: number;
  onClose: () => void;
}

interface CameraConfig {
  id: number;
  name: string;
  url: string;
  is_active: boolean;
  width: number;
  height: number;
  framerate: number;
  stream_port: number;
  stream_quality: number;
  stream_maxrate: number;
  stream_localhost: boolean;
  detection_enabled: boolean;
  detection_threshold: number;
  detection_smart_mask_speed: number;
  movie_output: boolean;
  movie_quality: number;
  movie_codec: string;
  snapshot_interval: number;
  target_dir: string;
}

interface MotionSettings {
  threshold: number;
  threshold_maximum: number;
  threshold_tune: boolean;
  noise_tune: boolean;
  noise_level: number;
  lightswitch_percent: number;
  despeckle_filter: string;
  minimum_motion_frames: number;
  smart_mask_speed: number;
  motion_detection: boolean;
  picture_output_motion: boolean;
  movie_output_motion: boolean;
  pre_capture: number;
  post_capture: number;
}

export const CameraConfig: React.FC<CameraConfigProps> = ({ cameraId, onClose }) => {
  const [config, setConfig] = useState<CameraConfig>({
    id: cameraId,
    name: `Camera ${cameraId}`,
    url: '',
    is_active: true,
    width: 1280,
    height: 720,
    framerate: 30,
    stream_port: 8081,
    stream_quality: 100,
    stream_maxrate: 30,
    stream_localhost: false,
    detection_enabled: true,
    detection_threshold: 1500,
    detection_smart_mask_speed: 10,
    movie_output: true,
    movie_quality: 100,
    movie_codec: 'mkv',
    snapshot_interval: 0,
    target_dir: './motioneye_media'
  });
  const [isLoading, setIsLoading] = useState(false);
  const [cameraStatus, setCameraStatus] = useState<string>('unknown');
  const [isTesting, setIsTesting] = useState(false);
  const [motionSettings, setMotionSettings] = useState<MotionSettings>({
    threshold: 1500,
    threshold_maximum: 0,
    threshold_tune: true,
    noise_tune: true,
    noise_level: 32,
    lightswitch_percent: 0,
    despeckle_filter: '',
    minimum_motion_frames: 1,
    smart_mask_speed: 0,
    motion_detection: true,
    picture_output_motion: false,
    movie_output_motion: false,
    pre_capture: 0,
    post_capture: 0,
  });

  useEffect(() => {
    loadCameraConfig();
    loadMotionSettings();
    checkCameraStatus();
  }, [cameraId]);

  const loadCameraConfig = async () => {
    try {
      const response = await axios.get(`http://localhost:8001/cameras/${cameraId}`);
      if (response.data) {
        setConfig(prev => ({ ...prev, ...response.data }));
      }
    } catch (error) {
      console.error('Error loading camera config:', error);
    }
  };

  const loadMotionSettings = async () => {
    try {
      const response = await axios.get(`http://localhost:8001/cameras/${cameraId}/motion-settings`);
      if (response.data) {
        setMotionSettings(response.data);
      }
    } catch (error) {
      console.error('Error loading motion settings:', error);
    }
  };

  const checkCameraStatus = async () => {
    try {
      const response = await axios.get(`http://localhost:8001/stream/${cameraId}`);
      setCameraStatus('active');
    } catch (error) {
      setCameraStatus('error');
    }
  };

  const testConnection = async () => {
    setIsTesting(true);
    try {
      // Test MotionEye connection
      const response = await axios.get(`http://localhost:8765`);
      if (response.status === 200) {
        toast.success("MotionEye connection successful!");
      }
    } catch (error) {
      toast.error("MotionEye connection failed. Check if MotionEye is running.");
    } finally {
      setIsTesting(false);
    }
  };

  const startCamera = async () => {
    setIsLoading(true);
    try {
      // Update camera to active status
      await axios.put(`http://localhost:8001/cameras/${cameraId}`, {
        is_active: true
      });
      toast.success("Camera activated successfully");
      checkCameraStatus();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to activate camera");
    } finally {
      setIsLoading(false);
    }
  };

  const stopCamera = async () => {
    setIsLoading(true);
    try {
      // Update camera to inactive status
      await axios.put(`http://localhost:8001/cameras/${cameraId}`, {
        is_active: false
      });
      toast.success("Camera deactivated successfully");
      checkCameraStatus();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to deactivate camera");
    } finally {
      setIsLoading(false);
    }
  };

  const saveConfig = async () => {
    setIsLoading(true);
    try {
      // Update camera configuration
      await axios.put(`http://localhost:8001/cameras/${cameraId}`, {
        name: config.name,
        url: config.url,
        width: config.width,
        height: config.height,
        framerate: config.framerate,
        stream_port: config.stream_port,
        stream_quality: config.stream_quality,
        stream_maxrate: config.stream_maxrate,
        stream_localhost: config.stream_localhost,
        detection_enabled: config.detection_enabled,
        detection_threshold: config.detection_threshold,
        detection_smart_mask_speed: config.detection_smart_mask_speed,
        movie_output: config.movie_output,
        movie_quality: config.movie_quality,
        movie_codec: config.movie_codec,
        snapshot_interval: config.snapshot_interval,
        target_dir: config.target_dir
      });
      toast.success("Configuration saved successfully");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to save configuration");
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfigChange = (key: keyof CameraConfig, value: any) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const saveMotionSettings = async () => {
    setIsLoading(true);
    try {
      await axios.post(`http://localhost:8001/cameras/${cameraId}/motion-settings`, motionSettings);
      toast.success("Motion settings saved successfully");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to save motion settings");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Camera Configuration</h2>
        <div className="flex items-center space-x-2">
          <Badge variant={cameraStatus === 'active' ? 'default' : 'destructive'}>
            {cameraStatus}
          </Badge>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>

      <Tabs defaultValue="general" className="w-full">
        <TabsList>
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="stream">Stream</TabsTrigger>
          <TabsTrigger value="detection">Detection</TabsTrigger>
          <TabsTrigger value="output">Output</TabsTrigger>
          <TabsTrigger value="actions">Actions</TabsTrigger>
        </TabsList>

        <TabsContent value="general" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Basic Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="name">Camera Name</Label>
                  <Input
                    id="name"
                    value={config.name}
                    onChange={(e) => handleConfigChange('name', e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="url">RTSP URL</Label>
                  <Input
                    id="url"
                    value={config.url}
                    onChange={(e) => handleConfigChange('url', e.target.value)}
                    placeholder="rtsp://username:password@ip:port/stream"
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <Label htmlFor="width">Width</Label>
                  <Input
                    id="width"
                    type="number"
                    value={config.width}
                    onChange={(e) => handleConfigChange('width', parseInt(e.target.value))}
                  />
                </div>
                <div>
                  <Label htmlFor="height">Height</Label>
                  <Input
                    id="height"
                    type="number"
                    value={config.height}
                    onChange={(e) => handleConfigChange('height', parseInt(e.target.value))}
                  />
                </div>
                <div>
                  <Label htmlFor="framerate">Frame Rate</Label>
                  <Input
                    id="framerate"
                    type="number"
                    value={config.framerate}
                    onChange={(e) => handleConfigChange('framerate', parseInt(e.target.value))}
                  />
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <Switch
                  id="is_active"
                  checked={config.is_active}
                  onCheckedChange={(checked) => handleConfigChange('is_active', checked)}
                />
                <Label htmlFor="is_active">Camera Active</Label>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="stream" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Stream Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="stream_port">Stream Port</Label>
                  <Input
                    id="stream_port"
                    type="number"
                    value={config.stream_port}
                    onChange={(e) => handleConfigChange('stream_port', parseInt(e.target.value))}
                  />
                </div>
                <div>
                  <Label htmlFor="stream_quality">Stream Quality</Label>
                  <Input
                    id="stream_quality"
                    type="number"
                    min="1"
                    max="100"
                    value={config.stream_quality}
                    onChange={(e) => handleConfigChange('stream_quality', parseInt(e.target.value))}
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="stream_maxrate">Max Frame Rate</Label>
                  <Input
                    id="stream_maxrate"
                    type="number"
                    value={config.stream_maxrate}
                    onChange={(e) => handleConfigChange('stream_maxrate', parseInt(e.target.value))}
                  />
                </div>
                <div className="flex items-center space-x-2">
                  <Switch
                    id="stream_localhost"
                    checked={config.stream_localhost}
                    onCheckedChange={(checked) => handleConfigChange('stream_localhost', checked)}
                  />
                  <Label htmlFor="stream_localhost">Localhost Only</Label>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="detection" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Motion Detection Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center space-x-2">
                <Switch
                  id="motion_detection"
                  checked={motionSettings.motion_detection}
                  onCheckedChange={(checked) => setMotionSettings(prev => ({ ...prev, motion_detection: checked }))}
                />
                <Label htmlFor="motion_detection">Enable Motion Detection</Label>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="threshold">Motion Threshold</Label>
                  <Input
                    id="threshold"
                    type="number"
                    value={motionSettings.threshold}
                    onChange={(e) => setMotionSettings(prev => ({ ...prev, threshold: parseInt(e.target.value) || 0 }))}
                  />
                  <p className="text-xs text-muted-foreground mt-1">Lower = more sensitive (default: 1500)</p>
                </div>
                <div>
                  <Label htmlFor="threshold_maximum">Threshold Maximum</Label>
                  <Input
                    id="threshold_maximum"
                    type="number"
                    value={motionSettings.threshold_maximum}
                    onChange={(e) => setMotionSettings(prev => ({ ...prev, threshold_maximum: parseInt(e.target.value) || 0 }))}
                  />
                  <p className="text-xs text-muted-foreground mt-1">0 = disabled</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="noise_level">Noise Level</Label>
                  <Input
                    id="noise_level"
                    type="number"
                    min="0"
                    max="100"
                    value={motionSettings.noise_level}
                    onChange={(e) => setMotionSettings(prev => ({ ...prev, noise_level: parseInt(e.target.value) || 0 }))}
                  />
                  <p className="text-xs text-muted-foreground mt-1">Ignore noise below this level (0-100)</p>
                </div>
                <div>
                  <Label htmlFor="minimum_motion_frames">Minimum Motion Frames</Label>
                  <Input
                    id="minimum_motion_frames"
                    type="number"
                    min="1"
                    value={motionSettings.minimum_motion_frames}
                    onChange={(e) => setMotionSettings(prev => ({ ...prev, minimum_motion_frames: parseInt(e.target.value) || 1 }))}
                  />
                  <p className="text-xs text-muted-foreground mt-1">Frames before triggering (default: 1)</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="smart_mask_speed">Smart Mask Speed</Label>
                  <Input
                    id="smart_mask_speed"
                    type="number"
                    min="0"
                    value={motionSettings.smart_mask_speed}
                    onChange={(e) => setMotionSettings(prev => ({ ...prev, smart_mask_speed: parseInt(e.target.value) || 0 }))}
                  />
                  <p className="text-xs text-muted-foreground mt-1">0 = disabled, higher = faster learning</p>
                </div>
                <div>
                  <Label htmlFor="lightswitch_percent">Lightswitch Percent</Label>
                  <Input
                    id="lightswitch_percent"
                    type="number"
                    min="0"
                    max="100"
                    value={motionSettings.lightswitch_percent}
                    onChange={(e) => setMotionSettings(prev => ({ ...prev, lightswitch_percent: parseInt(e.target.value) || 0 }))}
                  />
                  <p className="text-xs text-muted-foreground mt-1">Ignore light changes below this % (0-100)</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="pre_capture">Pre-Capture (seconds)</Label>
                  <Input
                    id="pre_capture"
                    type="number"
                    min="0"
                    value={motionSettings.pre_capture}
                    onChange={(e) => setMotionSettings(prev => ({ ...prev, pre_capture: parseInt(e.target.value) || 0 }))}
                  />
                  <p className="text-xs text-muted-foreground mt-1">Record before motion detected</p>
                </div>
                <div>
                  <Label htmlFor="post_capture">Post-Capture (seconds)</Label>
                  <Input
                    id="post_capture"
                    type="number"
                    min="0"
                    value={motionSettings.post_capture}
                    onChange={(e) => setMotionSettings(prev => ({ ...prev, post_capture: parseInt(e.target.value) || 0 }))}
                  />
                  <p className="text-xs text-muted-foreground mt-1">Record after motion ends</p>
                </div>
              </div>

              <div className="flex items-center space-x-4">
                <div className="flex items-center space-x-2">
                  <Switch
                    id="threshold_tune"
                    checked={motionSettings.threshold_tune}
                    onCheckedChange={(checked) => setMotionSettings(prev => ({ ...prev, threshold_tune: checked }))}
                  />
                  <Label htmlFor="threshold_tune">Auto-Tune Threshold</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Switch
                    id="noise_tune"
                    checked={motionSettings.noise_tune}
                    onCheckedChange={(checked) => setMotionSettings(prev => ({ ...prev, noise_tune: checked }))}
                  />
                  <Label htmlFor="noise_tune">Auto-Tune Noise</Label>
                </div>
              </div>

              <div className="flex items-center space-x-4">
                <div className="flex items-center space-x-2">
                  <Switch
                    id="picture_output_motion"
                    checked={motionSettings.picture_output_motion}
                    onCheckedChange={(checked) => setMotionSettings(prev => ({ ...prev, picture_output_motion: checked }))}
                  />
                  <Label htmlFor="picture_output_motion">Save Pictures on Motion</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Switch
                    id="movie_output_motion"
                    checked={motionSettings.movie_output_motion}
                    onCheckedChange={(checked) => setMotionSettings(prev => ({ ...prev, movie_output_motion: checked }))}
                  />
                  <Label htmlFor="movie_output_motion">Save Videos on Motion</Label>
                </div>
              </div>

              <div>
                <Label htmlFor="despeckle_filter">Despeckle Filter</Label>
                <Input
                  id="despeckle_filter"
                  value={motionSettings.despeckle_filter}
                  onChange={(e) => setMotionSettings(prev => ({ ...prev, despeckle_filter: e.target.value }))}
                  placeholder="EedDl (e.g., EedDl = Erode, dilate, dilate, Erode)"
                />
                <p className="text-xs text-muted-foreground mt-1">Filter pattern to reduce false positives</p>
              </div>

              <Button
                onClick={saveMotionSettings}
                disabled={isLoading}
                variant="default"
                className="w-full"
              >
                Save Motion Settings
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="output" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Recording Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center space-x-2">
                <Switch
                  id="movie_output"
                  checked={config.movie_output}
                  onCheckedChange={(checked) => handleConfigChange('movie_output', checked)}
                />
                <Label htmlFor="movie_output">Enable Video Recording</Label>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="movie_quality">Video Quality</Label>
                  <Input
                    id="movie_quality"
                    type="number"
                    min="1"
                    max="100"
                    value={config.movie_quality}
                    onChange={(e) => handleConfigChange('movie_quality', parseInt(e.target.value))}
                  />
                </div>
                <div>
                  <Label htmlFor="movie_codec">Video Codec</Label>
                  <Input
                    id="movie_codec"
                    value={config.movie_codec}
                    onChange={(e) => handleConfigChange('movie_codec', e.target.value)}
                  />
                </div>
              </div>
              
              <div>
                <Label htmlFor="target_dir">Output Directory</Label>
                <Input
                  id="target_dir"
                  value={config.target_dir}
                  onChange={(e) => handleConfigChange('target_dir', e.target.value)}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="actions" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Camera Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-4">
                <Button
                  onClick={testConnection}
                  disabled={isTesting}
                  variant="outline"
                >
                  {isTesting ? "Testing..." : "Test MotionEye Connection"}
                </Button>
                <Button
                  onClick={startCamera}
                  disabled={isLoading}
                  variant="default"
                >
                  Activate Camera
                </Button>
                <Button
                  onClick={stopCamera}
                  disabled={isLoading}
                  variant="destructive"
                >
                  Deactivate Camera
                </Button>
                <Button
                  onClick={saveConfig}
                  disabled={isLoading}
                  variant="default"
                >
                  Save Configuration
                </Button>
              </div>
              
              <div className="mt-4 p-4 bg-blue-50 rounded-lg">
                <h4 className="font-semibold text-blue-900">MotionEye Integration</h4>
                <p className="text-sm text-blue-700 mt-2">
                  This camera is managed through MotionEye. For advanced configuration, 
                  visit the MotionEye web interface at{' '}
                  <a href="http://localhost:8765" target="_blank" rel="noopener noreferrer" 
                     className="text-blue-600 hover:underline">
                    http://localhost:8765
                  </a>
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}; 