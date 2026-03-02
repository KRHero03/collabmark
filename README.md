# CollabMark -- Collaborative Markdown Editor

A real-time collaborative Markdown editor with Google OAuth sign-in, Google Docs-style sharing,
inline commenting, version history, and programmatic API access. Built for teams that work
in Markdown and need a live preview, concurrent editing, and fine-grained access control.

## Features

- **Real-time collaboration** via CRDTs (Yjs + pycrdt) -- up to 200 concurrent users per document
- **Google OAuth sign-in** for authentication
- **Google Docs-style sharing** with general access (`restricted`, `anyone with link can view/edit`) and email-based collaborators
- **Split-pane editor** with CodeMirror 6 (left) and live Markdown preview (right)
- **Resizable panes** with a draggable splitter (persisted in localStorage)
- **Debounced preview** that only re-renders after 1.5s of inactivity (Overleaf-style)
- **Presentation mode** that hides the editor and centers the preview full-screen
- **Mermaid diagram support** rendered as inline SVGs with dark mode theming
- **Syntax-highlighted code blocks** via highlight.js (auto-switches in dark mode)
- **Inline & document-level comments** with Yjs-anchored positions and single-depth replies
- **Version history** with author attribution and read-only snapshot preview
- **PDF and Markdown export**
- **API key access** for programmatic CRUD (create, read, update, delete documents)
- **Interactive API docs** at `/api-docs` with live "Try it" panels
- **Dark mode** with full theming support

## Quick Start (Local Development)

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker & Docker Compose (for MongoDB and Redis)

### 1. Start infrastructure

```bash
docker compose up -d mongodb redis
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials (see [Environment Variables](#environment-variables) below).

### 3. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`. Interactive Swagger docs at `http://localhost:8000/docs`.

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI is available at `http://localhost:5173`. The Vite dev server proxies `/api` and `/ws` to the backend.

### 5. Run tests

Backend:

```bash
cd backend && pytest -v
```

Frontend:

```bash
cd frontend && npx vitest run
```

## Environment Variables

| Variable                 | Description                          | Example                              |
|--------------------------|--------------------------------------|--------------------------------------|
| `MONGODB_URL`            | MongoDB connection string            | `mongodb://localhost:27017`          |
| `MONGODB_DB`             | Database name                        | `collabmark`                         |
| `REDIS_URL`              | Redis connection string              | `redis://localhost:6379`             |
| `GOOGLE_CLIENT_ID`       | Google OAuth client ID               | `123456.apps.googleusercontent.com`  |
| `GOOGLE_CLIENT_SECRET`   | Google OAuth client secret           | `GOCSPX-...`                         |
| `JWT_SECRET`             | JWT signing secret                   | (random string, 32+ chars)           |
| `BASE_URL`               | Public URL for OAuth redirects       | `http://localhost:5173`              |

## Architecture

```
Browser (React + CodeMirror 6 + Yjs)
    |
    |-- REST API (/api/*) --> FastAPI --> MongoDB (Beanie ODM)
    |
    |-- WebSocket (/ws/doc/{id}) --> pycrdt-websocket --> MongoYStore
```

- **Backend**: Python 3.12+ / FastAPI / Uvicorn / Gunicorn
- **Database**: MongoDB 7 (Beanie ODM, Motor async driver)
- **CRDT Server**: pycrdt + pycrdt-websocket with custom MongoDB store
- **CRDT Client**: Yjs + y-codemirror.next + y-websocket
- **Frontend**: React 19 / Vite 7 / TypeScript 5.9 / Tailwind CSS v4
- **Editor**: CodeMirror 6 (core API + yCollab binding)
- **Auth**: Google OAuth2 (authlib) / JWT sessions (python-jose) / API keys
- **Message Bus**: Redis (pub/sub for horizontal WebSocket scaling)
- **Testing**: pytest + httpx (backend), Vitest + React Testing Library (frontend)

## Project Structure

```
collabmark/
  backend/
    app/
      auth/          # OAuth, JWT, API key auth dependencies
      models/        # Beanie document models (User, Document, Comment, etc.)
      routes/        # REST API endpoints (thin -- delegate to services)
      services/      # Business logic layer
      ws/            # WebSocket handler (pycrdt rooms)
    tests/           # 103 backend tests
  frontend/
    src/
      components/    # Reusable UI components (Auth, Editor, Home, Layout, Settings)
      pages/         # Route-level pages (Home, Editor, Login, Settings, Profile, ApiDocs)
      hooks/         # Custom React hooks (useAuth, useDocuments, useYjsProvider, etc.)
      lib/           # API client (axios), utilities
  Dockerfile         # Multi-stage build (frontend + backend + supervisord + MongoDB)
  docker-compose.yml # Local dev: MongoDB + Redis
  fly.toml           # Fly.io deployment config
  .env.example       # Environment variable template
  agent.md           # AI agent reference (conventions, progress, architecture)
```

## Docker (Full Stack)

```bash
cp .env.example .env
# Edit .env with your credentials
docker compose up --build
```

The app is available at `http://localhost:8000`.

## Deployment (Fly.io)

The Docker image bundles MongoDB using `supervisord` so everything runs in a single container.

```bash
fly launch --copy-config --no-deploy
fly secrets set GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... JWT_SECRET=...
fly deploy
```

## API Key Access

Generate an API key from **Settings** in the web UI. Use it via the `X-API-Key` header:

```bash
# List your documents
curl -H "X-API-Key: cm_your_key_here" http://localhost:8000/api/documents

# Create a document
curl -X POST -H "X-API-Key: cm_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{"title": "My Doc", "content": "# Hello"}' \
  http://localhost:8000/api/documents

# Update a document
curl -X PUT -H "X-API-Key: cm_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{"content": "# Updated content"}' \
  http://localhost:8000/api/documents/{doc_id}
```

The interactive API documentation page at `/api-docs` lets you test all endpoints directly in the browser.

## Contributing

1. Fork and clone the repository
2. Set up local development (see Quick Start above)
3. Create a feature branch: `git checkout -b your-name/feature-description`
4. Write tests for every function/endpoint you add
5. Ensure all tests pass: `cd backend && pytest -v && cd ../frontend && npx vitest run`
6. Commit with concise messages explaining "why" not "what"
7. Open a pull request

Refer to `agent.md` for detailed coding conventions, architectural decisions, and project progress.
