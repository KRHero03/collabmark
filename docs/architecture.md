# Architecture Overview

CollabMark is a collaborative Markdown editor with real-time multi-user editing,
folder-based document organization, and a CLI for bidirectional file sync.

## System Overview

Three-tier architecture:

1. **Frontend** -- React single-page application served as static files.
2. **Backend** -- FastAPI (Python) application handling REST API, WebSocket, and
   static file serving.
3. **Storage** -- MongoDB (primary data store) and Redis (notification scheduling,
   retry queues).

All components communicate over REST (`/api/...`) and WebSocket (`/ws/doc/{id}`).
Production deployment targets Railway; the backend serves the built frontend via
a SPA fallback handler.

```
Browser/CLI
   |
   |--- REST (HTTPS) -----> FastAPI -----> MongoDB
   |--- WebSocket (WSS) --> pycrdt-ws --> MongoYStore --> MongoDB
                                            |
                                          Redis (notifications)
```

---

## Backend Architecture

**Path:** `backend/app/`

### Application Lifecycle

`app/main.py` defines a FastAPI application with an `asynccontextmanager` lifespan
that initializes:

- **Motor** async MongoDB client + Beanie ODM document registration (20 document models)
- **MongoYStore** database binding for CRDT persistence
- **CollabWebsocketServer** for real-time editing rooms
- **Redis** connection for the notification system (gracefully skipped if unavailable)
- **NotificationDispatcher** with registered channels, plus background `scheduler_loop`
  and `retry_loop` tasks

Middleware stack (applied in order):
- Security headers (HSTS, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy)
- CORS with configurable allowed origins
- Session middleware (Starlette)
- Rate limiting via slowapi

### Layers

| Layer | Path | Responsibility |
|-------|------|----------------|
| Routes | `app/routes/` | Thin HTTP handlers. Routers: `auth`, `documents`, `folders`, `sharing`, `comments`, `versions`, `keys`, `users`, `notifications`, `orgs`, `scim`, `ws` |
| Services | `app/services/` | Business logic. Key services: `document_service`, `folder_service`, `share_service`, `acl_service`, `comment_service`, `version_service`, `crdt_store`, `notification_dispatcher`, `notification_scheduler`, `notification_retry`, `blob_storage`, `org_service`, `scim_service`, `group_sharing_service` |
| Models | `app/models/` | Beanie ODM documents and Pydantic schemas for request/response serialization |
| Auth | `app/auth/` | Authentication providers: `google_oauth`, `sso_saml`, `sso_oidc`, `api_key`, `jwt`, `cookie_utils`, `dependencies`, `scim_auth`, `sso_common` |
| WebSocket | `app/ws/` | pycrdt-websocket server and FastAPI adapter |
| Utils | `app/utils/` | Shared helpers (`owner_resolver`) |

### Key Dependencies

FastAPI, Uvicorn, Beanie, Motor (async MongoDB driver), authlib, python-jose (JWT),
pycrdt + pycrdt-websocket, boto3 (S3 blob storage), redis (async), slowapi (rate limiting),
pydantic-settings.

---

## Frontend Architecture

**Path:** `frontend/src/`

### Stack

- React 19 + TypeScript + Vite
- Routing: react-router v7 (`BrowserRouter` with SPA fallback on backend)
- State management: Zustand (per-feature stores)
- HTTP client: axios (`src/lib/api.ts` -- all endpoints typed)
- Editor: CodeMirror 6 + Yjs CRDT + y-codemirror.next + y-websocket
- Styling: Tailwind CSS v4 with CSS custom properties for dark/light mode
- Markdown rendering: react-markdown + mermaid (diagram support)

### Directory Structure

| Directory | Contents |
|-----------|----------|
| `src/pages/` | Route-level components: `LandingPage`, `HomePage`, `EditorPage`, `SettingsPage`, `ProfilePage`, `ApiDocsPage`, `SuperAdminPage`, `OrgSettingsPage`, `CLILoginPage`, `NotFoundPage` |
| `src/components/Home/` | Document list, folder breadcrumbs, context menus, dialogs (create folder, rename, confirm), ACL panel, toast container, info modals |
| `src/components/Editor/` | Markdown editor (CodeMirror), formatting toolbar, comments panel, comment threads, share dialog, presence avatars, version history, diff view, markdown preview |
| `src/components/Auth/` | Google login button, SSO login flow |
| `src/components/Layout/` | Navbar, mobile sidebar, user avatar |
| `src/hooks/` | Zustand stores: `useAuth`, `useDocuments`, `useFolders`, `useComments`, `useCommentPositions`, `useCommentAnchors`, `usePresence`, `useYjsProvider`, `useShareCollaborators`, `useDarkMode`, `useToast` |
| `src/lib/` | `api.ts` (HTTP client), `cn.ts` (class names), `dateUtils.ts`, `pdfExport.ts`, `clipboard.ts` |

