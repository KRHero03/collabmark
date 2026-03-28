# CollabMark -- Agent Guidelines & Progress

This file serves as a self-reference guide for AI agents working on this project.
It tracks progress, conventions, architectural decisions, and coding standards.

## Project Overview

CollabMark is a collaborative Markdown editor (Google Docs-style) with:
- Real-time multi-user editing via CRDTs (Yjs/pycrdt)
- Google OAuth sign-in + SSO (SAML 2.0 / OIDC) for organizations
- API key access for programmatic use
- Google Docs-style document sharing (general access + email-based collaborators)
- Version history with diff view and restore capability
- Inline and doc-level commenting system with anchor lifecycle
- Spaces (folders) for hierarchical document organization with ACLs
- Trash bin with soft-delete, restore, and permanent delete
- PDF and Markdown export
- Toast notifications and confirmation modals for all mutations
- Dark mode support
- Email notifications with delayed dispatch and action validation (Resend/SMTP)
- MongoDB storage, Python (FastAPI) backend, React (Vite) frontend

## Current State

### Completed
- **Phase 1**: FastAPI skeleton, Beanie/MongoDB, Google OAuth2, Docker Compose
- **Phase 2**: Document CRUD, soft-delete, API keys (dual auth: JWT cookie + X-API-Key header), React scaffold with CodeMirror editor
- **Phase 3**: Real-time collaboration via CRDTs
  - Backend: MongoYStore (custom BaseYStore for MongoDB), CollabWebsocketServer, FastAPIWebsocketAdapter, WS route with JWT/API-key auth
  - Frontend: Yjs + y-codemirror.next + y-websocket integration, useYjsProvider hook, collaborative MarkdownEditor with cursor presence
- **Phase 4**: Sharing and ACLs (redesigned to Google Docs model)
  - Backend: share_service.py, sharing routes (collaborator management, general access, shared docs list), permission-aware document access (VIEW/EDIT), WS permission checks (VIEW and EDIT users can connect)
  - Document model has `general_access` field: `restricted` | `anyone_view` | `anyone_edit`
  - Email-based collaborator management: add/list/remove collaborators by email
  - Permission checks: owner > explicit DocumentAccess > folder access inheritance > general_access > deny
  - Frontend: Google Docs-style ShareDialog (add by email, people with access list, general access toggle, copy link), sharingApi client
  - 22 sharing-related tests + updated integration tests
- **Phase 5**: Version History
  - Backend: DocumentVersion model, version_service.py, version routes, auto-snapshot on document save
  - Deduplication: identical content to latest version returns 204 (no new version created)
  - Frontend: VersionHistory slide-out panel with diff view (jsdiff), restore button, versionsApi client
  - Auto-versioning: 30s idle timeout + 5min rate limit, beforeunload beacon
  - 15 version tests (including 5 dedup tests)
- **Phase 6**: Comments System
  - Backend: Comment model, comment_service.py, comment routes (create, reply, resolve, delete, reanchor, orphan)
  - Frontend: CommentsPanel (position-synced gutter), CommentThread (anchor status badges), useComments Zustand store, commentsApi client
  - 20 comment tests (10 original + 10 anchor lifecycle)
- **Phase 6b**: Comment Anchor Lifecycle
  - Backend: anchor_from_relative, anchor_to_relative, is_orphaned, orphaned_at fields on Comment model
  - Backend: PATCH /reanchor and PATCH /orphan endpoints, reanchor_comment() and orphan_comment() service functions
  - Frontend: useCommentAnchors hook (Yjs RelativePosition resolution, orphan detection, drift detection)
  - Frontend: useCommentPositions hook (pixel Y-coordinate mapping, stacking algorithm for same-line comments)
  - Frontend: MarkdownEditor exposes EditorView, selection events, floating "Comment" button, inline highlight decorations
  - Frontend: CommentsPanel rewritten as position-synced gutter with connecting lines, orphan section, doc-level section
  - Frontend: CommentThread shows anchor status badges ("text changed", "text removed")
  - Frontend: EditorPage wires Yjs RelativePositions on selection, panel toggle (mutual exclusion), backdrop overlay
  - 15 new frontend tests (useComments store, useCommentPositions stacking)
