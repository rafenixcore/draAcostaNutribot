"""Sandbox orchestration: compose base + generated app override (spec §2, §3)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from orchestrator.core import RunContext


def generate_app_override(
    project_root: Path, port: int = 8000, sandbox_env: dict | None = None
) -> dict:
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
    return subprocess.run(
        compose_cmd(ctx, ["up", "-d", "--wait", "--build"]),
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )


def compose_down(ctx: RunContext) -> subprocess.CompletedProcess:
    return subprocess.run(
        compose_cmd(ctx, ["down"]),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
