"""Container/performance skills: trivy, k6."""

from __future__ import annotations

import json

from orchestrator.core import RunContext
from orchestrator.toolrunner import container_exec
from skills.base import Skill


def _sandbox_network_up() -> bool:
    import subprocess

    return (
        subprocess.run(
            ["docker", "network", "inspect", "qg_sandbox"],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


class TrivySkill(Skill):
    name = "trivy"
    tool = "trivy"
    tool_layer = "container"

    def _execute(self, ctx: RunContext) -> dict:
        if not (ctx.profile or {}).get("docker"):
            return {"_skipped": True, "reason": "no Dockerfile present"}
        from orchestrator.images import IMAGES

        image = IMAGES["trivy"]
        mount = f"type=bind,src={ctx.project_root.resolve()},dst=/src,readonly"
        # image ENTRYPOINT is already "trivy"
        res = container_exec(
            image,
            ["fs", "--scanners", "vuln", "--format", "json", "/src"],
            cwd=ctx.project_root,
            mounts=[mount],
        )
        self._cmd_log.append("trivy fs --scanners vuln --format json /src")
        self._exit_log.append(res.returncode)
        stdout = res.stdout or ""
        # Non-zero exit with no JSON payload = the scan itself failed (e.g.
        # vulnerability DB download). Never fall through to a metrics verdict.
        if res.returncode != 0 and not stdout.lstrip().startswith("{"):
            return {"_error": res.stderr or f"trivy exited {res.returncode}"}
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return {"_error": res.stderr}

    def _extract_metrics(self, raw: dict) -> dict[str, float]:
        critical = 0
        for result in raw.get("Results", []):
            critical += sum(
                1
                for v in result.get("Vulnerabilities", [])
                if v.get("Severity") == "CRITICAL"
            )
        return {"trivy.critical_count": float(critical)}


class K6Skill(Skill):
    name = "performance"
    tool = "k6"
    tool_layer = "container"

    def _execute(self, ctx: RunContext) -> dict:
        if not (ctx.profile or {}).get("docker"):
            return {"_skipped": True, "reason": "no Dockerfile present"}
        if not _sandbox_network_up():
            return {
                "_skipped": True,
                "reason": (
                    "sandbox network qg_sandbox not up "
                    "(run qg setup + docker compose up -d in sandbox/)"
                ),
            }
        from orchestrator.images import IMAGES
        from orchestrator.toolrunner import container_exec
        from orchestrator.discovery import load_project_settings

        settings = load_project_settings(ctx.qg_root) or {}
        health_path = (settings.get("sandbox") or {}).get("health_path", "/health")

        out_dir = ctx.artifacts_dir / self.name
        out_dir.mkdir(parents=True, exist_ok=True)
        scripts = ctx.qg_root / "sandbox" / "k6"
        network = "qg_sandbox"
        results = {}
        failures = []
        for profile_name in ("smoke", "load"):
            # A stale summary from a previous run must never be read as this
            # run's evidence — delete before the run, not after.
            for stale in (out_dir / f"{profile_name}.json", out_dir / "summary.json"):
                stale.unlink(missing_ok=True)
            mounts = [
                f"type=bind,src={scripts},dst=/scripts,readonly",
                f"type=bind,src={out_dir},dst=/out",
            ]
            res = container_exec(
                IMAGES["k6"],
                [
                    "run",
                    "-e",
                    "BASE_URL=http://app:8000",
                    "-e",
                    f"HEALTH_PATH={health_path}",
                    f"/scripts/{profile_name}.js",
                ],
                cwd=ctx.project_root,
                mounts=mounts,
                network=network,
            )
            self._cmd_log.append(f"k6 run {profile_name}")
            self._exit_log.append(res.returncode)
            if res.returncode != 0:
                failures.append(
                    f"k6 {profile_name}: {res.stderr.strip() or res.returncode}"
                )
                continue
            # k6 handleSummary writes /out/summary.json; the per-profile name
            # is preferred for tooling that writes one file per run.
            summary = out_dir / f"{profile_name}.json"
            if not summary.exists():
                summary = out_dir / "summary.json"
            if summary.exists():
                results[profile_name] = json.loads(summary.read_text())
        if failures:
            return {"_error": "; ".join(failures)}
        return {"k6": results, "base_url": "http://app:8000"}

    def _extract_metrics(self, raw: dict) -> dict[str, float]:
        metrics = {}
        for name in ("smoke", "load"):
            p95 = raw.get("k6", {}).get(name, {}).get("p95_ms")
            if p95 is not None:
                metrics[f"k6.{name}_p95_ms"] = float(p95)
        return metrics
