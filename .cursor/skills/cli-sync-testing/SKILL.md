---
name: cli-sync-testing
description: End-to-end testing procedure for CollabMark CLI sync. Covers single-document sync, folder sync, subfolder CRUD, deletion propagation, logging verification, and permission-based deletion. Uses Playwright MCP for web UI interaction and CLI commands for local sync. Run after any changes to the sync engine, CRDT layer, or CLI commands.
---

# CLI Sync E2E Testing Procedure

Validates bidirectional sync between the CollabMark CLI and the web UI. Requires a running local stack (MongoDB, Redis, backend, frontend) and Playwright MCP for browser automation.

## Prerequisites

- Local stack running: `docker compose up -d mongodb redis`, backend on `:8000`, frontend on `:5173`
- CLI installed in isolated venv: `/tmp/collabmark-e2e/.venv/bin/collabmark`
- Playwright MCP connected (tools: `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`, `browser_fill_form`, `browser_evaluate`)
- Wrapper script at `/tmp/collabmark-e2e/cm` (sets `COLLABMARK_HOME`, `COLLABMARK_API_URL`, `COLLABMARK_FRONTEND_URL`)

### Environment Setup

```bash
# Create wrapper to avoid repeating env vars
cat > /tmp/collabmark-e2e/cm << 'EOF'
#!/bin/bash
export COLLABMARK_HOME=/tmp/collabmark-e2e/.collabmark
export COLLABMARK_API_URL=http://localhost:8000
export COLLABMARK_FRONTEND_URL=http://localhost:5173
exec /tmp/collabmark-e2e/.venv/bin/collabmark "$@"
EOF
chmod +x /tmp/collabmark-e2e/cm
```

### CLI Authentication

If the API key is missing (check with `collabmark doctor`), use Playwright to create one:

1. Navigate Playwright to `http://localhost:5173` and log in via Google OAuth
2. Use `browser_evaluate` to call the API from the authenticated session:
   ```js
   async () => {
     const userResp = await fetch('/api/users/me');
     const user = await userResp.json();
     const keyResp = await fetch('/api/keys', {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify({ name: 'CollabMark CLI (auto-created)' })
     });
     const keyData = await keyResp.json();
     return { user, keyData };
   }
   ```
3. Save the `raw_key` to the keyring:
   ```python
   import keyring
   keyring.set_password('collabmark', 'api_key', '<raw_key>')
   ```

## Test 1: Web UI Login via Playwright

| Step | Action | Expected |
|------|--------|----------|
| 1 | `browser_navigate` to `http://localhost:5173` | Landing page loads |
| 2 | Click "Sign in with Google" | OAuth completes (session may already exist) |
| 3 | `browser_snapshot` | Dashboard shows user name, "My Files" heading, file/folder list |

## Test 2: Single Document Sync

### Setup
Create a new document via Playwright: click "New Document", set title, type content.
Note the document ID from the URL (`/edit/<doc_id>`).

### 2a: Cloud → Local (initial pull)
```bash
mkdir -p /tmp/collabmark-e2e/sync-test
cd /tmp/collabmark-e2e/sync-test
/tmp/collabmark-e2e/cm start --doc <doc_id> &
sleep 5
cat "<Doc Title>.md"  # Should contain the cloud content
```
**Pass criteria:** Local `.md` file contains the document content from the web editor.

### 2b: Local → Cloud (push)
Edit the local `.md` file (append text). Wait ~12s for poll cycle. Navigate Playwright to the doc URL and `browser_snapshot`.

**Pass criteria:** New content appears in the web editor.

### 2c: Cloud → Local (real-time pull)
Type new content in the Playwright editor. Wait ~12s. Read the local file.

**Pass criteria:** New content from the web editor appears in the local file. If WebSocket is connected, updates arrive within seconds.

### Cleanup
`kill <sync_pid>`

## Test 3: Folder Sync (Bidirectional)

### Setup
1. Create a folder on the web UI via Playwright ("New Folder")
2. Add 2+ documents inside the folder with content
3. Note the folder ID from the URL (`?folder=<folder_id>`)
4. Start sync (pass folder ID as argument — `start` handles linking automatically):
```bash
mkdir -p /tmp/collabmark-e2e/folder-sync-test
/tmp/collabmark-e2e/cm start <folder_id> -p /tmp/collabmark-e2e/folder-sync-test &
```

### 3a: Cloud → Local (initial pull)
**Pass criteria:** All `.md` files from the cloud folder appear locally with correct content.

### 3b: Local new file → Cloud
Create a new `.md` file locally. Wait ~15s. Check the web UI folder.

**Pass criteria:** New document appears in the cloud folder.