- **Phase 6c**: Markdown Preview Fix
  - Installed @tailwindcss/typography and mermaid packages
  - rehype-highlight for code block syntax highlighting
  - MermaidBlock component for rendering ```mermaid diagrams as inline SVGs
  - highlight.js github theme CSS imported
- **Phase 7**: Export and Polish
  - Backend: PDF export via WeasyPrint (with HTML fallback), export routes
  - Frontend: PDF export button, dark mode toggle (CSS custom properties), Profile page
  - 3 export tests

- **Phase 8**: Scaling and Deployment
  - Dockerfile with multi-stage build, health check, gunicorn production server
  - docker-compose.prod.yml for production
  - railway.toml and Procfile for Railway deployment
  - Structured logging, enhanced health endpoint

- **Phase 9**: Interactive API Documentation
  - API key verified against running backend (all CRUD operations: list, create, get, update, delete, restore)
  - New ApiDocsPage at `/api-docs` with interactive "Try it" panels for all endpoints
  - Grouped by feature: Documents, Sharing, Versions, Comments, Export, API Keys
  - API key input (session storage), parameter forms, JSON body editors, live request execution
  - Responses displayed with status code badge and formatted JSON
  - Quick start guide with curl example
  - Navbar link added for "API Docs"
  - Route is public (no auth required -- API key is entered in the page itself)

- **Phase 10**: Editor UX Enhancements
  - Presentation Mode: toolbar toggle (Monitor icon) hides editor pane, centers preview full-width with `max-w-4xl`, Escape key to exit. Toolbar collapses to Back + Exit Presentation buttons.
  - Resizable Panes: draggable 4px splitter between editor and preview. Width ratio (20%-80%) persisted in `localStorage("collabmark_editor_width")`. Hidden in presentation mode. Proportional resize when comments panel open.
  - Debounced Preview: preview pane only re-renders after 1.5s of no typing (Overleaf-style). Shows "Preview outdated" / "Refresh preview" button when stale. Eliminates flickering during rapid edits, especially with Mermaid diagrams.

- **Phase 11**: Railway Deployment & Production Fixes
  - Dockerfile: Node 22 + yarn (corepack) for frontend build; `WORKDIR /app/backend` for gunicorn
  - SPA catch-all route: serves `index.html` for non-API paths (fixes direct URL navigation 404)
  - Static assets served via `/assets` mount; all other paths fall through to SPA
  - Environment variables configured on Railway (MongoDB, Redis, Google OAuth, JWT, CORS)
  - Google OAuth credentials updated for production domain
  - GitHub Actions CI/CD pipeline deploys to Railway on push to main

- **Phase 12**: Mermaid Re-render Fix & Recently Viewed Tab
  - **Mermaid fix**: MermaidBlock memoized with `React.memo`, stable render IDs via `useRef` counter,
    `components` prop memoized with `useMemo` to prevent ReactMarkdown from re-creating blocks.
    Yjs observer uses functional `setContent` to skip no-op state updates.
  - **Recently Viewed tab**: `DocumentView` model tracks all document views (including owner's own docs).
    `POST /api/documents/{id}/view` records or updates view timestamp for any document.
    `GET /api/documents/recent` returns all recently viewed docs sorted by recency, excluding
    deleted docs and docs the user has lost access to. EditorPage records a view on load.
    HomePage has a third "Recently viewed" tab with owner info and permission badges.

- **Phase 13**: Context Menu, Trash, Document Info, Right-Click Actions
  - Right-click context menu: owned docs (Open in new tab, Rename, Move to Trash, Delete, Info), shared/recently viewed (Open in new tab, Info)
  - Trash bin tab: soft-deleted docs/folders with Restore and Delete Permanently actions, Empty Trash button
  - DocumentInfoModal: metadata display (title, owner, dates, content length, access level, deleted status)
  - Backend hard delete: `DELETE /api/documents/{id}/permanent` with cleanup of CRDT updates, comments, shares, views, versions
  - RenameDialog for inline document renaming
  - Local time display everywhere via `dateUtils.ts` (formatDateShort, formatDateLong, formatDateTime)

- **Phase 14**: Spaces (Folders) Feature
  - Backend: `Folder` and `FolderAccess` models, `folder_service.py` with cascade soft-delete/restore/hard-delete
  - Backend: 13 folder endpoints (CRUD, trash/restore/hard-delete, contents, breadcrumbs, collaborator management)
  - Backend: Access inheritance -- documents in folders inherit parent folder's ACLs
  - Frontend: `useFolders` Zustand store, `foldersApi` with 12 methods
  - Frontend: FolderBreadcrumbs, CreateFolderDialog, FolderInfoModal components
  - Frontend: File-browser view on home page (replaced "My Documents" tab with "Files" tab)
  - Frontend: Right-click context menu support for folders (Rename, Delete, Info, Share)
  - 72 backend folder tests, 23 frontend folder store tests

- **Phase 15**: UX Polish & Version History Overhaul
  - **Confirmation Modals**: ConfirmDialog component for all delete actions (soft-delete, hard-delete, empty trash for docs and folders)
  - **Toast Notifications**: ToastContainer with slide-in/slide-out animations, stacked display (flex-col-reverse), phase-based state management (entering/visible/exiting), auto-dismiss after 4s
  - **Editor Back Button**: Uses `navigate(-1)` (browser history back) for natural navigation context preservation
  - **Auto-versioning**: Removed manual save button; versions created automatically after 30s of inactivity (rate-limited to 5min). `beforeunload` beacon for final snapshot on page close
  - **Version Deduplication**: Backend `save_snapshot` skips creation if content identical to latest version (returns None / 204)
  - **Diff View**: DiffView component using jsdiff (`diffLines`) replaces MarkdownPreview in VersionHistory. Shows added/removed/unchanged blocks with color coding
  - **Version Restore**: Restore button in VersionHistory replaces Yjs content and creates a restore snapshot with attribution
  - **Recently Viewed (All Docs)**: Updated to record and display ALL viewed documents including owner's own, sorted by recency

- **SSO Phase 1**: Organization Models and Membership
  - Backend: `Organization`, `OrgMembership`, `OrgSSOConfig` models (new files)
  - Modified: `User` (added `org_id`, `auth_provider`), `Document_` (added `org_id`), `Folder` (added `org_id`)
  - New: `org_service.py` (CRUD, membership management), `orgs.py` routes (9 endpoints)
  - New auth dependencies: `get_super_admin_user`, `get_org_admin_user`
  - Auto-propagation of `org_id` on document/folder creation
  - Frontend: `orgsApi` added to `api.ts` with full type definitions
  - 41 backend org tests, 11 frontend api tests

- **SSO Phase 2**: SSO Authentication (SAML 2.0 + OIDC)
  - Backend: `sso_common.py` (SSOCallbackResult, detect_org_by_email_domain, find_or_create_sso_user)
  - Backend: `sso_saml.py` (build_saml_settings, create_saml_auth_request, process_saml_response via python3-saml)
  - Backend: `sso_oidc.py` (create_oidc_client, get_oidc_discovery, initiate_oidc_login, process_oidc_callback via authlib)
  - Backend: 5 new routes in `auth.py`: `POST /sso/detect`, `GET /sso/saml/login/{org_id}`, `POST /sso/saml/callback`, `GET /sso/oidc/login/{org_id}`, `GET /sso/oidc/callback`
  - SAML flow: RelayState carries org_id, ACS validates assertion, extracts email/name/avatar
  - OIDC flow: Session-stored state for CSRF, discovery-based endpoint resolution, token exchange + userinfo
  - Frontend: `SSOLoginFlow` component (email detection, SSO redirect, Google fallback)
  - Frontend: Updated `LandingPage` (hero + final CTA use SSOLoginFlow) and `LoginPage`
  - Frontend: `authApi.detectSSO()` method
  - 48 backend SSO tests, 10 frontend SSOLoginFlow tests

- **SSO Phase 3**: Org-Scoped ACLs and Sharing
  - `org_allows_general_access()` utility in acl_service: returns False when entity belongs to an org and user is in a different org (or personal)
  - `get_base_permission()` and `_get_inherited_permission()` accept `user_org_id` for org-scoped general_access checks
  - `resolve_effective_permission()` passes `user.org_id` through to base permission resolver
  - `document_service._assert_access()` enforces org boundary before evaluating general_access
  - `share_service.add_collaborator()` blocks cross-org sharing (403 "Cannot share with users outside your organization")
  - `folder_service.add_folder_collaborator()` blocks cross-org folder sharing (same error)
  - `share_service.get_user_permission()` and `folder_service.get_folder_permission()` pass org context through
  - Frontend: ShareDialog and FolderShareDialog accept optional `orgName` prop; labels change from "Anyone with the link" to "Anyone in [OrgName] with the link"
  - 30 new backend tests covering: org boundary utility, ACL enforcement on docs/folders, folder inheritance chains, cross-org sharing denial, same-org sharing allowed, personal user backward compatibility
  - Backward compatible: personal users (org_id=None) keep all existing sharing behavior

- **SSO Phase 3b**: Readonly Field Security Audit
  - Audited all models for mass-assignment vulnerabilities (server-controlled fields like `owner_id`, `org_id`, `is_deleted`, `created_at`)
  - Confirmed Pydantic schemas (`DocumentCreate`, `DocumentUpdate`, `FolderCreate`, `FolderUpdate`, `UserUpdate`) correctly restrict writable fields
  - Fixed `document_service.update_document`: now validates EDIT access to target folder and enforces org boundary when moving docs via `folder_id`
  - Fixed `folder_service.update_folder`: now validates EDIT access to target parent and enforces org boundary when moving via `parent_id`
  - Fixed `folder_service.create_folder` and `document_service.create_document`: added org boundary checks on parent/folder targets
  - Replaced raw `dict` payload in `add_member` route with typed `AddMemberPayload` Pydantic schema (proper 422 validation)
  - 15 new security tests in `test_readonly_fields.py` covering all mass-assignment scenarios

- **SSO Phase 3c**: SSOLoginFlow UX Fix
  - Fixed silent fallback when SSO is not configured for an email domain
  - Now shows domain-specific error: `No SSO configured for "domain.com". Your organization may not be onboarded yet.`
  - Handles `?error=sso_not_configured`, `?error=saml_invalid`, `?error=oidc_config_error` query params from backend redirects
  - Clears error query params from URL after displaying
  - 16 SSOLoginFlow tests (up from 10)

- **SSO Phase 4**: Admin UI and Self-Serve Onboarding
  - Backend: New `GET /api/orgs/my` endpoint for any authenticated user to view their own org
  - Backend: New `POST /api/orgs/{org_id}/members/invite` endpoint for invite-by-email (finds user, auto-adds membership)
  - Backend: New `PATCH /api/orgs/{org_id}/members/{user_id}/role` endpoint for changing member roles
  - Backend: `InviteMemberPayload` and `UpdateRolePayload` Pydantic schemas
  - Frontend: `SuperAdminPage` at `/admin` — full org management dashboard (create/edit orgs, view members, domain management)
  - Frontend: `OrgSettingsPage` at `/org/:orgId/settings` — three-tab settings page:
    - General: edit org name, slug, verified domains, plan
    - Members: list/invite/remove members, change roles (admin/member)
    - SSO: configure SAML or OIDC, enable/disable toggle, save configuration
  - Frontend: Navigation integration — `Building2` icon in Navbar and MobileSidebar for org settings (conditional on `user.org_id`)
  - Frontend: Routes added to `App.tsx` with `ProtectedRoute` guards
  - Frontend: `orgsApi` updated with `getMyOrg`, `inviteMember`, `updateMemberRole` methods
  - 13 new backend org tests (invite, role change, my org endpoint)
  - 18 SuperAdminPage frontend tests, 28 OrgSettingsPage frontend tests

- **SSO Phase 5**: SCIM 2.0 Provisioning
  - Backend: SCIM auth, service, and routes at `/scim/v2/Users`
  - Backend: Token management in `orgs.py` (generate/revoke)
  - Frontend: SCIM section in OrgSettingsPage SSO tab
  - 82 new backend tests (auth, service, route), 11 new frontend tests

- **Code Quality & Tooling**: Lint, Format, Build Integration
  - Backend: ruff (linter + formatter), pytest-xdist, pytest-cov
  - Frontend: ESLint 9 flat config, Prettier, Vitest 4
  - Unified Makefile: `make lint`, `make format`, `make test`, `make build`, `make ci`

- **404 Page & Access Control**
  - `NotFoundPage.tsx`: themed 404 page with gradient text, Go Home button, dark mode
  - SuperAdminPage & OrgSettingsPage: render NotFoundPage on 403 (no info leakage)
  - `App.tsx`: catch-all route for unknown URLs
  - LandingPage: removed Google login button from navbar, replaced with "Sign In" anchor
  - Backend: deterministic trash sort (secondary `_id` tiebreaker)

- **Phase 16**: CLI Sync Tool (End-to-End)
  - Python CLI (`pip install collabmark`) for bidirectional markdown sync with CollabMark cloud
  - Built with Click + Rich for UX, httpx for async REST, keyring for OS keychain credential storage
  - Browser-based OAuth login flow: CLI opens `/cli-login` page, user authenticates, token relays back via localhost callback
  - API key fallback for headless environments
  - `collabmark login/logout/init/start/stop/status/logs` commands
  - Sync engine: three-way reconciliation (local filesystem vs sync.json state vs cloud tree)
  - Content hash (SHA-256) based change detection with folder structure preservation
  - File watcher: debounced OS filesystem events via `watchdog` (recursive, `.md`-only filtering)
  - Daemon mode with double-fork pattern, PID file management, SIGTERM handling
  - Structured JSON logging with rotating file handler and credential masking
  - Frontend: `/cli-login` page with OAuth flow, `/cli-login/success` confirmation page (matching landing page design, dark/light mode)
  - Backend: `POST /api/auth/cli/token` endpoint for CLI API key exchange, `GET /api/folders/tree` for full folder tree
  - 207 CLI tests covering all modules

- **Phase 17**: CRDT-Based Bidirectional Sync
  - Replaced REST-based content push/pull with WebSocket CRDT sync using pycrdt
  - `crdt_sync.py`: `write_content_via_ws` (new docs), `update_content_via_ws` (existing docs), `read_content_via_ws` (pull)
  - CLI connects to the same `/ws/doc/{id}` endpoint as the web editor
  - Yjs sync protocol handshake implemented in Python (sync step 1/2, awareness)
  - Edits from web editor propagate to CLI in real time (and vice versa)
  - Empty content guards: skip CRDT writes for empty/null content to prevent accidental overwrites
  - `sync_engine.py` updated to use CRDT functions instead of REST for content operations

- **Phase 18**: CLI Sync Observatory (Monitoring & Management)
  - Centralized sync registry at `~/.collabmark/registry.json` tracking all syncs (status, PID, last sync, errors)
  - File locking (`fcntl`) for concurrent registry access safety
  - Per-project PID files (`~/.collabmark/pids/{folder_id}.pid`) for concurrent daemon support
  - Per-project log files (`~/.collabmark/logs/{folder_id}.log`) for isolated logging
  - `collabmark status`: global overview (all syncs table) or project-specific detail view
  - `collabmark list`: alias for global sync overview
  - `collabmark stop`: interactive selection when multiple syncs running, `--all` and `--path` flags
  - `collabmark logs`: per-project viewing, `--all-syncs` for interleaved view, `--folder` for specific project
  - `collabmark clean`: remove stale registry entries (stopped syncs, missing directories), `--all` and `--force` flags
  - Heartbeat tracking: `start` command reports last_synced_at, action count, and errors to registry
  - Dead process detection: `status` prunes crashed processes by checking PID liveness
  - 313 CLI tests total (106 new tests for observatory features)

- **Phase 19**: Google Docs-Style Trash & Restore
  - Hierarchy-aware soft-delete: deleting a folder cascades to all children (nested folders + documents)
  - ACL deactivation on delete: collaborator access disabled for trashed items
  - ACL restoration on restore: own ACLs preserved, parent inheritance broken (restored to root)
  - Trash view: folders clickable to browse contents, documents shown at root when individually deleted
  - Breadcrumb navigation in trash view for deleted folder hierarchies
  - Individual document restore: if parent is deleted, document restores to root level
  - Folder restore: all children restored automatically, own ACLs preserved
  - Redirect to trash view when navigating to a deleted folder URL
  - 404/deleted state handling with proper UI feedback
  - Playwright E2E tests covering all trash/restore scenarios
  - Homepage refresh after restore operations

- **Phase 20**: Production Deployment & CI/CD Enhancements
  - Default CLI API URL switched from localhost to Railway production (`https://web-production-5e1bc.up.railway.app`)
  - Environment variable overrides (`COLLABMARK_API_URL`, `COLLABMARK_FRONTEND_URL`) for local development
  - CI pipeline: added `lint-cli` and `test-cli` jobs to `.github/workflows/ci.yml`
  - PyPI release workflow: `.github/workflows/cli-release.yml` triggered by `cli-v*` tags
  - Trusted publishing via `pypa/gh-action-pypi-publish` (OIDC-based, no API token needed)
  - Build and deploy gates include CLI checks

