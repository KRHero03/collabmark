---
name: e2e-testing
description: Full end-to-end testing procedure for CollabMark. Covers local infrastructure setup, backend/frontend verification, CLI installation in an isolated venv, Playwright MCP browser-based UI verification, and validation of all major features (sync, conflicts, doctor, offline resilience). Use before major releases, after blocker fixes, or when the user asks to "test everything end-to-end".
---

# E2E Testing Procedure for CollabMark

Run this procedure to validate that all components work together in a real local environment. This skill uses **shell commands** for infrastructure/CLI and the **Playwright MCP** (`user-playwright`) for browser-based UI verification.

## Prerequisites

- MongoDB installed (`brew install mongodb-community` or Docker)
- Redis installed (`brew install redis` or Docker)
- Python 3.12+ and Node.js 20+
- Backend and CLI virtualenvs set up (`make install`)
- Playwright MCP server enabled in Cursor (server name: `user-playwright`)

## Phase 1: Start Infrastructure

```bash
# Start MongoDB (if not already running)
mkdir -p /tmp/mongod_data
mongod --dbpath /tmp/mongod_data --logpath /tmp/mongod.log &
sleep 2
mongosh --eval "db.runCommand({ping:1})" --quiet  # Should print { ok: 1 }

# Start Redis (if not already running)
redis-server --daemonize yes
redis-cli ping  # Should print PONG
```

## Phase 2: Start Application Servers

```bash
# Terminal 1 — Backend (background it with block_until_ms: 0)
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend (background it with block_until_ms: 0)
cd frontend && yarn dev

# Verify both are up
curl -s http://localhost:8000/api/health | python3 -m json.tool
# Should show: { "status": "ok", "service": "collabmark", "version": "1.0.0" }

curl -s -o /dev/null -w "%{http_code}" http://localhost:5173
# Should print: 200
```

## Phase 3: Run Unit Tests

All tests must pass before proceeding to E2E verification.

```bash
# Backend (1044+ tests expected)
cd backend && .venv/bin/python -m pytest tests/ --tb=short -q

# CLI (410+ tests expected)
cd cli && .venv/bin/python -m pytest tests/ --tb=short -q

# Full CI pipeline (optional)
make ci
```

## Phase 4: CLI Installation in Isolated Venv

Install the CLI from local source into an isolated virtualenv. This validates that packaging, entry points, and dependencies all work correctly.

The workspace root is the directory that contains `backend/`, `frontend/`, `cli/`. Determine it from the current working directory or from the user's workspace path.

```bash
# Set WORKSPACE_ROOT to the collabmark repo root
WORKSPACE_ROOT=/Users/krank/Desktop/vanity-identifier-impl/collabmark

# Create a clean isolated environment
rm -rf /tmp/collabmark-e2e
mkdir -p /tmp/collabmark-e2e
cd /tmp/collabmark-e2e
python3 -m venv .venv
source .venv/bin/activate

# Install CLI from local source
pip install "$WORKSPACE_ROOT/cli"
```

**Verification checklist** (run each and confirm output):

```bash
# 1. Confirm the binary is in the venv
which collabmark
# Expected: /tmp/collabmark-e2e/.venv/bin/collabmark

# 2. Version matches cli/src/collabmark/__init__.py
collabmark --version
# Expected: collabmark, version 0.2.0  (or whatever __version__ is set to)

# 3. All commands are registered
collabmark --help
# Expected output must list ALL of these commands:
#   login, start, stop, status, list, logs, clean, conflicts, doctor, init

# 4. Doctor runs without crashing (failures are expected pre-login)
export COLLABMARK_API_URL=http://localhost:8000
export COLLABMARK_HOME=/tmp/collabmark-e2e/.collabmark
collabmark doctor
# Expected: ✗ Config directory, ✗ Credentials, ✓ Keyring, ✓ No active syncs
```

If any of these fail, stop and fix before continuing.

## Phase 5: Verify CLI Features

Each command should execute without errors:

```bash
export COLLABMARK_API_URL=http://localhost:8000
export COLLABMARK_HOME=/tmp/collabmark-e2e/.collabmark

# 1. Conflicts — no conflicts initially
collabmark conflicts /tmp/collabmark-e2e
# Expected: "No conflict files found."

# 2. Conflict detection — create a sidecar file and re-check
touch "/tmp/collabmark-e2e/notes.conflict.2026-01-01_000000.md"
collabmark conflicts /tmp/collabmark-e2e
# Expected: Table showing 1 conflict file

# 3. Start --verbose flag exists
collabmark start -v --help
# Expected: Shows -v/--verbose option

# 4. Start --doc flag exists
collabmark start --doc --help
# Expected: Shows --doc option
```

## Phase 6: Playwright MCP — Browser-Based UI Verification

Use the **Playwright MCP** (server: `user-playwright`) via `CallMcpTool` to drive a real browser against the running local servers. This validates that the frontend renders correctly, the backend API docs load, and the login flow is wired up.

### Available Playwright MCP tools

All calls use `CallMcpTool` with `server: "user-playwright"`. Key tools:

| toolName | Purpose |
|----------|---------|
| `browser_navigate` | Navigate to a URL. Args: `{ "url": "..." }` |
| `browser_snapshot` | Capture accessibility tree (use this to find `ref` values for clicks). Args: `{}` |
| `browser_click` | Click an element. Args: `{ "element": "description", "ref": "refFromSnapshot" }` |
| `browser_take_screenshot` | Capture a visual screenshot. Args: `{ "type": "png" }` |
| `browser_wait_for` | Wait for text or time. Args: `{ "text": "..." }` or `{ "time": 3 }` |
| `browser_fill_form` | Fill form fields. Args: `{ "fields": [...] }` |
| `browser_type` | Type text into focused element. Args: `{ "text": "...", "ref": "..." }` |
| `browser_close` | Close the browser. Args: `{}` |

