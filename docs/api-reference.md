# API Reference

## Authentication

CollabMark supports two authentication methods:

- **JWT cookie** (`access_token`) -- Set automatically after Google OAuth or SSO login. The cookie is HTTP-only, secure, and SameSite=Lax.
- **API key header** (`X-API-Key`) -- For CLI and programmatic access. Generate keys via `POST /api/keys`.

When both are present, the API key takes precedence.

WebSocket connections authenticate via the `access_token` cookie or an `api_key` query parameter.

## Rate Limiting

Rate limits are enforced per-client using `slowapi`. Exceeding a limit returns `429 Too Many Requests`.

| Category | Limit |
|---|---|
| Auth endpoints | 10/minute |
| SSO detect | 15/minute |
| Upload (images, attachments, logos) | 20-30/minute |
| SCIM reads | 120/minute |
| SCIM mutations | 60/minute |
| SCIM deletes | 30/minute |
| API key create/revoke | 10/minute |
| SCIM token generation | 5/minute |

---

## Endpoints

### Health

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/api/health` | Health check for load balancers and monitoring. Returns `{"status": "ok", "service": "collabmark", "version": "1.0.0"}`. | No |

---

### Auth

All auth endpoints use the `/api/auth` prefix.

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/api/auth/google/login` | Redirect to Google OAuth consent screen. | No |
| GET | `/api/auth/google/callback` | Handle Google OAuth callback; creates/updates user and sets JWT cookie. | No |
| GET | `/api/auth/cli/complete` | Issue a short-lived auth code and redirect to the CLI's local server. Requires an active JWT cookie and a `port` query param (1024-65535). | Yes |
| POST | `/api/auth/cli/exchange` | Exchange a single-use CLI auth code for a JWT. Body: `{"code": "..."}`. Code expires after 60 seconds. | No |
| POST | `/api/auth/logout` | Clear the `access_token` session cookie. | No |
| POST | `/api/auth/sso/detect` | Detect whether an email belongs to an SSO-enabled org. Body: `{"email": "..."}`. Returns `{sso, org_id, org_name, protocol}`. | No |
| GET | `/api/auth/sso/saml/login/{org_id}` | Redirect to the SAML Identity Provider for the given org. | No |
| POST | `/api/auth/sso/saml/callback` | SAML Assertion Consumer Service (ACS) endpoint. Validates response, creates/finds user, sets JWT cookie. | No |
| GET | `/api/auth/sso/oidc/login/{org_id}` | Redirect to the OIDC Identity Provider for the given org. | No |
| GET | `/api/auth/sso/oidc/callback` | OIDC callback. Exchanges authorization code for tokens, creates/finds user, sets JWT cookie. Query params: `code`, `state`. | No |

---

