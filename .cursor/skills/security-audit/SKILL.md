---
name: security-audit
description: Comprehensive security audit checklist for the CollabMark backend. Covers OWASP Top 10, rate limiting, auth/ACL enforcement, injection prevention, file upload safety, and automated security test execution. Run as part of every pre-commit check and whenever adding or modifying backend code.
---

# Security Audit

Run this audit on every backend change. It combines an automated test gate with a manual review checklist aligned to OWASP Top 10 and CollabMark-specific patterns.

## 1. Automated Security Tests

Run the security test suite first. It covers regression tests for all known vulnerability fixes.

```bash
cd backend && .venv/bin/python -m pytest tests/test_security_fixes.py -v
```

- **All tests must pass.** If any fail, investigate and fix before proceeding.
- If you added a new security-relevant fix, add a corresponding test to `tests/test_security_fixes.py`.

## 2. Authentication & Authorization

Every endpoint must enforce auth. No exceptions unless explicitly public.

### Checklist
```
- [ ] Every new route uses `Depends(get_current_user)`, `Depends(get_org_admin_user)`, `Depends(get_super_admin_user)`, or `Depends(get_scim_org)`
- [ ] SCIM routes use bearer token auth via `get_scim_org`
- [ ] WebSocket routes authenticate via JWT cookie or API key query param
- [ ] Permission checks (VIEW/EDIT/DELETE) happen BEFORE any data mutation
- [ ] Cross-org boundary is enforced: use `org_allows_general_access()` before granting access via `general_access`
- [ ] Owner checks use `str(user.id)` comparison, not unchecked user input
```

## 3. Rate Limiting

All endpoints must have appropriate rate limits. API-key-authenticated requests from agents get higher limits.

### Tiers
| Tier | Limit | Applies to |
|------|-------|------------|
| Auth | 10/minute per IP | Login, callback, SSO, CLI exchange |
| Upload | 20/minute per IP | Image, attachment, logo uploads |
| SCIM | 120/minute per token | All SCIM provisioning endpoints |
| Mutation | 60/minute per IP | POST, PUT, PATCH, DELETE (default) |
| Read | 200/minute per IP | GET endpoints (global default) |

### Checklist
```
- [ ] New auth endpoints have `@_limiter.limit("10/minute")`
- [ ] New upload endpoints have `@_limiter.limit("20/minute")`
- [ ] New SCIM endpoints have `@_limiter.limit("120/minute")`
- [ ] Mutation endpoints are covered by the global write limit or an explicit decorator
- [ ] API key users are not blocked by overly tight IP-based limits (agents may make many requests)
```

## 4. Input Validation & Injection Prevention

### Checklist
```
- [ ] All user input goes through Pydantic schemas with constrained types — no raw `dict` from `request.json()`
- [ ] No f-string interpolation into MongoDB queries — use Beanie query builders
- [ ] `re.escape()` applied before any user input used in `$regex` queries
- [ ] SCIM filters parsed via regex, not interpolated into queries
- [ ] `avatar_url` validated to require `https://` scheme (see `_validate_avatar_url` in `models/user.py`)
- [ ] File extensions checked against allowlists, NOT denylists
- [ ] File content validated with `validate_file_content()` (magic-byte check) for all upload endpoints
- [ ] SVG files are NOT allowed (XSS vector)
```

## 5. HTML / Email Template Safety

User-supplied values rendered in HTML (emails, error pages) must be escaped.

### Checklist
```
- [ ] All user-supplied values in email templates use `_esc()` (which calls `html.escape()`)
- [ ] No raw f-string embedding of user names, document titles, or comments in HTML
- [ ] Email subjects may contain unescaped text (plaintext header) but the `<title>` tag in HTML uses `_esc()`
```

## 6. Secrets & Configuration

### Checklist
```
- [ ] No hardcoded tokens, keys, or passwords — all via `settings` from `.env`
- [ ] JWT secret is NOT the default value in production (startup fails with RuntimeError)
- [ ] Session secret key is separate from JWT secret key (auto-generated if not set)
- [ ] SCIM tokens and API keys stored as SHA-256 hashes, never plaintext
- [ ] Token comparisons use `hmac.compare_digest()` for timing safety
```

## 7. File Upload & Media Serving

### Checklist
```
- [ ] Upload extensions: allowlist only (no `.svg`, no `.html`, no `.js`)
- [ ] Upload size limits enforced (5MB images/attachments, 2MB logos)
- [ ] Magic-byte validation via `puremagic` for all uploads
- [ ] `/media/` endpoint requires JWT authentication
- [ ] Non-image files served with `Content-Disposition: attachment`
- [ ] Upload keys use UUID-based names, never user-supplied filenames
```

## 8. SSRF Prevention

### Checklist
```
- [ ] OIDC discovery URLs validated against private IP denylist (`_validate_url_not_internal`)
- [ ] No user-supplied URLs used for server-side HTTP requests without validation
- [ ] HTTPS enforced for external identity provider URLs
```

## 9. WebSocket Security

### Checklist
```
- [ ] WS connections authenticated (JWT cookie or API key)
- [ ] Per-document permission check before accepting connection
- [ ] Read-only enforcement for VIEW users (write messages dropped)
- [ ] Periodic permission re-check during session
- [ ] Message size limit enforced (`_MAX_WS_MESSAGE_SIZE = 5MB`)
```

## 10. Security Headers

Verified automatically by `test_security_fixes.py::TestSecurityHeaders`, but confirm:
```
- [ ] X-Content-Type-Options: nosniff
- [ ] X-Frame-Options: DENY
- [ ] Referrer-Policy: strict-origin-when-cross-origin
- [ ] Permissions-Policy: camera=(), microphone=(), geolocation=()
- [ ] Strict-Transport-Security in production
- [ ] Cache-Control: no-store on /api/* responses
```