### 6a. Verify Landing Page

```
CallMcpTool  server: "user-playwright"  toolName: "browser_navigate"
  arguments: { "url": "http://localhost:5173" }

CallMcpTool  server: "user-playwright"  toolName: "browser_wait_for"
  arguments: { "text": "CollabMark" }

CallMcpTool  server: "user-playwright"  toolName: "browser_snapshot"
  arguments: {}
```

**Check:** The snapshot should contain:
- The text "CollabMark" (app name / heading)
- A "Sign in with Google" or "Login" button/link

Take a screenshot for evidence:

```
CallMcpTool  server: "user-playwright"  toolName: "browser_take_screenshot"
  arguments: { "type": "png", "filename": "e2e-landing-page.png" }
```

### 6b. Verify Swagger / API Docs

```
CallMcpTool  server: "user-playwright"  toolName: "browser_navigate"
  arguments: { "url": "http://localhost:8000/docs" }

CallMcpTool  server: "user-playwright"  toolName: "browser_wait_for"
  arguments: { "text": "Swagger" }

CallMcpTool  server: "user-playwright"  toolName: "browser_snapshot"
  arguments: {}
```

**Check:** The snapshot should contain Swagger UI elements (endpoint paths like `/api/documents`, `/api/auth`).

```
CallMcpTool  server: "user-playwright"  toolName: "browser_take_screenshot"
  arguments: { "type": "png", "filename": "e2e-swagger-docs.png" }
```

### 6c. Verify Login Flow (Pre-Auth)

Navigate to the login page and confirm the OAuth button is rendered:

```
CallMcpTool  server: "user-playwright"  toolName: "browser_navigate"
  arguments: { "url": "http://localhost:5173/login" }

CallMcpTool  server: "user-playwright"  toolName: "browser_snapshot"
  arguments: {}
```

**Check:** Snapshot should show a Google OAuth sign-in button.

### 6d. Authenticated Flows (if OAuth is configured)

If the user has completed `collabmark login` and has a valid session:

1. Navigate to `http://localhost:5173` — should redirect to dashboard
2. Snapshot and verify folder list or document list is visible
3. Click "New Document" (find ref from snapshot)
4. Wait for editor to load
5. Type sample text via `browser_type`
6. Take a screenshot of the editor
7. Navigate back to document list, verify the new document appears

### 6e. Close browser

```
CallMcpTool  server: "user-playwright"  toolName: "browser_close"
  arguments: {}
```

## Phase 7: Verify Blob Storage Fallback

If MinIO/S3 is not available (S3_ENDPOINT_URL is empty in .env):

```bash
# Backend should start without S3
# Uploads should write to backend/media/ instead
# /media/* endpoint should serve files from local disk
```

## Phase 8: Auth + Sync (Manual, if OAuth configured)

```bash
collabmark login
# Opens browser for OAuth flow
# After login: collabmark doctor should show ✓ Credentials

collabmark start -p /tmp/collabmark-e2e/sync-test
# Select a folder, verify files sync down
# Edit a local .md file, verify push
# Edit on web, verify pull (real-time via persistent WebSocket)

collabmark status
collabmark stop
```

## Phase 9: Cleanup

```bash
rm -rf /tmp/collabmark-e2e
# Stop background services if you started them:
pkill mongod
redis-cli shutdown
```

## Key Checks Summary

| # | Check | Tool | How to verify |
|---|-------|------|--------------|
| 1 | Backend starts | Shell | `curl localhost:8000/api/health` returns `{"status": "ok"}` |
| 2 | Frontend starts | Shell | `curl -o /dev/null -w "%{http_code}" localhost:5173` returns 200 |
| 3 | Backend tests pass | Shell | `pytest tests/` -- 1044+ passed |
| 4 | CLI tests pass | Shell | `pytest tests/` -- 410+ passed |
| 5 | CLI installs in venv | Shell | `which collabmark` points to venv, `collabmark --version` matches `__init__.py` |
| 6 | CLI commands registered | Shell | `collabmark --help` lists login, start, stop, status, list, logs, clean, conflicts, doctor, init |
| 7 | Doctor command | Shell | `collabmark doctor` runs, shows keyring + config checks |
| 8 | Conflicts command | Shell | `collabmark conflicts` finds `.conflict` files, shows table |
| 9 | Verbose flag | Shell | `collabmark start -v --help` shows `-v/--verbose` |
| 10 | Landing page renders | Playwright MCP | `browser_navigate` to `:5173`, snapshot contains "CollabMark" |
| 11 | Login button visible | Playwright MCP | Snapshot of landing/login page shows Google OAuth button |
| 12 | Swagger docs load | Playwright MCP | `browser_navigate` to `:8000/docs`, snapshot contains API endpoints |
| 13 | Screenshots captured | Playwright MCP | `browser_take_screenshot` saves `e2e-landing-page.png`, `e2e-swagger-docs.png` |
| 14 | S3 fallback | Shell | With empty `S3_ENDPOINT_URL`, uploads go to `backend/media/` |
| 15 | No local .collabmark | Shell | Verify no `.collabmark/` dirs created inside sync directories |
| 16 | Persistent WS | Shell | `collabmark start --doc` uses real-time WebSocket connection |
