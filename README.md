# CollabMark

**Stop re-teaching your AI agent the same rules.**

[![PyPI](https://img.shields.io/pypi/v/collabmark)](https://pypi.org/project/collabmark/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Your team's AI agents keep learning the same lessons from scratch. Developer A's Cursor learns that you use Pydantic v2 validators. Developer B's Claude has no idea and makes the same mistakes. A new hire's Copilot starts from zero.

CollabMark fixes this. Write your team's conventions once, and every developer's AI agent reads the latest version automatically.

## The Problem

| Without CollabMark | With CollabMark |
|---|---|
| Developer A teaches Cursor your conventions | Write conventions once in CollabMark |
| Developer B's agent has no idea | Every agent reads the latest version |
| New hire's AI makes solved mistakes | New hire's agent starts fully informed |
| CLAUDE.md gets stale immediately | Changes sync to all agents in seconds |
| Copy-paste across machines | Background CLI keeps everything in sync |

## Get Started in 60 Seconds

```bash
pip install collabmark
collabmark login
collabmark start
```

That's it. Your team's coding standards, architecture decisions, and project context now sync to `.cursor/rules/`, `CLAUDE.md`, and `AGENTS.md` automatically.

## How It Works

1. **Write conventions on the web** — Your team collaborates on living documents: coding standards, architecture decisions, project context. Real-time editing, version history, inline comments.

2. **CLI syncs to local agent context** — The `collabmark start` daemon watches for changes and syncs your team's documents to local agent context files. Every AI tool reads them natively.

3. **Every agent stays informed** — When anyone updates a convention, every team member's Cursor, Claude, and Copilot know about it within seconds — no copy-pasting files.

## Features

- **Team context sync** — conventions, standards, and decisions synced to every developer's AI agent
- **Works with any AI agent** — Cursor (.cursor/rules/), Claude (CLAUDE.md), Copilot (AGENTS.md), and more
- **Real-time collaboration** — live editing with cursor presence, powered by CRDTs (Yjs + pycrdt)
- **CLI sync tool** — background daemon with bidirectional CRDT sync (`pip install collabmark`)
- **Full version history** — every convention change tracked, diffed, and restorable
- **Enterprise auth** — Google OAuth, SAML 2.0, OIDC, and API keys
- **Folders & sharing** — organize docs into folders, share with fine-grained permissions
- **Inline comments** — leave feedback on specific text with threaded replies
- **Beautiful Markdown** — Mermaid diagrams, syntax-highlighted code, dark mode
- **Interactive API docs** — test all endpoints live at `/api-docs`

## CLI Reference

| Command | Description |
|---------|-------------|
| `collabmark login` | Authenticate via browser (credentials stored in OS keychain) |
| `collabmark start` | Start syncing (foreground or `--daemon`) |
| `collabmark start <link>` | Join a shared folder by link |
| `collabmark status` | Show sync state (global or per-project) |
| `collabmark list` | List all active/stopped syncs across projects |
| `collabmark stop` | Stop sync (interactive, `--all`, or `--path`) |
| `collabmark logs` | View per-project logs (`--all-syncs` for interleaved view) |
| `collabmark clean` | Remove stale registry entries |

See [`cli/README.md`](cli/README.md) for the full reference.

## Self-Host / Development Setup

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker & Docker Compose (for MongoDB and Redis)

### Quick Start

```bash
make install                         # install backend + frontend deps
docker compose up -d mongodb redis   # start MongoDB and Redis
```

Then start both servers:

```bash
# Terminal 1 — Backend
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload

# Terminal 2 — Frontend
cd frontend && yarn dev
```

App: **http://localhost:5173** | API: **http://localhost:8000** | Swagger: **http://localhost:8000/docs**

### Environment Variables

```bash
cp .env.example .env
```

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URL` | MongoDB connection string | `mongodb://localhost:27017` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | *(required)* |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | *(required)* |
| `JWT_SECRET_KEY` | JWT signing secret (32+ random chars) | *(required in production)* |
| `FRONTEND_URL` | Frontend URL for CORS and redirects | `http://localhost:5173` |

See `.env.example` for all variables.

## Testing

```bash
make test       # Run all tests (backend + frontend + CLI)
make test-be    # Backend only
make test-fe    # Frontend only
make test-cov   # With coverage reports
make ci         # Full pipeline: lint + format + test + build
```

## Architecture

```
Browser (React + CodeMirror 6 + Yjs)             CLI (Python + pycrdt)
    |                                                |
    |-- REST API (/api/*) --> FastAPI --> MongoDB     |-- REST API (metadata, auth)
    |                                                |
    |-- WebSocket (/ws/doc/{id}) -+- pycrdt-websocket --> MongoYStore
                                  |
                                  +-- CLI CRDT sync (bidirectional)
```

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+, FastAPI, Uvicorn, Gunicorn |
| Database | MongoDB 7 (Beanie ODM, Motor async driver) |
| CRDT | pycrdt + pycrdt-websocket (server), Yjs + y-websocket (client) |
| Frontend | React 19, Vite 7, TypeScript 5.9, Tailwind CSS v4 |
| Editor | CodeMirror 6 with yCollab binding |
| Auth | Google OAuth2, SAML 2.0, OIDC, JWT, API keys |
| CLI | Python 3.12+, Click, Rich, httpx, pycrdt, watchdog |
| Deployment | Docker, Railway, GitHub Actions CI/CD |

## Project Structure

```
collabmark/
  backend/
    app/
      auth/       # OAuth, JWT, API key, SSO (SAML/OIDC) auth
      models/     # Beanie document models
      routes/     # REST API endpoints
      services/   # Business logic layer
      ws/         # WebSocket handler (pycrdt rooms)
    tests/        # Backend tests
  frontend/
    src/
      components/ # Reusable UI components
      pages/      # Route-level pages
      hooks/      # Custom hooks / Zustand stores
      lib/        # API client, utilities
  cli/
    src/collabmark/  # CLI package (commands/, lib/)
    tests/           # CLI tests
  Makefile           # Unified commands
  Dockerfile         # Multi-stage production build
  docker-compose.yml # Local dev (MongoDB + Redis)
```

## API Key Access

Generate an API key from **Settings** in the web UI. Use it via the `X-API-Key` header:

```bash
curl -H "X-API-Key: cm_your_key_here" http://localhost:8000/api/documents
```

Interactive API documentation at `/api-docs` lets you test all endpoints in the browser.

## Contributing

1. Fork and clone the repository
2. Set up local development (see [Quick Start](#quick-start))
3. Create a feature branch: `git checkout -b your-name/feature-description`
4. Write tests for every function/endpoint you add
5. Ensure the full CI pipeline passes: `make ci`
6. Open a pull request

See `AGENT.md` for detailed coding conventions, architectural decisions, and project progress.

## License

MIT