### Routing

Defined in `App.tsx`. Unauthenticated users see `LandingPage` at `/`; authenticated
users see `HomePage`. Protected routes (`/edit/:id`, `/settings`, `/profile`, `/admin`,
`/org/:orgId/settings`) redirect to `/login` if no session exists.

The `CLILoginPage` (`/cli-login`) handles the browser side of the CLI login flow.
After successful Google OAuth, the frontend checks `sessionStorage` for a pending
CLI login port and redirects to `/api/auth/cli/complete` to finalize the handoff.

---

## CLI Architecture

**Path:** `cli/src/collabmark/`

### Stack

Click-based CLI framework with Rich for terminal formatting. Installed as a Python
package providing the `collabmark` entry point.

### Commands

| Command | Description |
|---------|-------------|
| `login` | Opens browser for OAuth, receives auth code, exchanges for API key |
| `logout` | Clears stored credentials from OS keychain |
| `start` | Links directory to a cloud folder and starts sync (filesystem watcher + periodic sync) |
| `stop` | Stops the background sync daemon |
| `status` | Shows current sync state and daemon health |
| `logs` | Displays sync log (supports `-f` for follow mode) |
| `list` | Lists all active sync projects |
| `conflicts` | Shows unresolved sync conflicts |
| `doctor` | Runs diagnostic checks (connectivity, auth, config) |
| `clean` | Removes stale sync state and trash files |

### Libraries (`lib/`)

| Module | Purpose |
|--------|---------|
| `api.py` | HTTP client (`CollabMarkClient`) for REST API calls via httpx |
| `auth.py` | Credential storage and retrieval |
| `browser_auth.py` | Browser-based OAuth flow: starts local HTTP server, opens browser, receives callback |
| `config.py` | Configuration management, sync state persistence (`~/.collabmark/`) |
| `crdt_sync.py` | WebSocket CRDT operations: read/write/update document content via pycrdt |
| `daemon.py` | Background process management (start/stop/status) |
| `logger.py` | Structured logging configuration |
| `registry.py` | Project registration and discovery |
| `sync_engine.py` | Three-way reconciliation engine |
| `watcher.py` | Filesystem watcher (watchdog) for detecting local changes |
| `persistent_sync.py` | Persistent WebSocket connection for real-time push sync |

### Sync Engine

The sync engine (`sync_engine.py`) implements three-way reconciliation comparing:

1. **Local filesystem** -- SHA-256 hashes of all `.md` files under the sync root
2. **Sync state** -- persisted in `~/.collabmark/projects/{id}/sync.json`
3. **Cloud state** -- document metadata via REST API, content via CRDT/WebSocket

The reconciliation produces actions:

| Action | Trigger |
|--------|---------|
| `PUSH_NEW` | Local file exists, not tracked, not on cloud |
| `PUSH_UPDATE` | Local file changed since last sync, cloud unchanged |
| `PULL_NEW` | Cloud document exists, not tracked, no local file |
| `PULL_UPDATE` | Cloud document changed since last sync, local unchanged |
| `DELETE_LOCAL` | Cloud document deleted, local file still exists (moved to trash) |
| `DELETE_REMOTE` | Local file deleted, cloud document still exists (soft-delete) |
| `CONFLICT` | Both local and cloud changed since last sync |

Conflicts are resolved by writing the remote version to a `.conflict.<timestamp>.md`
sidecar file, leaving the local file untouched for manual resolution.

Content always flows through the CRDT layer (WebSocket). The REST API is used only
for metadata operations (create/delete documents, folder structure).

### Credentials

Stored in the OS keychain via the `keyring` library. Configuration is centralized
at `~/.collabmark/`.

---

## Real-Time Collaboration

### CRDT Protocol

- **Frontend:** Yjs (`y-websocket`) connects to `/ws/doc/{id}`
- **Backend:** pycrdt-websocket (`CollabWebsocketServer`) manages per-document rooms
- **CLI:** pycrdt over WebSocket (same protocol as the web editor)

All three clients use the same Yjs/pycrdt CRDT protocol, enabling simultaneous
editing from any combination of web browsers and CLI-synced editors.

### WebSocket Server