### Users

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/api/users/me` | Get the current authenticated user's profile, including org context (`org_role`, `org_name`, `org_logo_url`) and `is_super_admin` flag. | Yes |
| PUT | `/api/users/me` | Update the current user's profile. Body fields: `name` (optional), `avatar_url` (optional). | Yes |

---

### Documents

All document endpoints use the `/api/documents` prefix.

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/documents` | Create a new document owned by the current user. Body: `{title, content}` (both optional with defaults). Returns 201. | Yes |
| GET | `/api/documents` | List documents owned by the current user, sorted by `updated_at` desc. Query param: `include_deleted` (bool, default false). | Yes |
| GET | `/api/documents/trash` | List soft-deleted documents owned by the current user, sorted by `deleted_at` desc. | Yes |
| GET | `/api/documents/shared` | List documents shared with the current user, sorted by recency. Includes `permission` and `last_accessed_at`. | Yes |
| GET | `/api/documents/recent` | List all documents recently viewed by the current user (including owned), sorted by most recently viewed. | Yes |
| POST | `/api/documents/{doc_id}/images` | Upload an image for a document. Requires EDIT permission. Rate limited: 30/minute. Multipart form with `file` field. | Yes |
| POST | `/api/documents/{doc_id}/attachments` | Upload a file attachment for a document. Requires EDIT permission. Max 5 MB. Supports images, documents, spreadsheets, presentations, archives, text. Rate limited: 20/minute. | Yes |
| GET | `/api/documents/{doc_id}` | Get a single document by ID. Requires access (owner or collaborator). | Yes |
| PUT | `/api/documents/{doc_id}` | Update a document's title and/or content. Requires EDIT permission. Body: `{title, content}` (both optional). | Yes |
| DELETE | `/api/documents/{doc_id}` | Soft-delete a document. Owner only. | Yes |
| POST | `/api/documents/{doc_id}/restore` | Restore a soft-deleted document. Owner only. | Yes |
| DELETE | `/api/documents/{doc_id}/permanent` | Permanently delete a document and all related data (CRDT updates, comments, versions, collaborators, view records). Owner only. Returns 204. | Yes |
| GET | `/api/documents/{doc_id}/acl` | Get consolidated ACL for a document showing all users with effective permissions. Includes inherited permissions. | Yes |
| PUT | `/api/documents/{doc_id}/access` | Update the document's general access setting (e.g., restricted, org-wide). Owner only. Body: `{general_access}`. | Yes |
| GET | `/api/documents/{doc_id}/permission` | Get the current user's permission level on a document. Returns `{"permission": "edit"|"view"}` or 403. | Yes |
| POST | `/api/documents/{doc_id}/view` | Record that the current user viewed a document. Requires VIEW access. Returns 204. | Yes |

---

### Folders

All folder endpoints use the `/api/folders` prefix.

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/folders` | Create a new folder. Optionally nest under a parent. Body: `{name, parent_id}`. Returns 201. | Yes |
| GET | `/api/folders/trash` | List all soft-deleted folders owned by the current user. | Yes |
| GET | `/api/folders/trash/{folder_id}/contents` | List deleted subfolders and documents inside a trashed folder. Returns `{folders, documents, parent_name, parent_id, ancestors}`. | Yes |
| GET | `/api/folders/shared` | List all folders shared with the current user, with owner info, permission, and `last_accessed_at`. | Yes |
| GET | `/api/folders/contents` | List folders and documents at a given level. Query param: `folder_id` (null for root). When accessing a shared folder, includes a `permission` field. | Yes |
| GET | `/api/folders/breadcrumbs` | Return the breadcrumb trail from root to the given folder. Query param: `folder_id` (required). | Yes |
| GET | `/api/folders/recent` | List all folders recently viewed by the current user, sorted by recency. | Yes |
| POST | `/api/folders/{folder_id}/view` | Record that the current user viewed/opened a folder. Returns 204. | Yes |
| GET | `/api/folders/{folder_id}/tree` | Recursively list all nested folders and documents under a folder. Used by the CLI sync engine for single-request discovery. | Yes |
| GET | `/api/folders/{folder_id}` | Get a folder by ID. Returns 404 if not found or not accessible. | Yes |
| PUT | `/api/folders/{folder_id}` | Update a folder's name or move it to a different parent. Body: `{name, parent_id}`. | Yes |
| DELETE | `/api/folders/{folder_id}` | Cascade soft-delete a folder and all its contents. Owner only. | Yes |
| POST | `/api/folders/{folder_id}/restore` | Cascade restore a soft-deleted folder and all its contents. Owner only. | Yes |
| DELETE | `/api/folders/{folder_id}/permanent` | Permanently delete a folder and all nested content. Owner only. Returns 204. | Yes |
| GET | `/api/folders/{folder_id}/acl` | Get consolidated ACL for a folder showing all users with effective permissions. | Yes |

---

### Sharing -- Document Collaborators

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/documents/{doc_id}/collaborators` | Add a collaborator by email with specified permission. Owner only. Body: `{email, permission}`. Returns 201. | Yes |
| GET | `/api/documents/{doc_id}/collaborators` | List all collaborators for a document. Owner only. | Yes |
| DELETE | `/api/documents/{doc_id}/collaborators/{user_id}` | Remove a collaborator's access. Owner only. Returns 204. | Yes |

