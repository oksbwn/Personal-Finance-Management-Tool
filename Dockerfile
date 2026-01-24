# Stage 1: Build Frontend
FROM node:20 AS frontend-build
WORKDIR /app
COPY version.json ./
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
ARG VITE_APP_BUILD=0000
ENV VITE_APP_BUILD=$VITE_APP_BUILD
RUN npm run build

# Stage 2: Final Image
FROM python:3.11-slim

# 1. System Installations
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Python Dependency Installation
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 3. Static Infrastructure Configs (Change infrequently)
COPY frontend/nginx.conf /etc/nginx/sites-available/default
# Create entrypoint.sh inline to avoid CRLF/BOM issues
RUN printf "#!/bin/bash\nnginx\npython run_backend.py\n" > entrypoint.sh && chmod +x entrypoint.sh

# 4. Application Code (Changes frequently)
COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html
COPY backend/ ./backend/
COPY run_backend.py ./
COPY version.json ./

# Environment variables
ENV DATABASE_URL="duckdb:////data/family_finance_v3.duckdb"
ENV PYTHONPATH="/app"

EXPOSE 80

ENTRYPOINT ["./entrypoint.sh"]
