"""Sandbox orchestration: compose base + generated app override (spec §2, §3)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from orchestrator.core import RunContext

# The integration sandbox's own network — the one controlled exception to the
# --network none isolation model. Docker compose defines it by name in
# sandbox/docker-compose.yml; this is the gate-side name for checks and for
# container skills that must reach the sandbox services.
SANDBOX_NETWORK = "qg_sandbox"


def generate_app_override(
    project_root: Path, port: int = 8000, sandbox_env: dict | None = None
) -> dict:
    """Compose override mounting the analyzed app as the sandbox service.

    `sandbox_env` (from settings.json project.sandbox.env) becomes the
    container's `environment`; absent or empty, no key is emitted.
    """
    service = {
        "build": {"context": str(project_root.resolve())},
        "ports": [f"{port}:{port}"],
        "depends_on": {
            "postgres": {"condition": "service_healthy"},
            "redis": {"condition": "service_healthy"},
        },
    }
    if sandbox_env:
        service["environment"] = sandbox_env
    return {"services": {"app": service}}


def write_override(ctx: RunContext) -> Path:
    """Write the app override YAML to artifacts; returns its path.

    Sandbox env vars come from settings.json (project.sandbox.env), so each
    analyzed project controls its own service configuration.
    """
    from orchestrator.discovery import load_project_settings

    settings = load_project_settings(ctx.qg_root) or {}
    sandbox_cfg = settings.get("sandbox") or {}
    override = generate_app_override(
        ctx.project_root, sandbox_env=sandbox_cfg.get("env") or None
    )
    path = ctx.artifacts_dir / "sandbox" / "app-override.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(override))
    return path


def compose_cmd(ctx: RunContext, args: list[str]) -> list[str]:
    """Build a docker compose command on base + generated override.

    `--env-file` must precede the subcommand; secrets (never committed) reach
    services through `.env.qg` only.
    """
    base = ctx.qg_root / "sandbox" / "docker-compose.yml"
    override = write_override(ctx)
    # --env-file must come before the compose subcommand; secrets (never
    # committed) reach services via this file only.
    return [
        "docker",
        "compose",
        "-f",
        str(base),
        "-f",
        str(override),
        "--env-file",
        str(ctx.qg_root / ".env.qg"),
        *args,
    ]


def compose_up(ctx: RunContext) -> subprocess.CompletedProcess:
    """Bring the integration sandbox up (build + wait for health)."""
    return subprocess.run(
        compose_cmd(ctx, ["up", "-d", "--wait", "--build"]),
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )


def compose_down(ctx: RunContext) -> subprocess.CompletedProcess:
    """Tear the integration sandbox down."""
    return subprocess.run(
        compose_cmd(ctx, ["down"]),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