### Sharing -- Document Group Collaborators

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/documents/{doc_id}/group-collaborators` | Add a group as a collaborator on a document. Owner only. Body: `{group_id, permission}`. Returns 201. | Yes |
| GET | `/api/documents/{doc_id}/group-collaborators` | List groups that have access to a document. Requires VIEW access. | Yes |
| DELETE | `/api/documents/{doc_id}/group-collaborators/{group_id}` | Remove a group's access to a document. Owner only. Returns 204. | Yes |

### Sharing -- Folder Collaborators

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/folders/{folder_id}/collaborators` | Add a collaborator to a folder with the specified permission level. Body: `{email, permission}`. Returns 201. | Yes |
| GET | `/api/folders/{folder_id}/collaborators` | List all collaborators for a given folder. | Yes |
| DELETE | `/api/folders/{folder_id}/collaborators/{user_id}` | Remove a collaborator's access from a folder. Returns 204. | Yes |

### Sharing -- Folder Group Collaborators

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/folders/{folder_id}/group-collaborators` | Add a group as a collaborator on a folder. Owner only. Body: `{group_id, permission}`. Returns 201. | Yes |
| GET | `/api/folders/{folder_id}/group-collaborators` | List groups that have access to a folder. Requires VIEW access. | Yes |
| DELETE | `/api/folders/{folder_id}/group-collaborators/{group_id}` | Remove a group's access to a folder. Owner only. Returns 204. | Yes |

---

### Versions

Version endpoints are nested under documents.

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/documents/{doc_id}/versions` | Create a version snapshot. Requires EDIT access. Body: `{content, summary}`. Returns 201 (new version) or 204 (content identical to latest, deduplicated). `content` max 10 MB, `summary` max 500 chars. | Yes |
| GET | `/api/documents/{doc_id}/versions` | List all versions for a document, newest first. Requires VIEW access. | Yes |
| GET | `/api/documents/{doc_id}/versions/{version_number}` | Get a specific version with full content. Requires VIEW access. | Yes |

---

### Comments

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/documents/{doc_id}/comments` | Create a comment on a document. Requires VIEW access. Body: `{content, anchor_from, anchor_to}`. Returns 201. | Yes |
| GET | `/api/documents/{doc_id}/comments` | List all comments for a document. Requires VIEW access. | Yes |
| POST | `/api/comments/{comment_id}/reply` | Reply to an existing comment. Requires VIEW access on the parent document. Body: `{content}`. Returns 201. | Yes |
| POST | `/api/comments/{comment_id}/resolve` | Mark a comment as resolved. Requires VIEW access on the parent document. | Yes |
| PATCH | `/api/comments/{comment_id}/reanchor` | Update a comment's anchor positions. Requires VIEW access on the parent document. Body: `{anchor_from, anchor_to}`. | Yes |
| PATCH | `/api/comments/{comment_id}/orphan` | Mark a comment as orphaned (anchor lost). Requires VIEW access on the parent document. | Yes |
| DELETE | `/api/comments/{comment_id}` | Delete a comment. Author only. Requires VIEW access on the parent document. Returns 204. | Yes |

---

### API Keys

All API key endpoints use the `/api/keys` prefix.

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/keys` | Create a new API key. The raw key is returned **only in this response** -- store it securely. Body: `{name}`. Returns 201 with `{id, name, raw_key, created_at}`. Rate limited: 10/minute. | Yes |
| GET | `/api/keys` | List all active API keys for the current user. Returns `[{id, name, created_at}]` (raw key and hash excluded). | Yes |
| DELETE | `/api/keys/{key_id}` | Revoke an API key (sets `is_active` to false). Owner only. Returns 204. Rate limited: 10/minute. | Yes |