`CollabWebsocketServer` (in `app/ws/handler.py`) extends pycrdt-websocket's
`WebsocketServer`. Each document gets a `YRoom` backed by `MongoYStore`.

On room creation, existing CRDT updates are loaded from MongoDB and applied to
a fresh `Doc()`, ensuring the server has the full document state even after
restarts.

### FastAPIWebsocketAdapter

Bridges FastAPI WebSocket connections to the `YRoom.serve()` channel interface.
Key behaviors:

- **Read-only enforcement:** When the user has VIEW permission, incoming Yjs
  sync-update messages (document edits) are silently dropped.
- **Dynamic permission re-check:** Every 10 seconds, the adapter re-queries the
  database for the user's current permission, so mid-session ACL changes (e.g.,
  downgrade from Editor to Viewer) take effect without reconnection.
- **User attribution:** For every incoming message that modifies the Y.Doc, the
  adapter pushes the authenticated user's ID into the store's FIFO queue so the
  subsequent `write()` can record who made the change.
- **Message size limit:** 5 MB per WebSocket message.

### MongoYStore

Custom `BaseYStore` implementation that persists Y.Doc binary updates to the
`crdt_updates` MongoDB collection. Schema per record:

```
{ room, update (bytes), metadata (bytes), timestamp (float), version (int) }
```

Supports compaction: replaces N incremental updates with a single full-state
snapshot within a MongoDB transaction.

### Awareness Protocol