### 3c: Local update → Cloud
Edit an existing local `.md` file. Wait ~15s. Open the document in Playwright.

**Pass criteria:** Updated content visible in the web editor.

### 3d: Cloud new document → Local
Create a new document on the web UI inside the folder. Wait ~15s. Check local directory.

**Pass criteria:** New `.md` file appears locally with correct content.

### 3e: Cloud update → Local
Edit a document on the web UI via Playwright. Wait ~15s. Read the local file.

**Pass criteria:** Updated content appears in the local file.

## Test 4: Subfolder CRUD

### 4a: Cloud subfolder → Local
Create a subfolder on the web UI, add a document inside it. Wait ~15s.

**Pass criteria:** Subfolder directory and `.md` file appear locally.

### 4b: Local subfolder → Cloud
Create a local subdirectory with a `.md` file. Wait ~15s. Check the web UI.

**Pass criteria:** Subfolder and document appear on the cloud.

### 4c: Cloud folder deletion → Local
Delete a folder on the web UI ("Move to Trash"). Wait ~15s.

**Pass criteria:** Documents inside the folder are removed locally. Empty directory shell may remain (by design — sync engine avoids deleting dirs that might contain non-synced files).

### 4d: Local folder deletion → Cloud
Delete a local subfolder (`rm -rf`). Wait ~15s. Check the web UI.

**Pass criteria:** Documents inside the folder are deleted from the cloud. Empty cloud folder shell may remain (same behavior as 4c).

## Test 5: Permission-Based Deletion

**Requires a second user account** with VIEW-only access to a shared folder.

### 5a: Try local delete with VIEW-only permission
Delete a locally-synced file that the user only has VIEW access to.

**Expected:** API returns a permission error.

### 5b: Verify file restoration
The sync engine should detect the deletion failed and re-pull the file from the cloud.

**Expected:** File reappears locally on next sync cycle.

> **Note:** This test requires creating a second test account and sharing a folder with VIEW-only access. Skip if only one account is available.

## Test 6: Logging Verification

Start sync with verbose logging:
```bash
/tmp/collabmark-e2e/cm start <folder_id> -p <path> -v &
```

Trigger operations (create, update, delete files locally and on cloud), then check log file:
```bash
cat ~/.collabmark/logs/<folder_id>.log
```

### Required log events

| Event | Log message pattern |
|-------|-------------------|
| PULL_NEW | `↓ pulled  <filename>` |
| PUSH_NEW | `↑ pushed (new)  <filename>` |
| PUSH_UPDATE | `↑ pushed (update) <filename>` |
| DELETE_LOCAL | `↓ moved to trash  <filename>` |
| DELETE_REMOTE | `x deleted remote  <filename>` |
| Folder creation | `created cloud folder  <name>` |
| Watcher events | `Detected create/modify/delete: <path>` |
| Sync cycles | `Sync cycle: N actions (M files tracked)` |

**Pass criteria:** All event types present in logs as structured JSON with timestamps.

## Results Summary Template

| Test | Result | Notes |
|------|--------|-------|
| 1. Web UI Login | PASS/FAIL | |
| 2a. Cloud → Local pull | PASS/FAIL | |
| 2b. Local → Cloud push | PASS/FAIL | |
| 2c. Cloud → Local real-time | PASS/FAIL | |
| 3a. Folder initial pull | PASS/FAIL | |
| 3b. Local new file → Cloud | PASS/FAIL | |
| 3c. Local update → Cloud | PASS/FAIL | |
| 3d. Cloud new doc → Local | PASS/FAIL | |
| 3e. Cloud update → Local | PASS/FAIL | |
| 4a. Cloud subfolder → Local | PASS/FAIL | |
| 4b. Local subfolder → Cloud | PASS/FAIL | |
| 4c. Cloud folder delete | PASS/FAIL | |
| 4d. Local folder delete | PASS/FAIL | |
| 5. Permission deletion | PASS/FAIL/SKIP | Needs 2nd user |
| 6. Logging verification | PASS/FAIL | |

## Known Behaviors

- **Empty folder cleanup:** The sync engine does not remove empty directories after all documents are deleted. This is by design to avoid accidentally removing directories that may contain non-synced files.
- **WebSocket doctor check:** `collabmark doctor` reports WebSocket failure because it uses a fake doc ID (`__health_check__`) which fails the permission check. Actual document WebSocket connections work fine.
- **List nesting in markdown:** The CRDT → markdown rendering may produce extra `-` characters in nested lists. This is a rendering quirk, not a sync issue.
- **Poll interval:** Folder sync uses polling (default 10s). Single-document sync also uses a persistent WebSocket for real-time updates.