---

### Organizations

All organization endpoints use the `/api/orgs` prefix. Access levels vary per endpoint.

#### Current User's Org

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/api/orgs/my` | Get the current user's organization, or null if personal user. | Yes |

#### Organization CRUD (Super Admin)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/orgs` | Create a new organization. The requesting super admin becomes the first admin member. Returns 201. | Yes (super admin) |
| GET | `/api/orgs` | List all organizations. | Yes (super admin) |

#### Organization Details (Org Admin)

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/api/orgs/{org_id}` | Get organization details. | Yes (org admin) |
| PUT | `/api/orgs/{org_id}` | Update organization details (name, settings). | Yes (org admin) |

#### Member Management (Org Admin)

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/api/orgs/{org_id}/members` | List all members of an organization. | Yes (org admin) |
| POST | `/api/orgs/{org_id}/members` | Add a member by `user_id`. Body: `{user_id, role}`. Returns 201. | Yes (org admin) |
| POST | `/api/orgs/{org_id}/members/invite` | Invite a user by email. User must already have a CollabMark account. Body: `{email, role}`. Returns 201. | Yes (org admin) |
| PATCH | `/api/orgs/{org_id}/members/{member_user_id}/role` | Change a member's role. Body: `{role}`. | Yes (org admin) |
| DELETE | `/api/orgs/{org_id}/members/{member_user_id}` | Remove a member from the organization. Returns 204. | Yes (org admin) |

#### Groups

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/api/orgs/{org_id}/groups` | Search groups by name within an organization. Query param: `q` (search string). Any org member can search. | Yes (org member) |

#### SSO Configuration (Org Admin)

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/api/orgs/{org_id}/sso` | Get the SSO configuration for an organization. Secrets are redacted. | Yes (org admin) |
| PUT | `/api/orgs/{org_id}/sso` | Create or update SSO configuration (protocol, IdP URLs, certificates, etc.). | Yes (org admin) |

#### SCIM Token Management (Org Admin)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/orgs/{org_id}/scim/token` | Generate a new SCIM bearer token. Plaintext returned once. Invalidates any previous token. Returns 201 with `{token, scim_enabled}`. Rate limited: 5/minute. | Yes (org admin) |
| DELETE | `/api/orgs/{org_id}/scim/token` | Revoke the SCIM bearer token and disable SCIM provisioning. Returns 204. | Yes (org admin) |

#### Logo Management (Org Admin)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/orgs/{org_id}/logo` | Upload or replace the organization logo. Max 2 MB. Accepts PNG/JPG/SVG/WebP. Rate limited: 10/minute. | Yes (org admin) |
| DELETE | `/api/orgs/{org_id}/logo` | Remove the organization logo. Returns 204. | Yes (org admin) |

---

### Notifications

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/api/notifications` | List the current user's notifications, newest first. Query params: `limit` (default 50, max 200), `offset` (default 0). | Yes |
| PATCH | `/api/notifications/{notification_id}/read` | Mark a single notification as read. Returns 204. | Yes |
| GET | `/api/notifications/preferences` | Get the current user's notification preferences. | Yes |
| PUT | `/api/notifications/preferences` | Update the current user's notification preferences. Body: `{preferences: {...}}`. | Yes |

---

### SCIM 2.0

SCIM endpoints use the `/scim/v2` prefix and follow RFC 7644. CRUD endpoints authenticate via a per-organization bearer token (generated at `POST /api/orgs/{org_id}/scim/token`). Discovery endpoints are public per the SCIM spec.

All SCIM responses use `Content-Type: application/scim+json`.

#### Discovery (No Auth)

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/scim/v2/ServiceProviderConfig` | SCIM ServiceProviderConfig (supported features, auth schemes). | No |
| GET | `/scim/v2/ResourceTypes` | List supported resource types (User, Group). | No |
| GET | `/scim/v2/ResourceTypes/{resource_type}` | Get a single resource type by name (`User` or `Group`). | No |
| GET | `/scim/v2/Schemas` | List all supported schemas. | No |
| GET | `/scim/v2/Schemas/{schema_id}` | Get a single schema by URN. | No |

