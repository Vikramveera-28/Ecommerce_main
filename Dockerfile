FROM node:20-bullseye

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install Python for the Flask backend.
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip python3-venv && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install backend dependencies first so Docker can cache them.
COPY backend/requirements.txt ./backend/requirements.txt
RUN python3 -m pip install --no-cache-dir -r backend/requirements.txt

# Copy backend source and frontend source.
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Build the frontend into ./frontend/dist for Flask to serve.
WORKDIR /app/frontend
RUN npm ci
RUN npm run build

WORKDIR /app/backend
EXPOSE 5000

CMD ["/bin/bash", "-lc", "gunicorn --bind 0.0.0.0:${PORT:-5000} manage:app"]
