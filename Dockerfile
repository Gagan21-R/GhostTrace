# Multi-stage build: compile the React frontend, then run FastAPI serving both API and UI.
FROM node:20.18-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements.txt backend/requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-ml.txt
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist
RUN useradd -m evx && mkdir -p data && chown -R evx /app
EXPOSE 8000
# Hosts pass the port in $PORT (Render) - default 8000 locally. A mounted disk (Render) arrives owned by root, so the
# container fixes ownership of the data folder, then drops to the unprivileged "evx" user before starting the app.
CMD ["sh", "-c", "mkdir -p /app/backend/data && chown -R evx /app/backend/data && exec setpriv --reuid=evx --regid=evx --init-groups uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=*"]
