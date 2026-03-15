---
name: pre-commit-checklist
description: Enforces a mandatory pre-commit quality gate before any code is committed. Covers security auditing (XSS, input validation, ACLs, CORS), unit test coverage (>90%), build verification, test execution, and lint/format checks. Use before every commit, when the user says "commit", "ready to commit", or after completing a feature or bug fix.
---

# Pre-Commit Quality Gate

Before committing ANY change, run through every section below in order. Do NOT skip sections. If any gate fails, fix the issue before proceeding.

## 1. Lint & Format

Run formatting first, then lint. Fix all issues before moving on.

```bash
make format       # auto-format backend (ruff) + frontend (prettier)
make lint         # ruff check + eslint + prettier check
```

- Zero lint errors and zero format diffs required.
- If `make lint` fails, run `make lint-fix` then re-check.

## 2. Security Audit

Manually review every changed file for the following. This is NOT optional.

### Backend (Python / FastAPI)
- **Input validation**: All user-supplied data goes through Pydantic schemas with constrained types (`constr`, `conint`, `EmailStr`). No raw `dict` payloads accepted by routes.
- **Authentication**: Every non-public route uses `Depends(get_current_user)` or an equivalent auth dependency (`get_scim_org`, `get_org_admin_user`, `get_super_admin_user`).
- **Authorization / ACLs**: Verify the route checks ownership or permission level before mutating data. Cross-org boundary checks must be present where applicable.
- **Injection**: No f-string interpolation into database queries. Use Beanie query builders or Motor operators.
- **Mass assignment**: Route handlers must use typed Pydantic schemas (not raw dicts) to prevent setting server-controlled fields (`owner_id`, `org_id`, `is_deleted`, `created_at`).
- **Secrets**: No tokens, keys, or credentials hardcoded. `.env` values accessed via `settings`.

### Frontend (React / TypeScript)
- **XSS**: User-generated content rendered via React JSX (auto-escaped). If `dangerouslySetInnerHTML` is used, content MUST be sanitized with DOMPurify.
- **CORS**: API calls go through the axios client in `lib/api.ts` which uses relative paths (`/api/...`). No direct cross-origin requests.
- **Auth tokens**: JWT stored in httpOnly cookies only. No tokens in localStorage or sessionStorage (API keys in sessionStorage on ApiDocsPage are acceptable — they are user-entered, not session tokens).
- **URL params**: Route params and query strings validated/sanitized before use in API calls.

### Checklist
```
- [ ] All new routes have auth dependencies
- [ ] All new routes use typed Pydantic request schemas
- [ ] No raw user input reaches DB queries unsanitized
- [ ] No dangerouslySetInnerHTML without DOMPurify
- [ ] No secrets committed (check .env, credentials, tokens)
- [ ] Cross-org boundary enforced on new shared resources
```

## 3. Write & Run Unit Tests

### Coverage target: >90% on changed code

For every new or modified function/endpoint, write tests covering:
- Happy path with specific value assertions (`assert data["title"] == "My Doc"`)
- Error cases (400, 401, 403, 404, 409)
- Edge cases (empty input, boundary values, concurrent ops)
- Auth failures (missing token, wrong role, cross-org)

### Backend tests
```bash
cd backend && .venv/bin/python -m pytest --cov=app --cov-report=term-missing -x
```
- Check `term-missing` output — every new function must be covered.
- Test files: `tests/test_<module>.py`
- Stack: pytest + pytest-asyncio + httpx ASGI transport + mongomock-motor
- Do NOT use generic assertions like `assert response.json()`.

### Frontend tests
```bash
cd frontend && yarn test:coverage
```
- Test files: `src/**/<Component>.test.tsx` or `src/**/<hook>.test.ts`
- Stack: Vitest + React Testing Library + jsdom
- Destructure from `render()` return — do NOT import `screen` from `@testing-library/react`.
- Use `getByRole`, `getByText`, `findByText` for selectors.

### After writing tests
```bash
make test         # run full suite — all must pass
make test-cov     # verify coverage numbers
```

## 4. Build Verification

```bash
make build        # frontend production build (vite build)
```

- Must complete with zero errors and zero warnings.
- If the Dockerfile is modified, also verify:
  ```bash
  docker compose -f docker-compose.prod.yml build
  ```

## 5. Dead Code & Unused Test Cleanup

Scan for and remove dead code before committing. This is NOT optional.

### What to look for
- **Unused imports**: `ruff check --select F401` (backend), TypeScript compiler warnings (frontend).
- **Unused functions/variables**: Functions defined but never called from production code. Private helpers (`_foo`) with zero callers. Exported hooks/components/interfaces never imported elsewhere.
- **Unused test cases**: Tests that exercise functions or endpoints that no longer exist.
- **Stale test-only code**: Functions/exports that exist solely for test imports but have no production purpose — move the logic into the test file or delete.
- **Commented-out code**: Remove it; version control is the history.

### Commands
```bash
cd backend && .venv/bin/ruff check app/ tests/ --select F401,F811,F841,RUF059   # unused imports/vars
```

### Checklist
```
- [ ] No unused imports (ruff F401 clean)
- [ ] No unused private functions (grep for def _foo, verify callers exist)
- [ ] No unused exported interfaces/hooks/components (frontend)
- [ ] No tests for removed functions/endpoints
- [ ] No commented-out code blocks
```

## 6. Final CI Gate

Run the full CI pipeline to catch anything missed:

```bash
make ci           # lint + format-check + test + build
```

All four stages must pass. Only then proceed to commit.

## Quick Reference

| Gate | Command | Pass criteria |
|------|---------|---------------|
| Format | `make format` | No remaining diffs |
| Lint | `make lint` | Exit code 0 |
| Security | Manual review | All checklist items checked |
| Tests | `make test-cov` | >90% coverage, 0 failures |
| Build | `make build` | Exit code 0, 0 warnings |
| Dead code | `ruff check --select F401,F811,F841,RUF059` + manual | No unused code |
| CI | `make ci` | All stages green |
