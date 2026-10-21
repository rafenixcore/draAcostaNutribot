# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- `/auth/refresh` raised `NameError` (HTTP 500) because `sha256`, `decode_access_token`, `datetime` and `timezone` were used without being imported
- CI: `tests/test_config_railway_db_url.py` imported `ensure_railway_tcp_proxy_ssl`, a function that never existed, which aborted pytest collection for the whole suite. The module now tests the URL normalisation that actually exists. (The proposed `sslmode` suffix was deliberately not implemented: SQLAlchemy's asyncpg dialect does not know that parameter and would forward it to `asyncpg.connect()`.)
- CI: `ruff`, `eslint` and `tsc` failures across backend and frontend (unused variables, unsorted imports, exception chaining, `capture_output`)

### Changed
- Translated all documentation to English (README, ARCHITECTURE.md)
- Added CONTRIBUTING.md, CHANGELOG.md, SECURITY.md
- Renamed project branding from Nutribot to Nutrisoft
- `backend/pyproject.toml` is now versioned so CI lints with the same rules as local runs

### Fixed
- Standardized API response keys from Spanish to English (audit log)
- Renamed `NoAplicaField` component to `OptionalField`
- Fixed inconsistent UI text language across pages
- Translated intake link error messages to Spanish (patient-facing)

## [1.1.0] - 2026-06-22

### Added
- PWA auto-update with service worker cache busting and reload prompt
- Circuit breaker middleware for external API resilience (50 errors/60s → 30s cooldown)
- JSON structured logging for production observability
- CORS production warning when origins set to wildcard

### Changed
- PDF generation: switched from Chromium to WeasyPrint (~60% memory reduction)
- Memory-optimized Docker images with smaller dependency footprint

### Fixed
- PWA update detection now uses cache-control headers to prevent stale content
- Fixed various security vulnerabilities via npm audit (Vite HIGH, react-router/js-yaml/postcss MODERATE)

## [1.0.0] - 2026-06-18

### Added
- Initial production release
- Patient intake forms with tokenized links (registration & updates)
- Body metrics with time series tracking
- 10-step diet generation wizard with strategy modes (Auto, Guided, Manual)
- Deterministic nutrition engine (Mifflin-St Jeor BMR, TDEE, macros)
- AI-assisted meal drafting via DeepSeek (OpenAI-compatible)
- Engine + LLM merge with clinical safety overrides
- Clinical rules for diabetes, hypertension, kidney disease, dyslipidemia
- Professional PDF export with WeasyPrint + ReportLab fallback
- Email delivery via Gmail API with professional template
- Dietary reminders via APScheduler background jobs
- JWT authentication with bcrypt + 3 RBAC roles (super_admin, admin, doctor)
- Force password change on first login
- Rate limiting on login (5/min) and forgot-password (2/10min)
- Soft delete with recycle bin for patients and diets
- Audit log for all clinical actions
- Profile completeness check before diet generation
- Single-tenant architecture with controlled account creation
- Admin user management (create, reset, deactivate doctors)
- Responsive PDF preview in browser
- Telegram bot integration for doctor's assistant
- Anti-duplication protections for Telegram callbacks
- Full versioning with input/output snapshots per diet
- Architecture Decision Records (ADR-001, ADR-002, ADR-003)
