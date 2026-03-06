# CollabMark

A real-time collaborative Markdown editor with Google OAuth, SSO (SAML 2.0 / OIDC),
Google Docs-style sharing, inline commenting, version history, org management, and
programmatic API access. Built with FastAPI, React, and CRDTs.

## Features

- **Real-time collaboration** via CRDTs (Yjs + pycrdt) with cursor presence
- **Authentication**: Google OAuth, SAML 2.0, OIDC, and API keys
- **Google Docs-style sharing**: general access levels, email-based collaborators, org-scoped ACLs
- **Organizations**: multi-tenant with SSO, admin dashboard, member management
- **Split-pane editor**: CodeMirror 6 with live Markdown preview, resizable splitter, presentation mode
- **Inline & document-level comments** with Yjs-anchored positions and reply threads
- **Version history** with line-level diffs, restore, and auto-versioning
- **Spaces (folders)** with hierarchical organization and access inheritance
- **Mermaid diagrams**, syntax-highlighted code blocks, dark mode
- **Interactive API docs** at `/api-docs` with live request execution
- **PDF and Markdown export**

## Prerequisites

- Python 3.12+
- Node.js 20+
- Docker & Docker Compose (for MongoDB and Redis)

## Quick Start

The fastest way to get running with a single command:

```bash
make install       # install backend + frontend dependencies
docker compose up -d mongodb redis   # start MongoDB and Redis
```

Then start both servers (in separate terminals):

```bash
# Terminal 1 — Backend
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

```bash
# Terminal 2 — Frontend
cd frontend
yarn dev
```

The app is available at **http://localhost:5173**. The API is at **http://localhost:8000** (Swagger docs at `/docs`).

## Step-by-Step Setup

### 1. Start infrastructure

```bash
docker compose up -d mongodb redis
```

This starts MongoDB 7 on port 27017 and Redis 7 on port 6379.

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials (see [Environment Variables](#environment-variables)).

### 3. Install dependencies

Using the Makefile (recommended):

```bash
make install
```

Or manually:

```bash
# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
yarn install
```

### 4. Run the backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

### 5. Run the frontend

```bash
cd frontend
yarn dev
```

The UI is at `http://localhost:5173`. Vite proxies `/api` and `/ws` to the backend automatically.

## Testing

### Run all tests

```bash
make test
```

This runs both backend (641 tests) and frontend (860 tests).

### Backend tests only

```bash
make test-be
```

Or directly:

```bash
cd backend
source .venv/bin/activate
python -m pytest
```

Backend tests use an in-memory MongoDB mock (`mongomock-motor`) — no running database needed.

### Frontend tests only

```bash
make test-fe
```

Or directly:

```bash
cd frontend
yarn test
```

### Watch mode (frontend)

```bash
cd frontend
yarn test:watch
```

### Test coverage

```bash
make test-cov
```

This generates coverage reports for both backend and frontend. Backend uses `pytest-cov`; frontend uses `@vitest/coverage-v8`.

You can also run them separately:

```bash
# Backend coverage
cd backend && .venv/bin/python -m pytest --cov=app --cov-report=term-missing

# Frontend coverage
cd frontend && yarn run test:coverage
```

## Linting & Formatting

### Check lint (both backend and frontend)

```bash
make lint
```

This runs:
- **Backend**: `ruff check` (pycodestyle, pyflakes, isort, bugbear, bandit security, and more)
- **Frontend**: `tsc` (TypeScript), `eslint` (React hooks, refresh), `prettier --check`

### Auto-fix lint issues

```bash
make lint-fix
```

### Format all code

```bash
make format
```

This runs:
- **Backend**: `ruff format` (Black-compatible, 120 char line width)
- **Frontend**: `prettier --write` (120 print width, double quotes, trailing commas)

### Check formatting without changes

```bash
make format-check
```

### Individual tools

```bash
# Backend lint
cd backend && .venv/bin/ruff check app/ tests/

# Backend format
cd backend && .venv/bin/ruff format app/ tests/

# Frontend lint
cd frontend && yarn run lint

# Frontend lint auto-fix
cd frontend && yarn run lint:fix

# Frontend format
cd frontend && yarn run format

# Frontend full check (tsc + eslint + prettier)
cd frontend && yarn run check
```

## Build

### Frontend production build

```bash
make build
```

Or directly:

```bash
cd frontend && yarn build
```

The output goes to `frontend/dist/`.

### Full CI pipeline

```bash
make ci
```

This runs the complete pipeline: lint, format check, all tests, and production build. Use this before committing.

## Docker

### Full stack (development)

```bash
cp .env.example .env
# Edit .env with your credentials
docker compose up --build
```

The app is available at `http://localhost:8000`.

### Production

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

## Makefile Reference

Run `make help` to see all available commands:

