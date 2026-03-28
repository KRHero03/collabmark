# CLI Reference

The CollabMark CLI keeps local markdown files in sync with your team's CollabMark cloud workspace. Sync is bidirectional, real-time, and powered by CRDTs (the same conflict-free protocol used by the web editor).

## Installation

```bash
pip install collabmark
collabmark --version
```

For development:

```bash
cd cli
pip install -e ".[dev]"
```

## Commands

### `collabmark login`

Authenticate with CollabMark. Opens your browser for one-click Google/SSO login. Credentials are stored securely in your OS keychain via `keyring`.

```bash
collabmark login                     # Browser login (recommended)
collabmark login --api-key <KEY>     # API key fallback (headless environments)
```

**Auth flow:** Browser opens `/cli-login` page -> user authenticates -> backend issues auth code -> CLI exchanges code for JWT -> JWT traded for persistent API key -> key stored in OS keychain.

### `collabmark logout`

Remove stored credentials from the OS keychain and delete `~/.collabmark/credentials.json`.

```bash
collabmark logout
```

### `collabmark init`

Link a local directory to a cloud folder. Configuration is stored centrally in `~/.collabmark/projects/`. After init, use `start` to begin syncing.

```bash
collabmark init                      # Interactive folder picker
collabmark init <share-link>         # Join a shared folder by link
collabmark init -p ~/notes           # Init a specific directory
```

### `collabmark start`

Begin syncing markdown files. Performs an initial sync, then watches for changes on both sides. Content is synced via CRDT WebSocket for real-time bidirectional updates.

```bash
collabmark start                     # Sync current dir, choose folder interactively
collabmark start <share-link>        # Join a shared folder by link
collabmark start -d                  # Run as a background daemon
collabmark start -p ~/notes          # Sync a specific directory
collabmark start --interval 30       # Poll every 30 seconds (default: 10s)
collabmark start --doc <id>          # Sync a single document
collabmark start --doc <id> -p f.md  # Sync a single doc to a specific file
collabmark start -v                  # Verbose (DEBUG) logging
```

**Daemon mode:** Use `-d` to run in the background. PID files are stored at `~/.collabmark/pids/{folder_id}.pid`. Stop with `collabmark stop`.

### `collabmark stop`

Gracefully stop sync processes.

```bash
collabmark stop                      # Stop current project or choose interactively
collabmark stop --all                # Stop all running syncs
collabmark stop --path ~/notes       # Stop a specific project
```

### `collabmark status`

Show the current sync state. From a project directory, shows detailed project info. Otherwise, shows a global overview.

```bash
collabmark status                    # Project-specific or global view
collabmark status -p ~/notes         # Check a specific project
```

### `collabmark list`

List all registered syncs across all projects.

```bash
collabmark list
```

Shows: local path, cloud folder, status (running/stopped), PID, last sync time, error status.

### `collabmark logs`

View structured sync log output. Each project has its own log file at `~/.collabmark/logs/{folder_id}.log`.

```bash
collabmark logs                      # Current project logs (last 50)
collabmark logs -n 100               # Last 100 entries
collabmark logs -f                   # Follow in real time
collabmark logs --folder <id>        # Logs for a specific cloud folder
collabmark logs --all-syncs          # Interleaved logs from all syncs
```

### `collabmark conflicts`

List unresolved sync conflict files (files matching `*.conflict.*.md`).

```bash
collabmark conflicts                 # Check current directory
collabmark conflicts /path/to/dir    # Check specific directory
```

### `collabmark doctor`

Run health diagnostics: checks credentials, server connectivity, sync health.

```bash
collabmark doctor
```

Checks: config directory exists, credentials present, keyring accessible, server reachable, no stale syncs.

### `collabmark clean`

Remove stale entries from the sync registry.

```bash
collabmark clean                     # Interactive selection
collabmark clean --all               # Remove all stopped entries
collabmark clean --force             # Remove all entries (including running)
```

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `COLLABMARK_API_URL` | Override API server URL | `https://web-production-5e1bc.up.railway.app` |
| `COLLABMARK_FRONTEND_URL` | Override frontend URL | `https://web-production-5e1bc.up.railway.app` |
| `COLLABMARK_HOME` | Override global config directory | `~/.collabmark` |
| `COLLABMARK_API_KEY` | Provide API key directly (skips keychain) | — |

## Configuration Storage

All configuration is stored centrally under `~/.collabmark/`:

| Path | Purpose |
|------|---------|
| `~/.collabmark/projects/{folder_id}/config.json` | Linked cloud folder, server URL, user info |
| `~/.collabmark/projects/{folder_id}/sync.json` | Per-file sync state (hashes, doc IDs) |
| `~/.collabmark/projects/{folder_id}/pending.json` | Queued failed sync actions for retry |
| `~/.collabmark/projects/{folder_id}/trash/` | Files removed by cloud-side deletions |
| `~/.collabmark/registry.json` | Centralized sync registry (all projects) |
| `~/.collabmark/logs/{folder_id}.log` | Per-project structured JSON logs (10MB max, rotated) |
| `~/.collabmark/pids/{folder_id}.pid` | Daemon PID files |
| `~/.collabmark/credentials.json` | Non-sensitive login metadata (email, name) |
| OS keychain | API key (encrypted, via `keyring`) |

## Sync Protocol

### Three-Way Reconciliation

1. **Local scan** — finds all `.md` files recursively (ignoring hidden directories)
2. **Cloud scan** — fetches the full folder tree in one `GET /api/folders/{id}/tree` call
3. **Reconcile** — compares local files, the last-known sync state (`sync.json`), and cloud documents

| Local Changed | Cloud Changed | Action |
|--------------|---------------|--------|
| New file | — | PUSH_NEW (create doc on cloud) |
| — | New doc | PULL_NEW (download to local) |
| Modified | Same | PUSH_UPDATE (overwrite cloud) |
| Same | Modified | PULL_UPDATE (overwrite local) |
| Modified | Modified | CONFLICT (neither overwritten) |
| Deleted | Same | DELETE_REMOTE (soft-delete on cloud) |
| Same | Deleted | DELETE_LOCAL (remove local file) |

### CRDT Sync

Content is pushed/pulled via WebSocket using pycrdt (the same CRDT library the server uses). This means edits merge correctly with concurrent web users — no manual conflict resolution needed for real-time changes.

For single-document sync (`--doc` mode), a persistent WebSocket connection provides real-time bidirectional updates without polling.

### Content Hashing

SHA-256 hashes are used to detect changes. Each file's hash is stored in `sync.json` after every successful sync. A file is considered "changed" when its current hash differs from the stored hash.

## Credential Security

- API keys are stored in the OS keychain (macOS Keychain, Linux Secret Service, Windows Credential Locker) via the `keyring` library
- Only non-sensitive metadata (email, name) is stored on disk in `credentials.json`
- `credentials.json` is created with `0o600` permissions (user read/write only)
- API keys are masked in log output (first 6 + last 4 characters shown)
