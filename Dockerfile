FROM node:20-bullseye

# Install Python and pip for the backend
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip python3-venv && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy backend and install Python dependencies
COPY backend/ ./backend/
RUN python3 -m pip install --no-cache-dir -r backend/requirements.txt

# Copy frontend and install Node dependencies, then build static assets
COPY frontend/ ./frontend/
WORKDIR /app/frontend
RUN npm install
RUN npm run build

# Expose backend port
EXPOSE 5000

# Go back to app root
WORKDIR /app

# Start backend with Gunicorn on Render-provided port.
CMD ["/bin/bash", "-lc", "cd /app/backend && gunicorn --bind 0.0.0.0:${PORT:-5000} manage:app"]