- **Phase 21**: CRDT User Attribution
  - Queue-based approach: `MongoYStore` uses `collections.deque` (FIFO) to associate user IDs with CRDT updates
  - WebSocket handler enqueues user ID when a Y.Doc-modifying message is received; store pops it when writing to MongoDB
  - Each CRDT update in MongoDB now carries `metadata.user_id` for audit trail
  - `apply_incremental_diff` in CLI: uses `difflib.SequenceMatcher` for efficient, minimal CRDT updates (avoids sending full document)
  - CLI CRDT writes also carry user attribution

- **Phase 22**: Email Notification System
  - Channel-agnostic notification infrastructure (extensible to in-app, push, campaign notifications)
  - **Delayed dispatch**: notifications scheduled with configurable delay (default 60s) via Redis sorted set
  - **Pre-send validation**: scheduler verifies the triggering action still exists before sending (prevents notifications for reverted actions -- e.g., comment added then deleted, or share granted then revoked)
  - **Event types**: `document_shared`, `folder_shared`, `comment_added`
  - **Email providers**: Resend API and generic SMTP (auto-detected STARTTLS support)
  - **Branded HTML templates**: gradient header, Inter font, CTA buttons, direct links matching CollabMark web UI
  - **Retry mechanism**: Redis-backed queue with exponential backoff (max 3 retries)
  - **User preferences**: per-event/per-channel opt-in/out via `NotificationPreference` model
  - **Integration points**: `share_service`, `folder_service`, `group_sharing_service`, `comment_service` all schedule notifications
  - **Local testing**: Mailpit (docker-compose) for local SMTP email capture
  - **Production**: Resend API with Railway environment variables
  - 68 notification tests at 99% coverage
  - Backend architecture:
    - `notification_dispatcher.py`: schedules + delivers via registered channels
    - `notification_scheduler.py`: background loop polling Redis ZSET for due notifications
    - `notification_retry.py`: background loop for failed sends with exponential backoff
    - `channels/email.py`: Resend API + SMTP delivery
    - `channels/templates.py`: branded HTML email templates
    - `channels/base.py`: abstract channel interface

