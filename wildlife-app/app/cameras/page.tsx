"use client"

import React, { useEffect, useState } from 'react';
import CameraList from '@/components/CameraList';

const CamerasPage: React.FC = () => {
  const [mounted, setMounted] = useState(false);

  // Ensure component is mounted before rendering to trigger useEffect in CameraList
  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading cameras...</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1>Cameras</h1>
      <CameraList />
    </div>
  );
};

export default CamerasPage; 