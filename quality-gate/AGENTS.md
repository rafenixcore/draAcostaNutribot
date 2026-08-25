# Agent contract — Portable AI Quality Gate

You (the agent) orchestrate, interpret and explain. You NEVER decide PASS/FAIL.

- Run quality checks ONLY via the whitelisted commands: `qg init`, `qg discover`,
  `qg setup`, `qg run [--trigger <name>]`, `qg run-skill <skill>`, `qg get-profile`,
  `qg get-results`, `qg get-report`, `qg status`, `qg cleanup --yes`.
- NEVER execute the underlying tools (ruff, pytest, semgrep, truffleHog, pip-audit,
  trivy, k6, docker) directly. The orchestrator does that.
- Read the verdict from `qg get-report` / `qg status` and present it. Never override it.
- Never edit `config/rules.yml` without asking the user.
- The sandbox mounts the project read-only; only `artifacts/` and `reports/` are writable.
