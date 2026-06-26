FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY backend/requirements.txt /app/backend/requirements.txt
COPY frontend/requirements.txt /app/frontend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt -r /app/frontend/requirements.txt

# Copy app code
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY data/ /app/data/
COPY deploy/nginx.conf /etc/nginx/nginx.conf

# Create uploads dir
RUN mkdir -p /app/data/uploads

# Expose nginx port
EXPOSE 9000

# Start nginx and both services
COPY deploy/start.sh /app/start.sh
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
