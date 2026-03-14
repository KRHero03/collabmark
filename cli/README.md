# CollabMark CLI

Keep your local markdown files in sync with your team's CollabMark cloud
workspace -- bidirectionally and in real time, powered by CRDTs.

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
login. Credentials are stored securely in your OS keychain via `keyring`.

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
changes on both sides. Content is synced via CRDT WebSocket for real-time
bidirectional updates; REST is used only for metadata and authentication.

```bash
collabmark start                     # Sync current dir, choose folder interactively
collabmark start <share-link>        # Join a shared folder by link
collabmark start -d                  # Run as a background daemon
collabmark start -p ~/notes          # Sync a specific directory
collabmark start --interval 30       # Poll every 30 seconds (default: 10s)
```

### `collabmark status`

Show the current sync state. When run from a project directory, shows detailed
project info. When run without a project, shows a global overview of all syncs.

```bash
collabmark status                    # Project-specific or global view
collabmark status -p ~/notes         # Check a specific project
```

### `collabmark list`

List all registered syncs across all projects with status, PID, last sync
time, and cloud folder info.

```bash
collabmark list
```

### `collabmark stop`

Gracefully stop sync processes. Supports interactive selection when multiple
syncs are running.

```bash
collabmark stop                      # Stop current project or choose interactively
collabmark stop --all                # Stop all running syncs
collabmark stop --path ~/notes       # Stop a specific project's sync
```

### `collabmark logs`

View structured sync log output. Each sync project has its own log file.

```bash
collabmark logs                      # Current project logs (last 50 entries)
collabmark logs -n 100               # Last 100 entries
collabmark logs -f                   # Follow in real time (like tail -f)
collabmark logs --folder <id>        # Logs for a specific cloud folder
collabmark logs --all-syncs          # Interleaved logs from all syncs
```

### `collabmark clean`

Remove stale entries from the sync registry (stopped syncs, missing directories).

```bash
collabmark clean                     # Interactive selection of stale entries
collabmark clean --all               # Remove all stopped entries
collabmark clean --force             # Remove all entries (including running)
```

## How Sync Works

1. **Local scan** -- finds all `.md` files recursively (ignoring `.collabmark/`).
2. **Cloud scan** -- fetches the full folder tree from CollabMark in one API call.
3. **Three-way reconciliation** -- compares local files, the last-known sync state
   (`.collabmark/sync.json`), and cloud documents to determine what changed where.
4. **CRDT sync** -- content is pushed/pulled via WebSocket using pycrdt (the same
   CRDT library the server uses), so edits merge correctly with concurrent web users.
5. **Continuous watch** -- uses OS filesystem events (debounced) plus periodic
   cloud polling to keep both sides in sync.

### Conflict Resolution

When the same file changes both locally and on the cloud between sync cycles,
it is flagged as a **conflict**. Neither side is overwritten. The conflict is
logged and shown in `collabmark logs`.

## Monitoring & Observability

CollabMark CLI uses a centralized registry at `~/.collabmark/registry.json`
to track all active and stopped syncs. This enables:

- **Global visibility**: `collabmark list` shows all syncs at a glance
- **Per-project logs**: each sync writes to `~/.collabmark/logs/{folder_id}.log`
- **Heartbeat tracking**: last sync time, action count, and error status
- **Dead process detection**: `collabmark status` prunes crashed processes
- **Stale cleanup**: `collabmark clean` removes orphaned registry entries

## Configuration

All per-project configuration lives in `.collabmark/` at the root of your
synced directory:

| File              | Purpose                                      |
|-------------------|----------------------------------------------|
| `config.json`     | Linked cloud folder, server URL, user info   |
| `sync.json`       | Per-file sync state (hashes, doc IDs)        |
| `trash/`          | Files removed by cloud-side deletions        |

Global state is stored under `~/.collabmark/`:

| Path                              | Purpose                                  |
|-----------------------------------|------------------------------------------|
| `~/.collabmark/registry.json`     | Centralized sync registry (all projects) |
| `~/.collabmark/logs/{id}.log`     | Per-project structured JSON logs         |
| `~/.collabmark/pids/{id}.pid`     | Per-project PID files (daemon mode)      |
| `~/.collabmark/credentials.json`  | Non-sensitive login metadata             |
| OS keychain                       | API key (encrypted, via `keyring`)       |

### Environment Variables

| Variable                  | Purpose                            | Default                                          |
|---------------------------|------------------------------------|--------------------------------------------------|
| `COLLABMARK_API_URL`      | Override API server URL            | `https://web-production-5e1bc.up.railway.app`    |
| `COLLABMARK_FRONTEND_URL` | Override frontend URL              | `https://web-production-5e1bc.up.railway.app`    |
| `COLLABMARK_HOME`         | Override global config directory   | `~/.collabmark`                                  |

## Development

```bash
cd cli

# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests (313 tests)
python -m pytest -v

# Run tests with coverage
pytest --cov=collabmark

# Lint and format
ruff check src/ tests/
ruff format src/ tests/
```

## Releasing to PyPI

Releases are automated via GitHub Actions. To publish a new version:

1. Update the version in `cli/src/collabmark/__init__.py` and `cli/pyproject.toml`
2. Commit and push to `main`
3. Create and push a tag: `git tag cli-v0.1.0 && git push origin cli-v0.1.0`
4. The `cli-release.yml` workflow runs lint, tests, builds, and publishes to PyPI

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
      start.py            collabmark start (with registry + heartbeat)
      status.py           collabmark status (global + project views)
      stop.py             collabmark stop (interactive + --all + --path)
      logs.py             collabmark logs (per-project + --all-syncs)
      list_syncs.py       collabmark list (global sync overview)
      clean.py            collabmark clean (stale entry removal)
    lib/
      api.py              Async REST client with retry/backoff
      auth.py             Keychain credential management
      browser_auth.py     Browser-based OAuth flow
      config.py           .collabmark/ config and state management
      crdt_sync.py        CRDT WebSocket sync (pycrdt)
      daemon.py           Per-project PID file and process management
      logger.py           Per-project structured JSON logging
      registry.py         Centralized sync registry (~/.collabmark/registry.json)
      sync_engine.py      Three-way reconciliation and sync actions
      watcher.py          Debounced filesystem watcher
  tests/                  313 tests
    conftest.py           Shared fixtures
    test_api.py           API client tests
    test_auth.py          Auth and keychain tests
    test_browser_auth.py  Browser OAuth flow tests
    test_clean.py         Clean command tests
    test_config.py        Config/state management tests
    test_crdt_sync.py     CRDT sync tests
    test_daemon.py        Per-project daemon PID tests
    test_integration.py   End-to-end sync flow tests
    test_list_syncs.py    List command tests
    test_logger.py        Logging tests
    test_logs.py          Logs command tests
    test_main.py          CLI entry point tests
    test_registry.py      Sync registry tests
    test_start.py         Start command tests
    test_status.py        Status command tests
    test_stop.py          Stop command tests
    test_sync_engine.py   Reconciliation logic tests
    test_watcher.py       File watcher tests
  pyproject.toml          hatchling build config + CLI entry point
```
