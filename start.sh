#!/bin/bash
echo ""
echo " ================================================"
echo "  AirTrack Solutions - Starting AirTrack"
echo " ================================================"
echo ""
echo " Please wait while AirTrack starts up..."
echo ""
docker compose -f docker-compose.client.yml up -d
if [ $? -ne 0 ]; then
    echo ""
    echo " ERROR: AirTrack failed to start."
    echo " Make sure Docker is running and try again."
    echo ""
    exit 1
fi
echo ""
echo " ================================================"
echo "  AirTrack is running!"
echo "  Open your browser and go to:"
echo "  http://localhost:5000"
echo " ================================================"
echo ""
