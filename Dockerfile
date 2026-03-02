## Stage 1: Build the React frontend
FROM node:22-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-optional
COPY frontend/ ./
RUN ./node_modules/.bin/tsc -b && ./node_modules/.bin/vite build

## Stage 2: Python backend + static assets
FROM python:3.12-slim AS runtime
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-build /build/dist ./frontend/dist

ENV PYTHONPATH=/app/backend
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

EXPOSE 8000
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "1", \
     "--timeout", "120"]
