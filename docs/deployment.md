# Deployment Guide

This guide covers local development setup, environment configuration, and production deployment for CollabMark.

## Prerequisites

- **Python 3.12+** (backend)
- **Node.js 22+** and **yarn** (frontend)
- **MongoDB 7** (required)
- **Redis 7** (optional -- notifications disabled if unavailable)
- **MinIO** (optional -- falls back to local filesystem storage)
- **Mailpit** (optional -- local email testing)
- **Docker and Docker Compose** (recommended for running infrastructure services)

## Local Development

### Quick Start

Run one command from the project root:

```bash
make quickstart
```

This will:
1. Copy `.env.example` to `.env` if it does not already exist
2. Install backend (Python venv + pip) and frontend (yarn) dependencies
3. Start MongoDB and Redis via Docker Compose
4. Wait for MongoDB to become available

After it finishes, start the servers in two separate terminals:

```bash
# Terminal 1 -- Backend
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload

# Terminal 2 -- Frontend
cd frontend && yarn dev
```

- App: http://localhost:5173
- API: http://localhost:8000
- Swagger: http://localhost:8000/docs

### Manual Setup

1. **Copy environment file**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and configure at minimum: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `JWT_SECRET_KEY`.

2. **Install dependencies**
   ```bash
   make install
   ```
   Or manually:
   ```bash
   cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   cd frontend && yarn install
   ```

3. **Start infrastructure services**
   ```bash
   docker compose up -d mongodb redis
   ```

4. **Start the backend**
   ```bash
   cd backend && source .venv/bin/activate && uvicorn app.main:app --reload
   ```

5. **Start the frontend**
   ```bash
   cd frontend && yarn dev
   ```

6. **Verify the backend is running**
   ```bash
   curl http://localhost:8000/api/health
   ```

### Docker Compose Services

The development `docker-compose.yml` defines the following services:

| Service    | Image                  | Ports                          | Purpose                                 |
|------------|------------------------|--------------------------------|-----------------------------------------|
| `mongodb`  | `mongo:7`              | `27017:27017`                  | Primary database                        |
| `redis`    | `redis:7-alpine`       | `6379:6379`                    | Pub/sub for real-time notifications     |
| `minio`    | `minio/minio:latest`   | `9002:9000` (API), `9003:9001` (Console) | S3-compatible object storage for media  |
| `mailpit`  | `axllent/mailpit:latest`| `8025:8025` (UI), `1025:1025` (SMTP) | Local email testing (catches all mail) |
| `app`      | Built from `Dockerfile`| `8000:8000`                    | Full application (frontend + backend)   |

Persistent volumes: `mongo_data` (database), `minio_data` (uploaded files).

## Environment Variables

All variables are defined in `.env.example`. Copy it to `.env` and edit as needed.

### Database (required)

| Variable         | Default                       | Description                              |
|------------------|-------------------------------|------------------------------------------|
| `MONGODB_URL`    | `mongodb://localhost:27017`   | MongoDB connection string                |
| `MONGODB_DB_NAME`| `collabmark`                  | Database name                            |

### Redis (optional)

| Variable    | Default                   | Description                                           |
|-------------|---------------------------|-------------------------------------------------------|
| `REDIS_URL` | `redis://localhost:6379`  | Redis connection string; notifications disabled if unset or unreachable |

### Google OAuth (required)

| Variable               | Default | Description                                                        |
|------------------------|---------|--------------------------------------------------------------------|
| `GOOGLE_CLIENT_ID`     | --      | OAuth 2.0 Client ID from Google Cloud Console                     |
| `GOOGLE_CLIENT_SECRET` | --      | OAuth 2.0 Client Secret                                           |
| `GOOGLE_REDIRECT_URI`  | `http://localhost:8000/api/auth/google/callback` | OAuth callback URL (must match Google Console config) |

To configure: go to https://console.cloud.google.com/apis/credentials, create an OAuth 2.0 Client ID (Web application), and add the redirect URI.

### JWT

| Variable           | Default  | Description                                 |
|--------------------|----------|---------------------------------------------|
| `JWT_SECRET_KEY`   | --       | Secret for signing tokens (min 32 chars)    |
| `JWT_ALGORITHM`    | `HS256`  | Signing algorithm                           |
| `JWT_EXPIRE_MINUTES`| `10080` | Token lifetime in minutes (default: 7 days) |

### Frontend / CORS

| Variable          | Default                                              | Description                      |
|-------------------|------------------------------------------------------|----------------------------------|
| `FRONTEND_URL`    | `http://localhost:5173`                               | Frontend origin URL             |
| `ALLOWED_ORIGINS` | `["http://localhost:5173","http://localhost:8000"]`    | JSON array of allowed CORS origins |

### S3 / MinIO (optional)