- **Phase 23**: CLI Auth Fix, Migration Cleanup & Technical Documentation
  - Fixed CLI browser login: updated callback handler to capture `code` param (not `token`) and exchange it via `POST /api/auth/cli/exchange` for the JWT
  - Added `_exchange_code_for_jwt()` helper in `browser_auth.py`
  - Removed legacy `detect_and_migrate()`, `migrate_local_project()`, and `PROJECT_DIR_NAME` from CLI config
  - Removed `init` command entirely (redundant — `start` handles folder linking)
  - Removed vestigial migration calls from `start` command
  - Updated CLI README to reference centralized `~/.collabmark/projects/` storage
  - Added technical documentation: `docs/architecture.md`, `docs/api-reference.md`, `docs/cli-reference.md`, `docs/deployment.md`, `docs/ci-cd.md`
  - Added Makefile targets: `test-cli`, `lint-cli`, `test-all`, `verify`
  - Updated `lint` and `test` targets to include CLI

**Total: 1002 backend tests, 945 frontend tests, 408 CLI tests (all passing).**

## Tech Stack

| Layer       | Technology                                        |
|-------------|---------------------------------------------------|
| Backend     | Python 3.12+, FastAPI, Uvicorn, Gunicorn          |
| Database    | MongoDB 7 (Beanie ODM, Motor async driver)        |
| CRDT Server | pycrdt + pycrdt-websocket                         |
| CRDT Client | Yjs + y-codemirror.next + y-websocket             |
| Frontend    | React 19, Vite 7, TypeScript 5.9                  |
| Styling     | Tailwind CSS v4                                   |
| Editor      | CodeMirror 6 (core API + yCollab)                 |
| Auth        | Google OAuth2 (authlib), JWT (python-jose), API keys |
| Diffing     | diff (jsdiff) for version history diff view       |
| Blob Storage| MinIO (S3-compatible), boto3 client                |
| Notifications| Resend API / SMTP, Redis (delayed scheduling + retry) |
| Message Bus | Redis (notification scheduling, future: pub/sub for WS) |
| Testing BE  | pytest, pytest-asyncio, httpx, mongomock-motor    |
| Testing FE  | Vitest, React Testing Library, jsdom              |
| CLI         | Python 3.12+, Click, Rich, httpx, pycrdt, watchdog, keyring     |
| Testing CLI | pytest, pytest-asyncio, respx                                   |
| Deployment  | Docker, Railway (with MongoDB, Redis & MinIO/S3 add-ons), Gunicorn |

## Project Structure