| Command            | Description                                      |
|--------------------|--------------------------------------------------|
| `make install`     | Install all dependencies (backend + frontend)    |
| `make lint`        | Run linters (ruff + eslint + prettier check)     |
| `make lint-fix`    | Auto-fix lint issues                             |
| `make format`      | Format all code (ruff + prettier)                |
| `make format-check`| Check formatting without changes                 |
| `make test`        | Run all tests (backend + frontend)               |
| `make test-be`     | Run backend tests only                           |
| `make test-fe`     | Run frontend tests only                          |
| `make test-cov`    | Run all tests with coverage reports              |
| `make build`       | Build frontend for production                    |
| `make ci`          | Full CI pipeline: lint + format + test + build   |
| `make clean`       | Remove build artifacts and caches                |

## Environment Variables

| Variable               | Description                            | Default / Example                       |
|------------------------|----------------------------------------|-----------------------------------------|
| `DEBUG`                | Enable debug mode                      | `true`                                  |
| `MONGODB_URL`          | MongoDB connection string              | `mongodb://localhost:27017`             |
| `MONGODB_DB_NAME`      | Database name                          | `collabmark`                            |
| `REDIS_URL`            | Redis connection string                | `redis://localhost:6379`                |
| `GOOGLE_CLIENT_ID`     | Google OAuth client ID                 | `123456.apps.googleusercontent.com`     |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret             | `GOCSPX-...`                            |
| `GOOGLE_REDIRECT_URI`  | OAuth callback URL                     | `http://localhost:8000/api/auth/google/callback` |
| `JWT_SECRET_KEY`       | JWT signing secret (32+ random chars)  | *(required in production)*              |
| `JWT_ALGORITHM`        | JWT algorithm                          | `HS256`                                 |
| `JWT_EXPIRE_MINUTES`   | JWT token lifetime in minutes          | `10080` (7 days)                        |
| `SESSION_SECRET_KEY`   | Session middleware secret              | Falls back to `JWT_SECRET_KEY`          |
| `FRONTEND_URL`         | Frontend URL for CORS and redirects    | `http://localhost:5173`                 |
| `ALLOWED_ORIGINS`      | CORS allowed origins (JSON array)      | `["http://localhost:5173","http://localhost:8000"]` |
| `SUPER_ADMIN_EMAILS`   | Emails with super admin access (JSON)  | `[]`                                    |

## Architecture

```
Browser (React + CodeMirror 6 + Yjs)
    |
    |-- REST API (/api/*) --> FastAPI --> MongoDB (Beanie ODM)
    |
    |-- WebSocket (/ws/doc/{id}) --> pycrdt-websocket --> MongoYStore
```

| Layer        | Technology                                              |
|--------------|---------------------------------------------------------|
| Backend      | Python 3.12+, FastAPI, Uvicorn, Gunicorn                |
| Database     | MongoDB 7 (Beanie ODM, Motor async driver)              |
| CRDT Server  | pycrdt + pycrdt-websocket with custom MongoDB store     |
| CRDT Client  | Yjs + y-codemirror.next + y-websocket                   |
| Frontend     | React 19, Vite 7, TypeScript 5.9, Tailwind CSS v4      |
| Editor       | CodeMirror 6 (core API + yCollab binding)               |
| Auth         | Google OAuth2, SAML 2.0, OIDC, JWT, API keys           |
| Lint (BE)    | ruff (lint + format)                                    |
| Lint (FE)    | ESLint 9 + Prettier 3                                   |
| Testing (BE) | pytest, pytest-asyncio, pytest-cov, httpx, mongomock-motor |
| Testing (FE) | Vitest 4, React Testing Library, jsdom                  |
| Deployment   | Docker, Railway, Gunicorn                               |

## Project Structure

```
collabmark/
  backend/
    app/
      auth/          # OAuth, JWT, API key, SSO (SAML/OIDC) auth
      models/        # Beanie document models (User, Document, Comment, Folder, Organization, etc.)
      routes/        # REST API endpoints (thin -- delegate to services)
      services/      # Business logic layer (document, share, version, comment, folder, org, acl)
      utils/         # Shared utilities (owner_resolver)
      ws/            # WebSocket handler (pycrdt rooms)
    tests/           # 641 backend tests
    pyproject.toml   # Ruff lint/format + pytest configuration
    requirements.txt # Python dependencies
  frontend/
    src/
      components/    # Reusable UI components (Auth, Editor, Home, Layout)
      pages/         # Route-level pages (Home, Editor, Login, Settings, Profile, ApiDocs, Admin, OrgSettings)
      hooks/         # Custom React hooks / Zustand stores
      lib/           # API client (axios), utilities
    eslint.config.js # ESLint 9 flat config
    .prettierrc      # Prettier config
    vite.config.ts   # Vite + Vitest configuration
  Makefile           # Unified lint/format/test/build/ci commands
  Dockerfile         # Multi-stage production build
  docker-compose.yml # Local dev infrastructure (MongoDB + Redis)
  docker-compose.prod.yml  # Production compose
  .env.example       # Environment variable template
  AGENT.md           # Agent reference (conventions, architecture, progress)
```

