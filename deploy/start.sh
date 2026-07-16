#!/bin/bash
set -e

# Start FastAPI backend on port 8000 in background
cd /app
uvicorn backend.app:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait briefly for FastAPI to be ready
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/status >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

# Trap signals for graceful shutdown
trap "kill $BACKEND_PID 2>/dev/null || true; exit 0" SIGTERM SIGINT

# Start nginx in foreground (this is the main container process)
exec nginx -g "daemon off;"
