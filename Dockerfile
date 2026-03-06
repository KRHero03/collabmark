## Stage 1: Build the React frontend
FROM node:22-slim AS frontend-build
WORKDIR /build
ENV NODE_OPTIONS="--max-old-space-size=4096"
COPY frontend/package.json frontend/yarn.lock ./
RUN corepack enable && yarn install --frozen-lockfile
COPY frontend/ ./
RUN ./node_modules/.bin/tsc -b && ./node_modules/.bin/vite build

## Stage 2: Python backend + static assets
FROM python:3.12-slim AS runtime
WORKDIR /app

COPY backend/requirements.prod.txt .
RUN pip install --no-cache-dir -r requirements.prod.txt && rm -rf /root/.cache

COPY backend/app/ ./backend/app/
COPY --from=frontend-build /build/dist ./frontend/dist

ENV PYTHONPATH=/app/backend
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app/backend

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; import os; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",8000)}/api/health')"

EXPOSE 8000
CMD ["sh", "-c", "gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT} --workers 1 --timeout 120"]