| Variable           | Default | Description                                               |
|--------------------|---------|-----------------------------------------------------------|
| `S3_ENDPOINT_URL`  | --      | MinIO/S3 endpoint; leave empty to use local `backend/media/` directory |
| `S3_ACCESS_KEY`    | --      | S3 access key                                             |
| `S3_SECRET_KEY`    | --      | S3 secret key                                             |
| `S3_BUCKET`        | --      | Bucket name (e.g., `collabmark-media`)                    |
| `S3_REGION`        | --      | AWS region (only needed for real S3)                      |

### Notifications (optional)

| Variable                      | Default                    | Description                                |
|-------------------------------|----------------------------|--------------------------------------------|
| `NOTIFICATIONS_ENABLED`       | `true`                     | Enable/disable the notification system     |
| `NOTIFICATION_EMAIL_PROVIDER` | `smtp`                     | Email provider: `smtp` (dev) or `resend` (production) |
| `NOTIFICATION_FROM_EMAIL`     | `noreply@collabmark.local` | Sender address for notification emails     |
| `SMTP_HOST`                   | `localhost`                | SMTP server host (Mailpit for local dev)   |
| `SMTP_PORT`                   | `1025`                     | SMTP server port                           |
| `NOTIFICATION_DELAY_SECONDS`  | `10`                       | Delay before sending (batches rapid edits) |
| `RESEND_API_KEY`              | --                         | Resend API key (production only)           |

### Debug

| Variable | Default | Description                    |
|----------|---------|--------------------------------|
| `DEBUG`  | `true`  | Enable debug mode (disable in production) |

## Production Deployment (Railway)

### Overview

CollabMark uses a multi-stage Docker build and is configured for one-click deployment on Railway.

### Dockerfile Stages

1. **Stage 1 -- Frontend build** (`node:22-slim`): Installs yarn dependencies, runs TypeScript compilation and Vite build, produces static assets in `/build/dist`.
2. **Stage 2 -- Runtime** (`python:3.12-slim`): Installs Python production dependencies, copies backend code and frontend static assets, runs Gunicorn with Uvicorn workers.

### Railway Configuration

From `railway.toml`:

```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
healthcheckPath = "/api/health"
healthcheckTimeout = 60
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

Railway will build the Dockerfile, health-check against `/api/health`, and restart on failure up to 3 times.

### Required Production Environment Variables

Set these in the Railway dashboard:

- `MONGODB_URL` -- point to your managed MongoDB instance (e.g., MongoDB Atlas)
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` -- production OAuth credentials
- `GOOGLE_REDIRECT_URI` -- must use your production domain
- `JWT_SECRET_KEY` -- a strong random string (32+ characters)
- `FRONTEND_URL` -- your production frontend URL
- `ALLOWED_ORIGINS` -- JSON array including your production domain
- `DEBUG` -- set to `false`

Optional but recommended:
- `REDIS_URL` -- managed Redis for real-time notifications
- `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`, `S3_REGION` -- for file storage
- `NOTIFICATION_EMAIL_PROVIDER=resend` and `RESEND_API_KEY` -- for production email

### Gunicorn Configuration

The production server runs:

```bash
gunicorn app.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:${PORT} \
  --workers 1 \
  --timeout 120
```

The `PORT` environment variable is set automatically by Railway (default: `8000`). Adjust `--workers` based on your instance size.

### Health Check

The Dockerfile includes a built-in health check:

```
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3
```

It hits `/api/health` on the configured port. Railway also performs its own health check against the same endpoint.

## Docker Compose Production

For self-hosted production deployments, use `docker-compose.prod.yml`:

```bash
docker compose -f docker-compose.prod.yml up -d
```

### Differences from Development Compose

- All services have `restart: unless-stopped` for resilience
- No Mailpit service (use a real email provider)
- `DEBUG=false` is set on the app container
- MinIO credentials are pulled from environment variables (`S3_ACCESS_KEY`, `S3_SECRET_KEY`) with defaults
- MinIO ports use standard mapping (`9000:9000`, `9001:9001`) instead of offset ports

### Services

| Service   | Image                 | Ports                        | Notes                    |
|-----------|-----------------------|------------------------------|--------------------------|
| `mongodb` | `mongo:7`             | `27017:27017`                | Persistent volume        |
| `redis`   | `redis:7-alpine`      | `6379:6379`                  | In-memory, no persistence|
| `minio`   | `minio/minio:latest`  | `9000:9000`, `9001:9001`     | Persistent volume        |
| `app`     | Built from Dockerfile | `8000:8000`                  | Depends on all services  |

### Production Checklist

1. Set strong, unique values for `JWT_SECRET_KEY`, `S3_ACCESS_KEY`, and `S3_SECRET_KEY` in `.env`
2. Configure Google OAuth credentials with the correct production redirect URI
3. Set `DEBUG=false`
4. Set `FRONTEND_URL` and `ALLOWED_ORIGINS` to your production domain
5. Configure a real email provider (`resend`) or disable notifications
6. Back up the `mongo_data` and `minio_data` volumes regularly
