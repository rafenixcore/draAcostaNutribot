"""Tool execution: venv tools (soft isolation) and containers (hard isolation)."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecResult:
    returncode: int
    stdout: str
    stderr: str


# Default venv lives next to the package (quality-gate/.venv), so it resolves
# no matter where the gate is invoked from. QG_VENV overrides it.
_DEFAULT_VENV = str(Path(__file__).resolve().parents[1] / ".venv")


def venv_exec(
    cmd: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
    extra_env: dict[str, str] | None = None,
) -> ExecResult:
    """Run `cmd` with the QG venv's bin dir prepended to PATH."""
    venv = Path(os.environ.get("QG_VENV", _DEFAULT_VENV)).resolve()
    full_env = dict(env or os.environ)
    full_env["PATH"] = f"{venv / 'bin'}:{full_env.get('PATH', '')}"
    if extra_env:
        full_env.update(extra_env)
    proc = subprocess.run(
        [str(venv / "bin" / cmd[0]), *cmd[1:]],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=full_env,
        timeout=900,
        check=False,
    )
    return ExecResult(proc.returncode, proc.stdout, proc.stderr)


def container_exec(
    image_ref: str,
    cmd: list[str],
    cwd: Path,
    mounts: list[str] | None = None,
    env: dict[str, str] | None = None,
    network: str = "none",
) -> ExecResult:
    """Run a tool in a container with pinned digest; project mounted read-only."""
    # docker run [OPTIONS] IMAGE [CMD...] — options must precede the image,
    # otherwise docker treats them as the container command.
    full_cmd = ["docker", "run", "--rm", "--network", network]
    for m in mounts or []:
        full_cmd += ["--mount", m]
    for k, v in (env or {}).items():
        full_cmd += ["--env", f"{k}={v}"]
    full_cmd += [image_ref, *cmd]
    proc = subprocess.run(
        full_cmd, cwd=cwd, capture_output=True, text=True, timeout=1800, check=False
    )
    return ExecResult(proc.returncode, proc.stdout, proc.stderr)
