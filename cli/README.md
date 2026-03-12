# CollabMark CLI

Keep your local markdown files in sync with your team's CollabMark cloud
workspace — bidirectionally and in real time.

## Installation

```bash
cd cli
pip install -e ".[dev]"
collabmark --version
```

## Quick Start

```bash
# Step 1: Log in (opens your browser for one-click authentication)
collabmark login

# Step 2: Start syncing the current directory
collabmark start

# That's it! Your .md files are now synced with CollabMark.
```

Run `collabmark` with no arguments for a friendly getting-started guide.

## Commands

### `collabmark login`

Authenticate with CollabMark. Opens your browser for a one-click Google/SSO
login. Credentials are stored securely in your OS keychain.

```bash
collabmark login                     # Browser login (recommended)
collabmark login --api-key <KEY>     # API key fallback (headless environments)
```

### `collabmark logout`

Remove stored credentials from the OS keychain.

```bash
collabmark logout
```

### `collabmark init`

Set up the current directory for syncing. Creates a `.collabmark/` config folder
and links to a cloud folder. After init, use `start` to begin syncing.

```bash
collabmark init                      # Interactive folder picker
collabmark init <share-link>         # Join a shared folder by link
```

### `collabmark start`

Begin syncing markdown files. Performs an initial sync, then watches for
changes on both sides.

```bash
collabmark start                     # Sync current dir, choose folder interactively
collabmark start <share-link>        # Join a shared folder by link
collabmark start -d                  # Run as a background daemon
collabmark start -p ~/notes          # Sync a specific directory
collabmark start --interval 30       # Poll every 30 seconds (default: 10s)
```

### `collabmark status`

Show the current sync state — linked folder, number of synced files, and
whether the background daemon is running.

```bash
collabmark status
collabmark status -p ~/notes
```

### `collabmark stop`

Gracefully stop the background sync daemon.

```bash
collabmark stop
```

### `collabmark logs`

View structured sync log output.

```bash
collabmark logs                      # Last 50 entries
collabmark logs -n 100               # Last 100 entries
collabmark logs -f                   # Follow in real time (like tail -f)
```

## How Sync Works

1. **Local scan** — finds all `.md` files recursively (ignoring `.collabmark/`).
2. **Cloud scan** — fetches the full folder tree from CollabMark in one API call.
3. **Three-way reconciliation** — compares local files, the last-known sync state
   (`.collabmark/sync.json`), and cloud documents to determine what changed where.
4. **Action execution** — pushes new/updated files to cloud, pulls new/updated
   documents locally, handles deletions, and flags conflicts.
5. **Continuous watch** — uses OS filesystem events (debounced) plus periodic
   cloud polling to keep both sides in sync.

### Conflict Resolution

When the same file changes both locally and on the cloud between sync cycles,
it is flagged as a **conflict**. Neither side is overwritten. The conflict is
logged and shown in `collabmark logs`.

## Configuration

All per-project configuration lives in `.collabmark/` at the root of your
synced directory:

| File              | Purpose                                      |
|-------------------|----------------------------------------------|
| `config.json`     | Linked cloud folder, server URL, user info   |
| `sync.json`       | Per-file sync state (hashes, doc IDs)        |
| `trash/`          | Files removed by cloud-side deletions        |

Global credentials and logs are stored under `~/.collabmark/`:

| Path                         | Purpose                                 |
|------------------------------|------------------------------------------|
| `~/.collabmark/logs/sync.log` | Structured JSON log (rotating)          |
| `~/.collabmark/credentials.json` | Non-sensitive login metadata         |
| OS keychain                   | API key (encrypted, via `keyring`)      |

## Development

```bash
# Run all tests
cd cli && pytest

# Run tests with coverage
pytest --cov=collabmark

# Lint and format
ruff check src/ tests/
ruff format src/ tests/
```

## Project Structure

```
cli/
  src/collabmark/
    __init__.py           Package version
    __main__.py           python -m collabmark entry point
    main.py               Root CLI group, welcome banner
    types.py              Shared dataclasses (SyncConfig, DocumentInfo, etc.)
    commands/
      init.py             collabmark init
      login.py            collabmark login
      logout.py           collabmark logout
      start.py            collabmark start
      status.py           collabmark status
      stop.py             collabmark stop
      logs.py             collabmark logs
    lib/
      api.py              Async REST client with retry/backoff
      auth.py             Keychain credential management
      browser_auth.py     Browser-based OAuth flow
      config.py           .collabmark/ config and state management
      daemon.py           PID file and process management
      logger.py           Structured JSON logging with credential masking
      sync_engine.py      Three-way reconciliation and sync actions
      watcher.py          Debounced filesystem watcher
  tests/
    conftest.py           Shared fixtures
    test_api.py           API client tests
    test_auth.py          Auth and keychain tests
    test_browser_auth.py  Browser OAuth flow tests
    test_config.py        Config/state management tests
    test_daemon.py        Daemon PID management tests
    test_integration.py   End-to-end sync flow tests
    test_logger.py        Logging tests
    test_main.py          CLI entry point tests
    test_start.py         Start command tests
    test_sync_engine.py   Reconciliation logic tests
    test_watcher.py       File watcher tests
```
