#!/bin/bash
set -e

# Start FastAPI backend on port 8000
cd /app
uvicorn backend.app:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start nginx in foreground
nginx -g "daemon off;" &
NGINX_PID=$!

# Trap signals for graceful shutdown
trap "kill $BACKEND_PID $NGINX_PID; exit 0" SIGTERM SIGINT

# Wait for any process to exit
wait -n $BACKEND_PID $NGINX_PID