#### User Provisioning (SCIM Bearer Token)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/scim/v2/Users` | Provision a new user in the organization. Returns 201 with Location header. Rate limited: 60/minute. | SCIM token |
| GET | `/scim/v2/Users` | List or filter users. Supports SCIM query params: `filter`, `startIndex`, `count`, `attributes`, `excludedAttributes`. Rate limited: 120/minute. | SCIM token |
| GET | `/scim/v2/Users/{user_id}` | Retrieve a single user by ID. Supports `attributes` and `excludedAttributes` params. Rate limited: 120/minute. | SCIM token |
| PUT | `/scim/v2/Users/{user_id}` | Full replacement of a user resource (RFC 7644 Section 3.5.1). Rate limited: 60/minute. | SCIM token |
| PATCH | `/scim/v2/Users/{user_id}` | Partial update via SCIM PATCH operations. Rate limited: 60/minute. | SCIM token |
| DELETE | `/scim/v2/Users/{user_id}` | Deactivate a user (remove org membership). Returns 204. Rate limited: 30/minute. | SCIM token |

#### Group Provisioning (SCIM Bearer Token)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/scim/v2/Groups` | Provision a new group. Returns 201 with Location header. Rate limited: 60/minute. | SCIM token |
| GET | `/scim/v2/Groups` | List or filter groups. Supports `filter`, `startIndex`, `count`. Rate limited: 120/minute. | SCIM token |
| GET | `/scim/v2/Groups/{group_id}` | Retrieve a single group by ID. Rate limited: 120/minute. | SCIM token |
| PUT | `/scim/v2/Groups/{group_id}` | Full replacement of a group resource. Rate limited: 60/minute. | SCIM token |
| PATCH | `/scim/v2/Groups/{group_id}` | Partial update via SCIM PATCH operations. Rate limited: 60/minute. | SCIM token |
| DELETE | `/scim/v2/Groups/{group_id}` | Delete a group and all its memberships. Returns 204. Rate limited: 30/minute. | SCIM token |

---

### WebSocket

| Protocol | Path | Description | Auth |
|---|---|---|---|
| WebSocket | `/ws/doc/{document_id}` | Real-time collaborative editing via CRDT sync (pycrdt-websocket). Authenticates via `access_token` cookie or `api_key` query param. Both VIEW and EDIT users can connect; write permissions are enforced by the editor UI (read-only mode for VIEW users). Closes with 1008 (Policy Violation) on auth failure. | Yes |

---

### Media

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/media/{file_path}` | Proxy media files from blob storage (S3 or local filesystem). Requires a valid JWT cookie. Non-image files are served as attachments to prevent browser execution. | Yes |

---

## Error Responses

All API errors return JSON in the standard format:

```json
{"detail": "error message"}
```

SCIM endpoints return errors in SCIM format per RFC 7644:

```json
{
  "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
  "detail": "error message",
  "status": "404"
}
```

### Common Status Codes

| Code | Meaning |
|---|---|
| 200 | Success |
| 201 | Created |
| 204 | No Content (success with no body) |
| 302 | Redirect (OAuth/SSO flows) |
| 401 | Unauthorized -- missing or invalid authentication |
| 403 | Forbidden -- authenticated but insufficient permissions |
| 404 | Not Found -- resource does not exist or is not accessible |
| 409 | Conflict -- SCIM uniqueness violation |
| 422 | Unprocessable Entity -- request body validation failed |
| 429 | Too Many Requests -- rate limit exceeded |
| 500 | Internal Server Error |
