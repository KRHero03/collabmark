# CI/CD Pipeline

CollabMark uses GitHub Actions for continuous integration and deployment. There are two workflows: the main CI pipeline for every push/PR, and a separate CLI release pipeline for PyPI publishing.

## Main CI Pipeline

**File:** `.github/workflows/ci.yml`
**Triggers:** Push to `main`, pull requests targeting `main`

### Jobs

| Job | Runs On | Purpose |
|-----|---------|---------|
| `lint` | ubuntu-latest | Backend ruff lint + format check, frontend tsc + eslint + prettier |
| `lint-cli` | ubuntu-latest | CLI ruff lint + format check |
| `test-backend` | ubuntu-latest | Backend pytest (requires `DEBUG=true` env) |
| `test-frontend` | ubuntu-latest | Frontend vitest (`yarn test`) |
| `test-cli` | ubuntu-latest | CLI pytest |
| `build` | ubuntu-latest | Frontend production build (`yarn build`) |
| `deploy` | ubuntu-latest | Railway deployment (main branch pushes only) |
| `rollback` | ubuntu-latest | Auto-reverts failed commits on main |

### Job Dependencies

```
lint ──────────┐
lint-cli ──────┤
test-backend ──┼──> build ──> deploy
test-frontend ─┤       │
test-cli ──────┘       └──> rollback (on failure)
```

All lint and test jobs run in parallel. The `build` job waits for all of them to pass. `deploy` runs only on pushes to `main` after build succeeds. `rollback` triggers automatically if any test or build job fails on a main push.

### Backend Tests

```yaml
- name: Install system dependencies
  run: sudo apt-get install -y pkg-config libxml2-dev libxmlsec1-dev libxmlsec1-openssl
- name: Run backend tests
  run: python -m pytest
  env:
    DEBUG: "true"
```

The `DEBUG=true` env var is required to use mongomock instead of a real MongoDB instance.

### Deploy to Railway

```yaml
- name: Deploy to Railway
  run: railway up --service ${{ secrets.RAILWAY_SERVICE_ID }} --detach
  env:
    RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
```

Requires `RAILWAY_TOKEN` and `RAILWAY_SERVICE_ID` secrets configured in the repository.

### Auto-Rollback

If tests or build fail on a push to `main`, the rollback job automatically reverts the commit:

```yaml
- name: Revert failed commit
  run: |
    git revert --no-edit HEAD
    git push origin main
```

## CLI Release Pipeline

**File:** `.github/workflows/cli-release.yml`
**Triggers:** Tags matching `cli-v*` (e.g., `cli-v0.2.0`)

### Jobs

| Job | Purpose |
|-----|---------|
| `lint-and-test` | Ruff lint + format check + pytest |
| `publish` | Build with hatch + publish to PyPI |

### Publishing

Uses PyPI trusted publishing (OIDC) for secure, tokenless publishing:

```yaml
permissions:
  contents: read
  id-token: write

- name: Build package
  run: hatch build
  working-directory: cli

- name: Publish to PyPI
  uses: pypa/gh-action-pypi-publish@release/v1
  with:
    packages-dir: cli/dist/
```

### Release Workflow

To publish a new CLI version:

1. Update the version in `cli/src/collabmark/__init__.py` and `cli/pyproject.toml`
2. Commit and push to `main`
3. Create and push a tag:
   ```bash
   git tag cli-v0.3.0
   git push origin cli-v0.3.0
   ```
4. The `cli-release.yml` workflow runs lint, tests, builds, and publishes to PyPI
5. Verify at: `pip install collabmark==0.3.0`

## Makefile Targets

The root `Makefile` provides unified build commands for local development:

| Target | Description |
|--------|-------------|
| `make install` | Install all dependencies (backend venv + frontend yarn + CLI) |
| `make quickstart` | One-command dev setup: env, deps, infra, instructions |
| `make lint` | Run all linters (backend ruff + frontend eslint/prettier + CLI ruff) |
| `make lint-fix` | Auto-fix lint issues |
| `make format` | Format all code (ruff + prettier) |
| `make format-check` | Check formatting without changes |
| `make test` | Run all tests (backend + frontend + CLI) |
| `make test-be` | Backend tests only |
| `make test-fe` | Frontend tests only |
| `make test-cli` | CLI tests only |
| `make test-cov` | Tests with coverage reports |
| `make build` | Frontend production build |
| `make ci` | Full CI pipeline locally: lint + format-check + test + build |
| `make verify` | Local E2E verification: infra + tests + build |
| `make clean` | Remove build artifacts |

### Running Full CI Locally

```bash
make ci
```

This runs the equivalent of what GitHub Actions does: lint all code, check formatting, run all test suites, and build the frontend. Run this before pushing to catch issues early.
