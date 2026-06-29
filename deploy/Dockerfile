# Stage 1: Build React frontend
FROM node:22-alpine AS build
WORKDIR /app
COPY frontend-react/package.json frontend-react/package-lock.json ./frontend-react/
RUN cd frontend-react && npm ci
COPY frontend-react/ ./frontend-react/
RUN cd frontend-react && npm run build

# Stage 2: Python runtime
FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps (backend only)
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy app code
COPY backend/ /app/backend/
COPY data/ /app/data/
COPY deploy/nginx.conf /etc/nginx/nginx.conf

# Copy built React frontend from build stage
COPY --from=build /app/frontend-react/dist /app/frontend-react/dist

# Create uploads dir
RUN mkdir -p /app/data/uploads

# Expose nginx port
EXPOSE 9000

# Start nginx and backend
COPY deploy/start.sh /app/start.sh
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
