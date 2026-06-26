#!/bin/bash
set -e

# Start FastAPI backend on port 8000
cd /app
uvicorn backend.app:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start Streamlit frontend on port 8501
cd /app
streamlit run frontend/streamlit_app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false &
FRONTEND_PID=$!

# Start nginx in foreground
nginx -g "daemon off;" &
NGINX_PID=$!

# Trap signals for graceful shutdown
trap "kill $BACKEND_PID $FRONTEND_PID $NGINX_PID; exit 0" SIGTERM SIGINT

# Wait for any process to exit
wait -n $BACKEND_PID $FRONTEND_PID $NGINX_PID