Cursor presence (showing other users' cursor positions and selections) is handled
by the Yjs awareness protocol, transported over the same WebSocket connection.
The frontend renders this via `PresenceAvatars` component.

---

## Authentication and Authorization

### Authentication Providers

| Provider | Use Case | Flow |
|----------|----------|------|
| **Google OAuth2** | Default for personal users | Redirect to Google -> authorize -> callback -> JWT cookie |
| **SAML 2.0** | Organizations with SAML IdPs | `app/auth/sso_saml.py` |
| **OIDC** | Organizations with OIDC providers | `app/auth/sso_oidc.py` |
| **API Keys** | CLI and programmatic access | `X-API-Key` header, SHA-256 hashed in MongoDB |
| **CLI Browser Login** | CLI authentication | Opens browser -> user authenticates -> backend issues auth code -> CLI exchanges for API key |

### JWT

- Algorithm: HS256
- Expiry: 7 days (configurable via `jwt_expire_minutes`)
- Transport: httponly cookie (`access_token`)
- Claims: `sub` (user ID), `exp` (expiration)

### API Keys

- Format: `cm_` prefix + 32 bytes hex (64 hex chars)
- Storage: SHA-256 hash stored in MongoDB (`api_keys` collection)
- Lookup: constant-time comparison via `hmac.compare_digest`
- Usage tracking: `last_used_at` updated on each authenticated request

### Permission Model

Resolution order (highest priority first):

1. **Root folder owner** -- full control over the entire folder hierarchy
2. **Entity owner** (at root level or also root owner) -- full control
3. **Entity owner** (nested, created via edit access) -- view, edit, share; delete only if all children are also owned
4. **Editor** (direct `DocumentAccess`/`FolderAccess`, group-based, or inherited from parent folder) -- view, edit; no delete, no share
5. **Viewer** (direct, group-based, or inherited) -- view only
6. **general_access** (`anyone_view`/`anyone_edit`) -- scoped to same-organization users when the entity belongs to an org
7. **Deny** -- no access

Inheritance walks up the folder `parent_id` chain (max depth 50). Performance is
optimized via a denormalized `root_folder_id` field on documents and folders for
O(1) root-owner resolution.

---

## Data Model

MongoDB collections managed via Beanie ODM.

### Core Entities

| Collection | Model | Key Fields |
|------------|-------|------------|
| `users` | `User` | `email` (unique), `google_id`, `name`, `avatar_url`, `org_id`, `auth_provider`, `external_id` |
| `documents` | `Document_` | `title`, `content`, `owner_id`, `folder_id`, `root_folder_id`, `org_id`, `general_access`, `is_deleted` |
| `folders` | `Folder` | `name`, `owner_id`, `parent_id`, `root_folder_id`, `org_id`, `general_access`, `is_deleted` |
| `document_access` | `DocumentAccess` | `document_id`, `user_id`, `permission` (view/edit), `granted_by` |
| `folder_access` | `FolderAccess` | `folder_id`, `user_id`, `permission`, `granted_by` |
| `comments` | `Comment` | `document_id`, `author_id`, `content`, `anchor_from`, `anchor_to`, `anchor_from_relative`, `anchor_to_relative`, `quoted_text`, `parent_id`, `is_resolved`, `is_orphaned` |
| `document_versions` | `DocumentVersion` | `document_id`, `version_number` (compound unique with document_id), `content`, `author_id`, `summary` |
| `share_links` | `ShareLink` | `document_id`, `token` (unique), `permission`, `expires_at` |

### Organization Entities

| Collection | Model | Key Fields |
|------------|-------|------------|
| `organizations` | `Organization` | `name`, `slug` (unique), `verified_domains`, `plan`, `logo_url`, `admin_group_name` |
| `org_memberships` | `OrgMembership` | `org_id`, `user_id`, `role` (admin/member) |
| `org_sso_configs` | `OrgSSOConfig` | SSO configuration per organization |

### Group Entities

| Collection | Model | Key Fields |
|------------|-------|------------|
| `groups` | `Group` | Group definitions within organizations |
| `group_memberships` | `GroupMembership` | `group_id`, `user_id` |
| `document_group_access` | `DocumentGroupAccess` | `document_id`, `group_id`, `permission` |
| `folder_group_access` | `FolderGroupAccess` | `folder_id`, `group_id`, `permission` |

### Notification Entities

| Collection | Model | Key Fields |
|------------|-------|------------|
| `notifications` | `Notification` | `recipient_id`, `event_type`, `channel`, `status`, `payload`, `document_id`, `action_ref_id`, `scheduled_for`, `retry_count` |
| `notification_preferences` | `NotificationPreference` | `user_id` (unique), `preferences` (nested dict of event_type -> channel -> enabled) |

### Activity Tracking

| Collection | Model | Purpose |
|------------|-------|---------|
| `document_views` | `DocumentView` | Powers "Recently Viewed" tab |
| `folder_views` | `FolderView` | Powers "Recently Viewed" folders |
| `api_keys` | `ApiKey` | `user_id`, `key_hash` (unique), `name`, `is_active`, `last_used_at` |
| `crdt_updates` | (raw collection) | Binary CRDT updates per room, used by `MongoYStore` |

### Comment Anchoring

Inline comments use three anchoring mechanisms for resilience:

1. **Yjs RelativePositions** (`anchor_from_relative`, `anchor_to_relative`) -- CRDT-aware
   positions serialized as Base64 that survive concurrent edits
2. **Absolute offsets** (`anchor_from`, `anchor_to`) -- snapshot values periodically
   refreshed by the frontend; used as fallback
3. **Quoted text** (`quoted_text`) -- immutable snapshot of selected text at creation time

When anchored text is fully deleted, the comment is marked orphaned (`is_orphaned=True`)
and remains visible in the global comments panel.

---

## Email Notifications

### Architecture

The notification system uses a delayed-dispatch pattern to allow actions to be
undone before the notification is sent (e.g., a user accidentally shares a document,
then revokes access within the delay window).

### Components

| Component | File | Role |
|-----------|------|------|
| `NotificationDispatcher` | `notification_dispatcher.py` | Central coordinator: schedules notifications into Redis ZSET, delivers via registered channel handlers |
| `scheduler_loop` | `notification_scheduler.py` | Background task polling Redis every 10s for due notifications; validates the triggering action still exists before dispatching |
| `retry_loop` | `notification_retry.py` | Background task polling Redis retry list every 15s; exponential backoff (30s base, max 3 retries) |
| `EmailChannel` | `channels/email.py` | Channel handler for email delivery |

### Flow

1. An action (share, comment) calls `dispatcher.schedule()` with a configurable delay
   (default 60 seconds).
2. A `Notification` document is created in MongoDB with status `SCHEDULED`.
3. The notification ID is pushed into a Redis sorted set (`collabmark:notifications:scheduled`)
   scored by delivery timestamp.
4. The `scheduler_loop` pops due items, validates the action still exists (comment not
   deleted, access not revoked), and either dispatches or marks as `SKIPPED`.
5. On send failure, the notification is pushed to a Redis retry list
   (`collabmark:notifications:retry`) for exponential backoff retry.

### Channels

- **Resend API** -- production email delivery
- **SMTP** -- development/local delivery (compatible with Mailpit)

Configured via `notification_email_provider` setting (`resend` or `smtp`).

### Event Types

- `document_shared` -- triggered when a document is shared with a user
- `folder_shared` -- triggered when a folder is shared with a user
- `comment_added` -- triggered when a comment is added to a document

### User Preferences

Per-user preferences stored in `notification_preferences` collection. Users can
disable specific event/channel combinations. Defaults to all enabled.
