# Contributing

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/rafenixcore/draAcostaNutribot.git
   cd diet_telegram_agent
   ```

2. **Configure environment**
   ```bash
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env.local
   ```

3. **Start dependencies**
   ```bash
   docker compose up -d
   ```

4. **Backend**
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8001
   ```

5. **Frontend**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Code Style

- **Python:** Black (line length 100) + Ruff for linting
  ```bash
   cd backend
   black . --line-length=100
   ruff check .
   ```
- **TypeScript/React:** Prettier + ESLint
  ```bash
   cd frontend
   npx prettier --write src/
   npx eslint src/
   ```
- **Docstrings:** English only (Google style for Python, JSDoc for TypeScript)
- **Comments:** English only — explain *why*, not *what*

## Language Convention

- **Code identifiers** (variables, functions, classes, files): **English**
- **User-facing UI text** (labels, messages, emails, PDFs): **Spanish** (the app serves Spanish-speaking clinics)
- **Documentation** (README, CHANGELOG, docs): **English**

## Commit Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add weight tracking chart to dashboard
fix: correct BMR calculation for female patients
docs: update API endpoint documentation
refactor: extract nutrition calculation into standalone engine
perf: reduce memory usage by switching PDF renderer
chore: bump dependencies
test: add E2E flow for diet generation
security: add rate limiting to login endpoint
```

## Pull Request Process

1. Create a branch from `dev`: `git checkout -b feat/your-feature`
2. Write tests for new functionality (TDD preferred)
3. Ensure all tests pass: `cd backend && pytest tests/ -v`
4. Run linters: `ruff check . && black --check .`
5. Open a PR against `dev` with a clear description of changes
6. PRs require at least one review before merging

## Testing

- All new features must include tests
- Bug fixes should include a regression test
- Backend: `pytest` with async support
- Frontend: `vitest` for unit tests, Playwright for E2E

```bash
# Backend tests
cd backend && pytest tests/ -v --cov

# Frontend tests
cd frontend && npx vitest run
```

## Project Structure

Keep files focused on a single responsibility. Follow the existing patterns:
- API routes in `backend/app/api/`
- Business logic in `backend/app/services/`
- Domain rules in `backend/app/logic/`
- Deterministic engine in `backend/app/nutrition/`
- React pages in `frontend/src/pages/`
- Reusable components in `frontend/src/components/`

## Questions?

Open a [GitHub Discussion](https://github.com/rafenixcore/draAcostaNutribot/discussions) or contact the maintainer.
