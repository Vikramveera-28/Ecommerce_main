FROM node:20-bullseye

# Install Python and pip for the backend
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip python3-venv && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy backend and install Python dependencies
COPY backend/ ./backend/
RUN python3 -m pip install --no-cache-dir -r backend/requirements.txt

# Copy frontend and install Node dependencies
COPY frontend/ ./frontend/
WORKDIR /app/frontend
RUN npm install

# Expose backend (Flask) and frontend (Vite) ports
EXPOSE 5000 5173

# Go back to app root
WORKDIR /app

# Start both backend and frontend in the same container
# - Backend: Flask app via manage.py on port 5000
# - Frontend: Vite dev server on port 5173
CMD ["/bin/bash", "-lc", "\
  cd /app/backend && python3 manage.py & \
  cd /app/frontend && npm run dev -- --host 0.0.0.0 --port 5173 & \
  wait \
"]
