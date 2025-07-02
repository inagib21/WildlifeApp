#!/bin/bash

# Create necessary directories
mkdir -p motion_config motion_media

# Build and start containers
docker-compose build
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Check service status
echo "Checking service status..."
docker-compose ps

echo "Setup complete! You can access:"
echo "- Frontend: http://localhost:3000"
echo "- Backend API: http://localhost:8000"
echo "- Motion Web Interface: http://localhost:8080"
echo "- pgAdmin: http://localhost:5050" 