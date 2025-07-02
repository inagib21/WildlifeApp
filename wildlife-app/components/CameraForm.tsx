import React, { useState } from 'react';
import axios from 'axios';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";

interface CameraFormProps {
  onSuccess: () => void;
}

export const CameraForm: React.FC<CameraFormProps> = ({ onSuccess }) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    url: '',
    is_active: true,
    width: 1280,
    height: 720,
    framerate: 30
  });

  const validateRTSPUrl = (url: string): boolean => {
    const rtspPattern = /^rtsp:\/\/[^\s]+$/;
    return rtspPattern.test(url);
  };

  const testConnection = async () => {
    if (!formData.url) {
      toast.error("Please enter an RTSP URL first");
      return;
    }

    if (!validateRTSPUrl(formData.url)) {
      toast.error("Please enter a valid RTSP URL (e.g., rtsp://username:password@ip:port/stream)");
      return;
    }

    setIsTesting(true);
    try {
      // Test MotionEye connection first
      const motioneyeResponse = await axios.get('http://localhost:8765');
      if (motioneyeResponse.status === 200) {
        toast.success("MotionEye is running and ready to accept cameras!");
      }
    } catch (error) {
      toast.error("MotionEye is not running. Please start MotionEye first.");
    } finally {
      setIsTesting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateRTSPUrl(formData.url)) {
      toast.error("Please enter a valid RTSP URL (e.g., rtsp://username:password@ip:port/stream)");
      return;
    }

    setIsSubmitting(true);
    try {
      await axios.post('http://localhost:8001/cameras', formData);
      toast.success("Camera added successfully");
      onSuccess();
    } catch (error: any) {
      console.error('Error adding camera:', error);
      toast.error(error.response?.data?.detail || "Failed to add camera");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked : value
    }));
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Camera Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="name">Camera Name</Label>
              <Input
                id="name"
                name="name"
                value={formData.name}
                onChange={handleChange}
                placeholder="Wildlife Camera 1"
                required
              />
            </div>
            <div>
              <Label htmlFor="url">RTSP URL</Label>
              <Input
                id="url"
                name="url"
                value={formData.url}
                onChange={handleChange}
                placeholder="rtsp://username:password@ip:port/stream"
                required
              />
            </div>
          </div>
          
          <div className="grid grid-cols-3 gap-4">
            <div>
              <Label htmlFor="width">Width</Label>
              <Input
                id="width"
                name="width"
                type="number"
                value={formData.width}
                onChange={handleChange}
                placeholder="1280"
              />
            </div>
            <div>
              <Label htmlFor="height">Height</Label>
              <Input
                id="height"
                name="height"
                type="number"
                value={formData.height}
                onChange={handleChange}
                placeholder="720"
              />
            </div>
            <div>
              <Label htmlFor="framerate">Frame Rate</Label>
              <Input
                id="framerate"
                name="framerate"
                type="number"
                value={formData.framerate}
                onChange={handleChange}
                placeholder="30"
              />
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <Switch
              id="is_active"
              name="is_active"
              checked={formData.is_active}
              onCheckedChange={(checked) => setFormData(prev => ({ ...prev, is_active: checked }))}
            />
            <Label htmlFor="is_active">Camera Active</Label>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button
          type="button"
          variant="outline"
          onClick={testConnection}
          disabled={isTesting}
        >
          {isTesting ? "Testing..." : "Test MotionEye Connection"}
        </Button>
        <Button
          type="submit"
          disabled={isSubmitting}
        >
          {isSubmitting ? "Adding..." : "Add Camera"}
        </Button>
      </div>

      <div className="p-4 bg-blue-50 rounded-lg">
        <h4 className="font-semibold text-blue-900">MotionEye Integration</h4>
        <p className="text-sm text-blue-700 mt-2">
          This camera will be managed through MotionEye. After adding the camera, 
          you can configure advanced settings in the MotionEye web interface at{' '}
          <a href="http://localhost:8765" target="_blank" rel="noopener noreferrer" 
             className="text-blue-600 hover:underline">
            http://localhost:8765
          </a>
        </p>
      </div>
    </form>
  );
}; 