```
collabmark/
  backend/           # Python FastAPI application
    app/
      auth/          # OAuth, JWT, API key, SSO (SAML/OIDC) auth
      models/        # Beanie document models
        user.py, document.py, api_key.py, share_link.py,
        document_version.py, document_view.py, comment.py,
        folder.py, notification.py, organization.py,
        org_sso_config.py, group.py
      routes/        # REST API endpoints
        auth.py, documents.py, keys.py, sharing.py,
        versions.py, comments.py, users.py,
        folders.py, notifications.py, orgs.py, scim.py, ws.py
      services/      # Business logic layer
        document_service.py, share_service.py, version_service.py,
        comment_service.py, folder_service.py, crdt_store.py,
        org_service.py, acl_service.py, scim_service.py,
        group_sharing_service.py, blob_storage.py,
        notification_dispatcher.py, notification_scheduler.py,
        notification_retry.py
        channels/    # Notification channels
          base.py, email.py, templates.py
      ws/            # WebSocket handler (pycrdt rooms)
    tests/           # Backend test suite (1002 tests)
  frontend/          # React SPA (Vite + TypeScript)
    src/
      components/    # Reusable UI components
        Auth/, Editor/, Home/, Layout/, Settings/
        Editor/DiffView.tsx       # jsdiff line-level diff rendering
        Editor/VersionHistory.tsx # Diff + restore slide-out panel
        Editor/EditorToolbar.tsx  # Toolbar with navigate(-1) back
        Home/DocumentContextMenu.tsx  # Right-click context menu
        Home/DocumentInfoModal.tsx    # Document metadata modal
        Home/FolderBreadcrumbs.tsx    # Hierarchical navigation
        Home/CreateFolderDialog.tsx   # New folder creation
        Home/FolderInfoModal.tsx      # Folder metadata modal
        Home/RenameDialog.tsx         # Inline rename modal
        Home/ConfirmDialog.tsx        # Confirmation modal
        Home/ToastContainer.tsx       # Animated toast notifications
      pages/         # Route-level page components
        HomePage, EditorPage, LoginPage, SettingsPage,
        ProfilePage, ApiDocsPage
      hooks/         # Custom React hooks / Zustand stores
        useAuth, useDocuments, useFolders, useToast,
        useYjsProvider, useComments, useCommentAnchors,
        useCommentPositions
      lib/           # API client, utilities
        api.ts       # Axios client with all API methods
        dateUtils.ts # Local time formatting utilities
  cli/               # Python CLI tool (pip install collabmark)
    src/collabmark/
      commands/      # CLI commands (init, login, start, stop, status, logs, list, clean)
      lib/           # Core libraries (api, auth, config, crdt_sync, daemon, logger, registry, sync_engine, watcher)
    tests/           # 408 CLI tests
    pyproject.toml   # hatchling build + CLI entry point
  docs/              # Technical documentation
    architecture.md  # System architecture overview
    api-reference.md # API endpoint reference
    cli-reference.md # CLI command reference
    deployment.md    # Deployment guide (local + production)
    ci-cd.md         # CI/CD pipeline documentation
    marketing/       # Marketing materials (dev.to, Product Hunt, Reddit)
  Dockerfile         # Multi-stage (build frontend + bundle with backend)
  docker-compose.yml # MongoDB + Redis + MinIO + Mailpit for local dev
  docker-compose.prod.yml # Production compose
  railway.toml       # Railway deployment config
  Procfile           # Heroku/Railway process file
  Makefile           # Unified build system (install, test, lint, format, build, ci, verify)
  agent.md           # THIS FILE -- agent reference
  .cursor/skills/    # Cursor AI skills (pre-commit checklist, toast-on-action, write-code)
```

## Cursor Skills (`.cursor/skills/`)

| Skill | When to Use |
|-------|-------------|
| `pre-commit-checklist` | Before every commit -- lint, format, security audit, tests (>90% coverage), build |
| `toast-on-action` | When writing frontend async actions -- ensure success/error toast for every mutation |
| `write-code` | When writing/modifying any code -- DRY, YAGNI, single responsibility, naming, readability |

## API Endpoints

### Auth
- `GET /api/auth/google/login` -- redirect to Google OAuth
- `GET /api/auth/google/callback` -- OAuth callback, set JWT cookie
- `POST /api/auth/logout` -- clear session
- `POST /api/auth/sso/detect` -- detect SSO org by email domain
- `GET /api/auth/sso/saml/login/{org_id}` -- redirect to SAML IdP
- `POST /api/auth/sso/saml/callback` -- SAML ACS (assertion consumer service)
- `GET /api/auth/sso/oidc/login/{org_id}` -- redirect to OIDC IdP
- `GET /api/auth/sso/oidc/callback` -- OIDC authorization code callback

### Users
- `GET /api/users/me` -- current user profile
- `PUT /api/users/me` -- update profile

### Documents
- `POST /api/documents` -- create document (accepts optional `folder_id`)
- `GET /api/documents` -- list own documents
- `GET /api/documents/trash` -- list soft-deleted documents
- `GET /api/documents/{id}` -- get document (owner or shared)
- `PUT /api/documents/{id}` -- update document (owner or edit access, accepts `folder_id`)
- `DELETE /api/documents/{id}` -- soft-delete (owner only)
- `POST /api/documents/{id}/restore` -- restore (owner only)
- `DELETE /api/documents/{id}/permanent` -- hard-delete with full cleanup (owner only)

### Folders
- `POST /api/folders` -- create folder (accepts optional `parent_id`)
- `GET /api/folders/{id}` -- get folder
- `PUT /api/folders/{id}` -- update folder (name, parent_id)
- `DELETE /api/folders/{id}` -- cascade soft-delete (owner only)
- `POST /api/folders/{id}/restore` -- cascade restore (owner only)
- `DELETE /api/folders/{id}/permanent` -- cascade hard-delete (owner only)
- `GET /api/folders/trash` -- list trashed folders
- `GET /api/folders/shared` -- list folders shared with me
- `GET /api/folders/contents` -- list contents of a folder (or root)
- `GET /api/folders/breadcrumbs` -- get breadcrumb path for a folder
- `GET /api/folders/tree` -- full folder tree with documents (used by CLI sync)
- `POST /api/folders/{id}/collaborators` -- add folder collaborator
- `GET /api/folders/{id}/collaborators` -- list folder collaborators
- `DELETE /api/folders/{id}/collaborators/{user_id}` -- remove folder collaborator

