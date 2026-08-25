"""Security skills: SAST (semgrep), secrets (truffleHog), deps (pip-audit)."""

from __future__ import annotations

import json

from orchestrator.core import RunContext
from orchestrator.toolrunner import venv_exec
from skills.base import Skill


class SastSkill(Skill):
    name = "sast"
    tool = "semgrep"
    tool_layer = "venv"

    def _execute(self, ctx: RunContext) -> dict:
        res = venv_exec(
            ["semgrep", "scan", "--json", "--quiet", "."], cwd=ctx.project_root
        )
        self._cmd_log.append("semgrep scan --json --quiet .")
        self._exit_log.append(res.returncode)
        # semgrep exits 1 when it found findings (valid JSON on stdout); any
        # other non-zero exit without JSON payload is a crash → policy decides.
        if res.returncode not in (0, 1) and not (res.stdout or "").lstrip().startswith(
            "{"
        ):
            return {"_error": res.stderr or f"semgrep exited {res.returncode}"}
        try:
            return json.loads(res.stdout or "{}")
        except json.JSONDecodeError:
            return {"_error": res.stderr}

    def _extract_metrics(self, raw: dict) -> dict[str, float]:
        high = sum(
            1
            for r in raw.get("results", [])
            if r.get("extra", {}).get("severity") == "ERROR"
        )
        return {"semgrep.high_count": float(high)}


def _parse_trufflehog_lines(lines: list[str]) -> list[dict]:
    """Parse trufflehog JSON output into [{'detector', 'file', 'verified'}].

    The file path lives under Data.Filesystem.file for filesystem scans and
    under Data.file for other sources — both shapes are accepted. A line that
    is not JSON, malformed JSON, or schema-drifted (non-dict values where
    dicts are expected) is skipped: the helper never raises.
    """
    findings = []
    for line in lines:
        if not line.strip().startswith("{"):
            continue
        try:
            d = json.loads(line)
            data = (d.get("SourceMetadata") or {}).get("Data") or {}
            file_ = (data.get("Filesystem") or {}).get("file") or data.get("file")
            detector = d.get("DetectorName") or d.get("SecretType")
            findings.append(
                {
                    "detector": detector,
                    "file": file_,
                    "verified": bool(d.get("Verified")),
                }
            )
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue
    return findings


class SecretsSkill(Skill):
    name = "secrets"
    tool = "trufflehog"
    tool_layer = "container"

    def _execute(self, ctx: RunContext) -> dict:
        from orchestrator.images import IMAGES
        from orchestrator.toolrunner import container_exec

        image = IMAGES["trufflehog"]
        mount = f"type=bind,src={ctx.project_root.resolve()},dst=/src,readonly"
        # image ENTRYPOINT is already "trufflehog"; --no-verification makes
        # findings deterministic and offline-friendly (no API calls).
        res = container_exec(
            image,
            ["filesystem", "/src", "--json", "--no-verification", "--no-update"],
            cwd=ctx.project_root,
            mounts=[mount],
        )
        self._cmd_log.append("trufflehog filesystem /src --json --no-verification")
        self._exit_log.append(res.returncode)
        if res.returncode != 0:
            return {"_error": res.stderr or f"trufflehog exited {res.returncode}"}
        # Persist detector + file only — NEVER the Raw secret value. The audit
        # log records which secrets were accessed (names, not values).
        findings = _parse_trufflehog_lines(res.stdout.splitlines())
        for f in findings:
            # detector missing → nothing meaningful to audit; never log "None"
            if f["detector"]:
                self._secret_log.append(
                    f"{f['detector']}@{f['file']}" if f["file"] else f["detector"]
                )
        return {"scope": "working-tree-only", "findings": findings, "image": image}

    def _extract_metrics(self, raw: dict) -> dict[str, float]:
        return {"secrets.count": float(len(raw.get("findings", [])))}


class DepsSkill(Skill):
    name = "deps"
    tool = "pip-audit"
    tool_layer = "venv"

    def _execute(self, ctx: RunContext) -> dict:
        from orchestrator.adapters.base import get_adapter

        profile = ctx.profile or {}
        framework = profile.get("framework")
        deps = []
        if framework and framework != "unsupported":
            try:
                deps = get_adapter(framework)().get_dependencies(ctx.project_root)
            except Exception:  # noqa: BLE001 — deps are best-effort
                deps = []
        if not deps:
            return {"_skipped": True, "reason": "no dependencies declared"}
        reqs = ctx.artifacts_dir / self.name / "requirements.txt"
        reqs.parent.mkdir(parents=True, exist_ok=True)
        reqs.write_text("\n".join(deps) + "\n")
        res = venv_exec(
            ["pip-audit", "--format", "json", "-r", str(reqs)], cwd=ctx.project_root
        )
        self._cmd_log.append("pip-audit --format json -r requirements.txt")
        self._exit_log.append(res.returncode)
        # pip-audit exits 1 when vulnerabilities exist (valid JSON); any other
        # non-zero exit without JSON payload is a crash → policy decides.
        if res.returncode not in (0, 1) and not (res.stdout or "").lstrip().startswith(
            "{"
        ):
            return {"_error": res.stderr or f"pip-audit exited {res.returncode}"}
        try:
            return json.loads(res.stdout or "{}")
        except json.JSONDecodeError:
            return {"_error": res.stderr}

    def _extract_metrics(self, raw: dict) -> dict[str, float]:
        critical = sum(
            1 for v in raw.get("vulnerabilities", []) if v.get("severity") == "critical"
        )
        return {"pip_audit.critical_count": float(critical)}
