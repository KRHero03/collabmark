# CollabMark -- Agent Guidelines & Progress

This file serves as a self-reference guide for AI agents working on this project.
It tracks progress, conventions, architectural decisions, and coding standards.

## Project Overview

CollabMark is a collaborative Markdown editor (Google Docs-style) with:
- Real-time multi-user editing via CRDTs (Yjs/pycrdt)
- Google OAuth sign-in
- API key access for programmatic use
- Google Docs-style document sharing (general access + email-based collaborators)
- Version history with author attribution
- Inline and doc-level commenting system
- PDF and Markdown export
- Dark mode support
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
  - Permission checks: owner > explicit DocumentAccess > general_access > deny
  - Frontend: Google Docs-style ShareDialog (add by email, people with access list, general access toggle, copy link), sharingApi client
  - Old token-based share link system removed (ShareLink model deprecated, SharedDocRedirect removed)
  - 22 sharing-related tests + updated integration tests
- **Phase 5**: Version History
  - Backend: DocumentVersion model, version_service.py, version routes, auto-snapshot on document save
  - Frontend: VersionHistory slide-out panel, version timeline, read-only snapshot preview, versionsApi client
  - 10 version tests
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
  - Frontend: PDF export button, dark mode toggle (CSS custom properties), Profile page, Ctrl+S keyboard shortcut
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
  - **Recently Viewed tab**: New `DocumentView` model tracks when users view non-owned docs.
    `POST /api/documents/{id}/view` records or updates view timestamp (no-op for owners).
    `GET /api/documents/recent` returns recently viewed docs sorted by recency, excluding
    deleted docs and docs the user has lost access to. EditorPage records a view on load.
    HomePage has a third "Recently viewed" tab with owner info and permission badges.
  - 17 backend tests (record view: 7 tests, list recently viewed: 10 tests)
  - 10 frontend tests (MarkdownPreview rendering, memoization, GFM features)

**Total: 117 backend tests, 46 frontend tests, all passing**

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
| Message Bus | Redis (future: pub/sub for WS horizontal scaling) |
| Testing BE  | pytest, pytest-asyncio, httpx, mongomock-motor    |
| Testing FE  | Vitest, React Testing Library, jsdom              |
| Deployment  | Docker, Railway (with MongoDB & Redis add-ons), Gunicorn |

## Project Structure

```
collabmark/
  backend/           # Python FastAPI application
    app/
      auth/          # OAuth, JWT, API key auth
      models/        # Beanie document models
        user.py, document.py, api_key.py, share_link.py,
        document_version.py, document_view.py, comment.py
      routes/        # REST API endpoints
        auth.py, documents.py, keys.py, sharing.py,
        versions.py, comments.py, export.py, users.py, ws.py
      services/      # Business logic layer
        document_service.py, share_service.py, version_service.py,
        comment_service.py, crdt_store.py
      ws/            # WebSocket handler (pycrdt rooms)
    tests/           # Backend test suite (97 tests)
  frontend/          # React SPA (Vite + TypeScript)
    src/
      components/    # Reusable UI components
        Auth/, Editor/, Home/, Layout/, Settings/
      pages/         # Route-level page components
        HomePage, EditorPage, LoginPage, SettingsPage,
        ProfilePage, ApiDocsPage
      hooks/         # Custom React hooks
        useAuth, useDocuments, useYjsProvider, useComments,
        useCommentAnchors, useCommentPositions
      lib/           # API client, utilities
  Dockerfile         # Multi-stage (build frontend + bundle with backend)
  docker-compose.yml # MongoDB + Redis for local dev
  docker-compose.prod.yml # Production compose
  railway.toml       # Railway deployment config
  Procfile           # Heroku/Railway process file
  agent.md           # THIS FILE -- agent reference
```

## API Endpoints

### Auth
- `GET /api/auth/google/login` -- redirect to Google OAuth
- `GET /api/auth/google/callback` -- OAuth callback, set JWT cookie
- `POST /api/auth/logout` -- clear session

### Users
- `GET /api/users/me` -- current user profile
- `PUT /api/users/me` -- update profile

### Documents
- `POST /api/documents` -- create document
- `GET /api/documents` -- list own documents
- `GET /api/documents/{id}` -- get document (owner or shared)
- `PUT /api/documents/{id}` -- update document (owner or edit access)
- `DELETE /api/documents/{id}` -- soft-delete (owner only)
- `POST /api/documents/{id}/restore` -- restore (owner only)

### Sharing
- `PUT /api/documents/{id}/access` -- update general access setting (owner only)
- `POST /api/documents/{id}/collaborators` -- add collaborator by email (owner only)
- `GET /api/documents/{id}/collaborators` -- list collaborators (owner only)
- `DELETE /api/documents/{id}/collaborators/{user_id}` -- remove collaborator (owner only)
- `GET /api/documents/shared` -- list docs shared with me
- `POST /api/documents/{id}/view` -- record document view (for "Recently Viewed" tab)
- `GET /api/documents/recent` -- list recently viewed docs (non-owned, sorted by recency)

### Versions
- `POST /api/documents/{id}/versions` -- create version snapshot
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

### WebSocket
- `WS /ws/doc/{document_id}` -- CRDT collaboration (VIEW or EDIT access required)

### Frontend Pages
- `/` -- Home page (owned docs, shared docs, recent access)
- `/login` -- Google OAuth login
- `/edit/:id` -- Document editor (also the share URL)
- `/settings` -- API key management
- `/profile` -- User profile
- `/api-docs` -- Interactive API documentation (public, no auth required)

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

### Git & Commits
- Branch format: `{username}/{description}` (kebab-case)
- Commit messages: concise, explain "why" not "what"
- All tests must pass before committing

## Architectural Decisions

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
Access is determined by a three-tier priority: owner > explicit DocumentAccess > general_access > deny.

**general_access** field on Document_ controls link-based access:
- `restricted`: only owner and explicit collaborators can access
- `anyone_view`: any authenticated user with the URL can view
- `anyone_edit`: any authenticated user with the URL can edit

**Explicit collaborators** are added by email via `POST /api/documents/{id}/collaborators`.
The share link is simply the document URL (`/edit/{doc_id}`).

WebSocket connections require at least VIEW permission (VIEW or EDIT users can connect).
Write permissions are enforced by the editor UI (read-only mode for VIEW users).

### Version History via content snapshots
Document content is snapshotted on each save (auto-versioning).
Versions stored in `document_versions` collection with author metadata.
Read-only preview reconstructs the document at any point in time.

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