### Sharing
- `PUT /api/documents/{id}/access` -- update general access setting (owner only)
- `POST /api/documents/{id}/collaborators` -- add collaborator by email (owner only)
- `GET /api/documents/{id}/collaborators` -- list collaborators (owner only)
- `DELETE /api/documents/{id}/collaborators/{user_id}` -- remove collaborator (owner only)
- `GET /api/documents/shared` -- list docs shared with me
- `POST /api/documents/{id}/view` -- record document view (all docs including own)
- `GET /api/documents/recent` -- list all recently viewed docs (including own, sorted by recency)

### Versions
- `POST /api/documents/{id}/versions` -- create version snapshot (returns 204 if deduplicated)
- `GET /api/documents/{id}/versions` -- list version timeline
- `GET /api/documents/{id}/versions/{num}` -- get version detail

### Comments
- `POST /api/documents/{id}/comments` -- create comment (accepts anchor_from_relative, anchor_to_relative)
- `GET /api/documents/{id}/comments` -- list comments with replies (includes orphaned)
- `POST /api/comments/{id}/reply` -- reply to comment
- `POST /api/comments/{id}/resolve` -- resolve comment
- `PATCH /api/comments/{id}/reanchor` -- update absolute anchor offsets after frontend re-resolution
- `PATCH /api/comments/{id}/orphan` -- mark comment as orphaned (anchored text was deleted)
- `DELETE /api/comments/{id}` -- delete comment

### Export (frontend-only via window.print)
- PDF export moved to frontend using presentation mode + window.print()

### API Keys
- `POST /api/keys` -- create API key
- `GET /api/keys` -- list API keys
- `DELETE /api/keys/{id}` -- revoke API key

### CLI Auth
- `GET /api/auth/cli/complete?port=XXXX` -- issues a short-lived auth code and redirects to CLI's local server
- `POST /api/auth/cli/exchange` -- exchanges the auth code for a JWT token
- `POST /api/keys` -- CLI exchanges JWT for a persistent API key (reuses existing key if present)
- `GET /cli-login` -- browser-based CLI login page (OAuth redirect + code relay)

### WebSocket
- `WS /ws/doc/{document_id}` -- CRDT collaboration (VIEW or EDIT access required, used by both web editor and CLI)

### Organizations
- `GET /api/orgs/my` -- current user's org (or null for personal users)
- `POST /api/orgs` -- create organization (super admin)
- `GET /api/orgs` -- list all organizations (super admin)
- `GET /api/orgs/{org_id}` -- get org details (org admin)
- `PUT /api/orgs/{org_id}` -- update org (org admin)
- `GET /api/orgs/{org_id}/members` -- list members (org admin)
- `POST /api/orgs/{org_id}/members` -- add member by user_id (org admin)
- `POST /api/orgs/{org_id}/members/invite` -- invite member by email (org admin)
- `PATCH /api/orgs/{org_id}/members/{user_id}/role` -- change member role (org admin)
- `DELETE /api/orgs/{org_id}/members/{user_id}` -- remove member (org admin)
- `GET /api/orgs/{org_id}/sso` -- get SSO config (org admin)
- `PUT /api/orgs/{org_id}/sso` -- create/update SSO config (org admin)

### Notifications
- `GET /api/notifications` -- list current user's notifications (paginated: `limit`, `offset`)
- `PATCH /api/notifications/{id}/read` -- mark notification as read
- `GET /api/notifications/preferences` -- get notification preferences
- `PUT /api/notifications/preferences` -- update notification preferences

### Frontend Pages
- `/` -- Home page (Files browser, shared docs, recently viewed, trash)
- `/login` -- Google OAuth login
- `/edit/:id` -- Document editor (also the share URL)
- `/settings` -- API key management
- `/profile` -- User profile
- `/api-docs` -- Interactive API documentation (public, no auth required)
- `/admin` -- Super admin dashboard (create/manage organizations, view members)
- `/org/:orgId/settings` -- Organization settings (General, Members, SSO config)
- `/cli-login` -- CLI browser-based login (OAuth flow with auth code relay back to CLI)

## Coding Guidelines

### General
- Every public function, class, and module MUST have a docstring
- Python: Google-style docstrings with type hints on all parameters and return values
- TypeScript: TSDoc comments on exported functions and interfaces
- Keep functions small and single-purpose for testability
- Use dependency injection (FastAPI Depends) on the backend
- Async/await everywhere -- no blocking calls

### Testing Standards
- Write tests for EVERY function/endpoint, backend AND frontend
- Tests must assert specific expected values (e.g., `assert data["title"] == "My Doc"`)
- Never use generic truthy assertions (e.g., avoid `assert response.json()`)
- Include edge cases: empty inputs, boundary values, auth failures, not-found, concurrent ops
- Backend: pytest + pytest-asyncio + httpx ASGI transport + mongomock-motor
- Frontend: Vitest + React Testing Library + jsdom + @testing-library/user-event
- Test files mirror source structure: `test_<module>.py` / `<Component>.test.tsx`
- Frontend: do NOT import `screen` directly from @testing-library/react (CI issue); destructure from `render()` return instead

### Backend Conventions
- Models in `app/models/` are Beanie Documents with `Settings.name` for collection
- Service layer in `app/services/` contains business logic (not in routes)
- Routes in `app/routes/` are thin -- delegate to services
- Auth via `Depends(get_current_user)` which supports both JWT cookie and API key
- All datetime fields use UTC (`datetime.now(timezone.utc)`)
- Use `Indexed()` on frequently queried fields
- Static routes (e.g., `/api/documents/shared`) must be registered before parameterized routes (e.g., `/api/documents/{doc_id}`)

### Frontend Conventions
- State management via Zustand stores in `hooks/`
- API calls via axios client in `lib/api.ts`
- Components are functional with TypeScript interfaces for props
- Tailwind CSS utility classes; CSS custom properties for theme colors
- Vite proxy forwards `/api` and `/ws` to backend at localhost:8000
- Dark mode via `.dark` class on `<html>` with CSS custom property overrides
- Date/time display uses `dateUtils.ts` (formatDateShort, formatDateLong, formatDateTime) for consistent local time formatting
- Toast notifications via `useToast` Zustand store for all mutation feedback

### Git & Commits
- Branch format: `{username}/{description}` (kebab-case)
- Commit messages: concise, explain "why" not "what"
- All tests must pass before committing

## Architectural Decisions

### SSO via SAML 2.0 + OIDC (Dual Protocol)
Both protocols supported per-org via OrgSSOConfig. Email-domain-based IdP detection
(`POST /api/auth/sso/detect`) checks `Organization.verified_domains` and routes to
the correct protocol. SAML uses python3-saml (OneLogin) for AuthnRequest/Response.
OIDC uses authlib for discovery, authorization, and token exchange. Shared
`SSOCallbackResult` dataclass normalizes both flows before `find_or_create_sso_user`.
Google OAuth remains as the default for personal (non-org) users. SSO users get
`auth_provider="saml"|"oidc"` and `org_id` set on their User document.

