# CollabMark CLI

Sync markdown files between your local machine and CollabMark cloud. Designed
so that even a product manager can start syncing with a single command.

## Quick Start

```bash
# Install in development mode
cd cli
pip install -e ".[dev]"

# Verify installation
collabmark --version

# Start syncing (interactive folder picker)
collabmark start

# Start syncing a shared link
collabmark start https://app.collabmark.io/share/abc123

# Run as a background daemon
collabmark start --daemon

# Check sync status
collabmark status

# View logs
collabmark logs --follow

# Stop the daemon
collabmark stop
```

## Development

```bash
# Run tests
pytest

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/
```

## Project Structure

```
cli/
  src/collabmark/
    __init__.py        # version
    __main__.py        # python -m collabmark
    main.py            # root CLI group
    types.py           # shared type definitions
    commands/          # click command implementations
      start.py
      status.py
      stop.py
      logs.py
    lib/               # shared library modules
      auth.py          # authentication (OAuth, API key)
      api_client.py    # REST client wrapper
      config.py        # .collabmark/ config management
      sync_engine.py   # reconciliation logic
      watcher.py       # file-system watcher
  tests/
    conftest.py
    test_main.py
```
