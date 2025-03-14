#!/bin/bash
set -e

echo "Stopping any running containers..."
docker-compose down

echo "Building Docker image with latest changes..."
docker-compose build

echo "Starting web container..."
docker-compose up -d web

echo "Container is now running!"
echo "Access the web UI at http://localhost:5000"
echo ""
echo "To view logs:"
echo "docker-compose logs -f web"
echo ""
echo "To stop the container:"
echo "docker-compose down" 