### CRDT over OT
CRDTs allow decentralized conflict resolution without a central arbiter.
No server-side transformation needed; the math guarantees convergence.
Supports offline editing and re-sync naturally.

### Yjs (client) + pycrdt (server)
Client uses Yjs + y-codemirror.next for seamless CodeMirror 6 integration.
Server uses pycrdt-websocket for room-based document sync with a custom MongoDB store.
The Yjs awareness protocol provides user presence (cursors, names, colors).

### MongoDB for CRDT persistence
CRDT binary state (encoded Y.Doc updates) stored in MongoDB.
Custom Store class implements pycrdt-websocket's store interface.
Periodic compaction merges incremental updates to prevent unbounded growth.

### Permission-aware document access (Google Docs model)
Owner has full control (CRUD, share, delete/restore).
Access is determined by a four-tier priority: owner > explicit DocumentAccess > folder access inheritance > general_access > deny.

**general_access** field on Document_ controls link-based access:
- `restricted`: only owner and explicit collaborators can access
- `anyone_view`: any authenticated user with the URL can view
- `anyone_edit`: any authenticated user with the URL can edit

**Explicit collaborators** are added by email via `POST /api/documents/{id}/collaborators`.
The share link is simply the document URL (`/edit/{doc_id}`).

**Folder access inheritance**: documents within a folder inherit the folder's ACLs. If a folder is shared with a user, they can access all documents within it at the folder's permission level.

WebSocket connections require at least VIEW permission (VIEW or EDIT users can connect).
Write permissions are enforced by the editor UI (read-only mode for VIEW users).

### Version History via content snapshots with deduplication
Document content is snapshotted automatically (30s idle + 5min rate limit).
Versions stored in `document_versions` collection with author metadata.
Deduplication: if content is identical to the latest version, no new version is created.
Diff view shows line-level changes between selected version and current document.
Restore replaces Yjs content and creates a new attributed snapshot.

### Spaces (Folders) -- Hierarchical Document Organization
Folders are a separate entity (`Folder` model) with their own ACLs (`FolderAccess` model).
Folders support nesting (parent_id) and cascade operations (soft-delete, restore, hard-delete).
Documents can optionally belong to a folder via `folder_id` field.
Frontend presents a file-browser view with breadcrumb navigation.

### Comments via MongoDB + single-depth threads
Comments stored in MongoDB `comments` collection (not in CRDT state).
Single-depth reply threads via parent_id self-reference.
Comments can be resolved or deleted by author.

### Comment Anchoring via Yjs RelativePositions
Inline comments use three anchoring mechanisms:
1. **Yjs RelativePositions** (anchor_from_relative/anchor_to_relative): CRDT-aware
   positions serialised as Base64 Uint8Arrays. Primary source of truth for positioning.
   Created via `Y.createRelativePositionFromTypeIndex()` on the frontend when the user
   selects text and adds a comment. Survive concurrent insertions and deletions.
2. **Absolute offsets** (anchor_from/anchor_to): snapshot character positions, periodically
   refreshed by the frontend via `PATCH /reanchor` when drift is detected.
3. **Quoted text** (quoted_text): immutable snapshot of the selected text at creation time.
   Used for human-readable context and reconciliation check.

When referenced text is deleted (RelativePositions collapse to same point), the comment
is marked as **orphaned** (`is_orphaned=True`, `orphaned_at` timestamp set). Orphaned
comments remain visible in the global comments panel with a "Referenced text was removed"
badge and the original quoted_text displayed with strikethrough. They can still be replied
to and resolved.

### Position-synced Comment Gutter (Google Docs style)
The comments panel on the right uses CodeMirror's `coordsAtPos()` to align each comment
card vertically with its anchored text in the editor. When multiple comments are on the
same line, a top-down stacking algorithm pushes cards below each other with an 8px gap.
Displaced cards show a dashed connecting line to their ideal position. Orphaned comments
are shown in a separate "Orphaned" section at the bottom of the panel.

### CRDT User Attribution (Queue-Based)
`pycrdt-websocket` does not propagate user context to the store layer. Instead, `MongoYStore`
maintains a FIFO `collections.deque` of user IDs. When the WebSocket handler receives a
Y.Doc-modifying message (sync step 2 / update), it calls `store.enqueue_user(user_id)`.
When the store writes an update to MongoDB, it pops from the queue and attaches
`metadata.user_id`. This avoids ContextVar limitations and works reliably with the
pycrdt-websocket room lifecycle.

### Email Notifications with Delayed Dispatch
Notifications are not sent immediately. When a triggering action occurs (document share,
folder share, comment), a `Notification` document is created with `status=SCHEDULED` and
`scheduled_for = now + delay` (default 60 seconds). The notification ID is added to a Redis
sorted set keyed by delivery time.

A background `scheduler_loop` polls the ZSET every 10 seconds for due items. Before sending,
it calls `_validate_action_exists()` to verify the triggering action hasn't been reverted:
- `DOCUMENT_SHARED`: checks `DocumentAccess.get(action_ref_id)`
- `FOLDER_SHARED`: checks `FolderAccess.get(action_ref_id)`
- `COMMENT_ADDED`: checks `Comment.get(action_ref_id)`

If the action no longer exists, the notification is marked `SKIPPED`. Otherwise, it's
delivered via the registered channel (currently `EmailChannel` supporting Resend API or SMTP).

Failed sends are pushed to a Redis retry list. A `retry_loop` processes items with exponential
backoff (base 30s, max 3 retries). The system is extensible: new channels (in-app, push)
can be added by implementing `BaseChannel` and registering with the dispatcher.

### Notification Environment Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `NOTIFICATIONS_ENABLED` | Enable/disable system | `true` |
| `NOTIFICATION_EMAIL_PROVIDER` | `resend` or `smtp` | `resend` |
| `NOTIFICATION_FROM_EMAIL` | Sender address | `onboarding@resend.dev` |
| `NOTIFICATION_DELAY_SECONDS` | Delay before sending | `60` |
| `RESEND_API_KEY` | Resend API key | `re_...` |
| `SMTP_HOST` | SMTP server host | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP server port | `587` |
| `SMTP_USER` | SMTP auth username | (optional) |
| `SMTP_PASSWORD` | SMTP auth password | (optional) |

## Common Pitfalls & Technical Challenges

