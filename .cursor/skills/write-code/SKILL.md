---
name: write-code
description: Enforces standard coding practices when writing or modifying code. Covers DRY, YAGNI, single responsibility, file organization, naming conventions, readability, and extensibility. Use whenever writing new code, modifying existing code, reviewing code, or implementing a feature.
---

# Code Quality & Organization

Apply these standards to ALL code changes. Refactor violations before moving on.

## DRY — Don't Repeat Yourself
- Shared logic extracted into reusable functions/hooks. If the same block appears in 2+ places, extract it.
- Backend: common patterns go in service functions (`app/services/`), not duplicated across routes.
- Frontend: shared UI patterns go in `components/`, shared state logic in `hooks/`, shared API calls in `lib/api.ts`.

## YAGNI — You Aren't Gonna Need It
- No speculative abstractions. Only build what's needed now.
- No unused parameters, dead code paths, or commented-out code left behind.
- No premature generalization — prefer a concrete implementation that can be refactored later over an abstract framework used once.

## Single Responsibility
- Each function does ONE thing. If you can describe it with "and", split it.
- Backend route handlers are thin — delegate logic to service functions.
- Frontend components render UI; data fetching and mutation live in hooks/stores.

## File Organization

Place code in the right location. If you're unsure, match existing patterns.

| What | Where (Backend) | Where (Frontend) |
|------|-----------------|-------------------|
| Constants / enums | `app/constants.py` or module-level in the relevant file | Top of module or dedicated `constants.ts` |
| Business logic | `app/services/<domain>_service.py` | `hooks/use<Domain>.ts` (Zustand stores) |
| Route handlers | `app/routes/<domain>.py` (thin, delegate to services) | `pages/<Page>.tsx` |
| Data models | `app/models/<model>.py` (Beanie Documents) | TypeScript interfaces in `lib/api.ts` |
| Auth helpers | `app/auth/` | Handled by `useAuth` hook + axios interceptor |
| Reusable UI | — | `components/<Feature>/` |
| Utilities | `app/utils/` or inline in service | `lib/` (e.g. `dateUtils.ts`) |

## Naming
- Functions/variables: descriptive, intent-revealing. `get_user_permission()` not `check()`.
- Boolean variables: use `is_`, `has_`, `can_` prefixes. `is_deleted` not `deleted`.
- Backend: `snake_case` for everything. Frontend: `camelCase` vars, `PascalCase` components.
- Test functions: `test_<what>_<scenario>` e.g. `test_create_user_duplicate_email_returns_409`.

## Readability
- Functions under ~40 lines. If longer, extract helpers.
- Max 3 levels of nesting. Use early returns / guard clauses to flatten.
- Group related code with blank lines. Order: imports → constants → types → main logic → helpers.
- Comments explain *why*, never *what*. No narrating code (`# increment counter`).

## Extensibility (without over-engineering)
- Prefer composition over inheritance.
- Backend services accept parameters rather than hard-coding values — makes testing and future changes easier.
- Frontend hooks expose granular actions rather than one monolithic function.

## Checklist
```
- [ ] No duplicated logic (DRY)
- [ ] No speculative/unused code (YAGNI)
- [ ] Each function has a single responsibility
- [ ] Code is in the correct file/layer (see table above)
- [ ] Names are descriptive and follow project conventions
- [ ] No deep nesting (max 3 levels)
- [ ] No functions longer than ~40 lines
- [ ] Comments explain intent, not mechanics
```
