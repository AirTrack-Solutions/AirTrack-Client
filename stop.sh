#!/bin/bash
echo ""
echo " ================================================"
echo "  AirTrack Solutions - Stopping AirTrack"
echo " ================================================"
echo ""
docker compose -f docker-compose.client.yml down
echo ""
echo " AirTrack has been stopped."
echo ""