### Frontend Testing
- **`screen` import issue**: `@testing-library/react` in CI doesn't export `screen` properly. Always destructure from `render()` return value instead.
- **`@testing-library/dom`**: Must be listed as an explicit devDependency for CI to work with yarn.
- **Toast test ordering**: Toasts are prepended (newest first), not appended. Tests must find toasts by message content, not array index.
- **Ambiguous selectors**: When multiple elements have the same text (e.g., "Delete" button + modal title), use more specific selectors like `getByRole('button', { name: ... })`.

### Backend Testing
- **Beanie model fields**: Models like `Comment` and `DocumentVersion` have required fields (`author_id`, `author_name`, `version_number`) that must be provided in test fixtures.
- **Route ordering**: Static routes (e.g., `/trash`, `/shared`, `/contents`) MUST be registered before parameterized routes (e.g., `/{doc_id}`) in FastAPI routers.

### CI/CD
- **npm vs yarn**: Use `corepack enable && yarn install` in CI to align with the Dockerfile. npm has caused crashes in GitHub Actions.
- **Git auth**: When pushing, ensure the correct GitHub CLI user is active (`gh auth switch --user <username>`).

### CRDT & Real-time
- **Content persistence on deploy**: `pycrdt-websocket`'s `YRoom` must explicitly load existing data from `MongoYStore` when a room is opened. Without this, deployments cause content loss until the room is re-opened by a client with local state.

### Notifications
- **Redis `stop-writes-on-bgsave-error`**: Local Redis may refuse writes if it can't persist RDB snapshots. Fix with `CONFIG SET stop-writes-on-bgsave-error no`.
- **STARTTLS detection**: SMTP code uses `server.has_extn("starttls")` instead of port-based detection. Mailpit (port 1025) is plain SMTP; production SMTP (port 587) typically supports STARTTLS.
- **Resend test sender**: `onboarding@resend.dev` works without domain verification but emails may land in spam. Verify a custom domain in Resend for production use.
- **Mocking scope**: When testing dispatcher in services, patch `get_dispatcher` in the *consuming* module (e.g., `app.services.share_service.get_dispatcher`), not the defining module.

### Blob Storage (S3/MinIO)
- **Local dev**: MinIO container in `docker-compose.yml` (API: port 9002, Console: port 9003). Default credentials: `collabmark` / `collabmark-secret`.
- **Production (Railway)**: Add an S3-compatible storage service. Required environment variables:
  - `S3_ENDPOINT_URL` -- MinIO or S3-compatible endpoint (e.g. `https://minio-production.railway.internal:9000` or AWS S3 URL)
  - `S3_ACCESS_KEY` -- Access key / AWS access key ID
  - `S3_SECRET_KEY` -- Secret key / AWS secret access key
  - `S3_BUCKET` -- Bucket name (default: `collabmark-media`)
  - `S3_REGION` -- Region (default: `us-east-1`)
- **Architecture**: `blob_storage.py` service wraps boto3. Uploads go to S3, served via `/media/{key}` proxy route in `main.py`. Bucket is auto-created if missing.
- **MinIO console**: Accessible at `http://localhost:9003` for local debugging.

## Release Process

### Web Application (Backend + Frontend)

Deployed automatically via GitHub Actions CI/CD pipeline:

1. Push to `main` triggers the `CI` workflow (`.github/workflows/ci.yml`)
2. Pipeline: lint (backend + frontend + CLI) -> test (backend + frontend + CLI) -> build -> deploy
3. Deploy step uses Railway CLI with `RAILWAY_TOKEN` and `RAILWAY_SERVICE_ID` secrets
4. If any test/build step fails, the `rollback` job auto-reverts the commit on `main`
5. Production URL: `https://web-production-5e1bc.up.railway.app`

### CLI Tool (PyPI)

Published via GitHub Actions on tagged releases:

1. Update version in `cli/src/collabmark/__init__.py` and `cli/pyproject.toml`
2. Commit: `git commit -m "chore: bump CLI version to X.Y.Z"`
3. Tag: `git tag cli-vX.Y.Z`
4. Push: `git push origin main --tags`
5. The `cli-release.yml` workflow runs lint, tests, builds via `hatch`, and publishes to PyPI
6. Uses trusted publishing (OIDC `id-token: write`) -- requires PyPI "Trusted Publisher" configuration:
   - PyPI project: `collabmark`
   - GitHub owner: `KRHero03`
   - Repository: `collabmark`
   - Workflow: `cli-release.yml`
   - Environment: `pypi`
7. Users install via: `pip install collabmark`

### Pre-Release Checklist

1. `ruff check` + `ruff format --check` on all Python code (backend + CLI)
2. `yarn run check` on frontend (tsc + eslint + prettier)
3. All tests passing: backend (1002), frontend (945), CLI (342)
4. Security audit: no hardcoded secrets, all routes have auth, typed Pydantic schemas
5. Frontend production build succeeds (`yarn build`)
6. Dead code scan: no unused imports, functions, or test cases

### Environment Configuration

The CLI defaults to the Railway production URL. For local development, override via environment variables:

```bash
export COLLABMARK_API_URL=http://localhost:8000
export COLLABMARK_FRONTEND_URL=http://localhost:5173
```

## CLI Architecture

### Sync Flow (CRDT-based)

1. **Authentication**: Browser OAuth -> auth code exchange -> JWT -> API key stored in OS keychain via `keyring`
2. **Init**: Link local directory to cloud folder, store config centrally in `~/.collabmark/projects/`, register in global registry
3. **Sync cycle**:
   - Local scan: recursive `.md` file discovery with SHA-256 content hashing
   - Cloud scan: `GET /api/folders/tree` for full folder+document tree
   - Three-way reconciliation: compare local state, `sync.json` (last known), cloud state
   - Actions: PUSH_NEW, PUSH_UPDATE, PULL_NEW, PULL_UPDATE, DELETE_LOCAL, DELETE_REMOTE, CONFLICT
   - CRDT operations: connect to `/ws/doc/{id}` via WebSocket, apply pycrdt document updates
4. **Watch**: `watchdog` filesystem events (debounced 2s) + periodic cloud polling
5. **Registry**: heartbeat updates to `~/.collabmark/registry.json` after each cycle

### Credential Security

- API keys stored in OS keychain via `keyring` (macOS Keychain, Windows Credential Locker, Linux SecretService)
- `credentials.json` contains only non-sensitive metadata (email, name, server URL)
- Logger masks API keys and tokens in all log output
- No credentials in `.collabmark/config.json` (only folder ID, server URL, user display info)