## API Endpoints

### Auth
- `GET /api/auth/google/login` -- redirect to Google OAuth
- `GET /api/auth/google/callback` -- OAuth callback, set JWT cookie
- `POST /api/auth/logout` -- clear session
- `POST /api/auth/sso/detect` -- detect SSO org by email domain
- `GET /api/auth/sso/saml/login/{org_id}` -- redirect to SAML IdP
- `POST /api/auth/sso/saml/callback` -- SAML assertion consumer service
- `GET /api/auth/sso/oidc/login/{org_id}` -- redirect to OIDC IdP
- `GET /api/auth/sso/oidc/callback` -- OIDC authorization code callback

### Documents
- `POST /api/documents` -- create document
- `GET /api/documents` -- list own documents
- `GET /api/documents/{id}` -- get document
- `PUT /api/documents/{id}` -- update document
- `DELETE /api/documents/{id}` -- soft-delete
- `POST /api/documents/{id}/restore` -- restore from trash
- `DELETE /api/documents/{id}/permanent` -- hard-delete with cleanup
- `GET /api/documents/trash` -- list trashed documents
- `GET /api/documents/shared` -- list docs shared with me
- `GET /api/documents/recent` -- list recently viewed docs

### Folders
- `POST /api/folders` -- create folder
- `GET /api/folders/{id}` -- get folder
- `PUT /api/folders/{id}` -- update folder
- `DELETE /api/folders/{id}` -- cascade soft-delete
- `POST /api/folders/{id}/restore` -- cascade restore
- `DELETE /api/folders/{id}/permanent` -- cascade hard-delete
- `GET /api/folders/contents` -- list folder contents
- `GET /api/folders/breadcrumbs` -- get breadcrumb path
- `POST /api/folders/{id}/collaborators` -- add collaborator
- `GET /api/folders/{id}/collaborators` -- list collaborators
- `DELETE /api/folders/{id}/collaborators/{user_id}` -- remove collaborator

### Sharing
- `PUT /api/documents/{id}/access` -- set general access level
- `POST /api/documents/{id}/collaborators` -- add collaborator by email
- `GET /api/documents/{id}/collaborators` -- list collaborators
- `DELETE /api/documents/{id}/collaborators/{user_id}` -- remove collaborator
- `POST /api/documents/{id}/view` -- record document view

### Versions
- `POST /api/documents/{id}/versions` -- create snapshot (deduplicated)
- `GET /api/documents/{id}/versions` -- list version timeline
- `GET /api/documents/{id}/versions/{num}` -- get version detail

### Comments
- `POST /api/documents/{id}/comments` -- create comment
- `GET /api/documents/{id}/comments` -- list comments with replies
- `POST /api/comments/{id}/reply` -- reply to comment
- `POST /api/comments/{id}/resolve` -- resolve comment
- `PATCH /api/comments/{id}/reanchor` -- update anchor offsets
- `PATCH /api/comments/{id}/orphan` -- mark as orphaned
- `DELETE /api/comments/{id}` -- delete comment

### Organizations
- `GET /api/orgs/my` -- current user's organization
- `POST /api/orgs` -- create organization (super admin)
- `GET /api/orgs` -- list all organizations (super admin)
- `GET /api/orgs/{org_id}` -- get org details
- `PUT /api/orgs/{org_id}` -- update org
- `GET /api/orgs/{org_id}/members` -- list members
- `POST /api/orgs/{org_id}/members` -- add member
- `POST /api/orgs/{org_id}/members/invite` -- invite by email
- `PATCH /api/orgs/{org_id}/members/{user_id}/role` -- change role
- `DELETE /api/orgs/{org_id}/members/{user_id}` -- remove member
- `GET /api/orgs/{org_id}/sso` -- get SSO config
- `PUT /api/orgs/{org_id}/sso` -- update SSO config

### Other
- `GET /api/users/me` -- current user profile
- `PUT /api/users/me` -- update profile
- `POST /api/keys` -- create API key
- `GET /api/keys` -- list API keys
- `DELETE /api/keys/{id}` -- revoke API key
- `WS /ws/doc/{document_id}` -- CRDT collaboration WebSocket

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

The interactive API documentation at `/api-docs` lets you test all endpoints in the browser.

## Contributing

1. Fork and clone the repository
2. Set up local development (see [Quick Start](#quick-start))
3. Create a feature branch: `git checkout -b your-name/feature-description`
4. Write tests for every function/endpoint you add
5. Ensure the full CI pipeline passes: `make ci`
6. Commit with concise messages explaining "why" not "what"
7. Open a pull request

See `AGENT.md` for detailed coding conventions, architectural decisions, and project progress.
