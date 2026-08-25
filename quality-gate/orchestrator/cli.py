"""CLI `qg`: explicit subcommands only, no passthrough (spec §8.1)."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

from orchestrator.core import ExitCodes, RunContext

PROJECT_ROOT = Path.cwd()
QG_ROOT = PROJECT_ROOT / "quality-gate"

STATUS_TO_EXIT = {
    "PASS": ExitCodes.PASS,
    "WARN": ExitCodes.PASS,
    "FAIL": ExitCodes.FAIL,
    "ERROR": ExitCodes.INFRA,
    "SKIPPED": ExitCodes.PASS,
}


def _fresh_ctx(project_root: Path | None = None) -> RunContext:
    project_root = PROJECT_ROOT if project_root is None else project_root
    qg, artifacts, reports = QG_ROOT, QG_ROOT / "artifacts", QG_ROOT / "reports"
    # %f (microseconds) guards against two runs within the same second
    # silently sharing one run_id directory.
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    artifacts = artifacts / run_id
    reports = reports / run_id
    artifacts.mkdir(parents=True, exist_ok=True)
    return RunContext(
        project_root=project_root,
        qg_root=qg,
        artifacts_dir=artifacts,
        reports_dir=reports,
    )


def _analyze_and_guard() -> dict | None:
    """Print the state banner; enforce require_branch/require_clean.

    Returns the fingerprint, or None when a guard blocked the run
    (message already printed).
    """
    from orchestrator.discovery import load_project_settings, settings_error
    from orchestrator.gitinfo import check_run_guards, git_fingerprint, state_banner

    analyzed = git_fingerprint(PROJECT_ROOT)
    print(state_banner(analyzed))
    # A malformed settings.json must fail CLOSED before anything runs:
    # running with silently-empty settings means no guards at all.
    err = settings_error(QG_ROOT)
    if err:
        print(f"blocked: {err}")
        return None
    # load_project_settings returns the "project" subset; check_run_guards
    # expects the full settings shape with a "project" key.
    err = check_run_guards(analyzed, {"project": load_project_settings(QG_ROOT)})
    if err:
        print(f"blocked: {err}")
        return None
    return analyzed


def cmd_init() -> int:
    template = QG_ROOT / "sandbox" / ".env.qg.template"
    env_file = QG_ROOT / ".env.qg"
    if not env_file.exists() and template.exists():
        env_file.write_text(template.read_text())
    for d in (QG_ROOT / "artifacts", QG_ROOT / "reports"):
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitignore").write_text("*\n")
    missing = [t for t in ("docker", "uv") if shutil.which(t) is None]
    if missing:
        print(f"missing host tools: {', '.join(missing)}")
        return ExitCodes.INFRA
    print("quality gate initialized")
    return ExitCodes.PASS


def cmd_discover() -> int:
    from orchestrator.discovery import DiscoveryError, discover, find_app_root

    profile_path = QG_ROOT / "artifacts" / "project-profile.json"
    try:
        app_root, source = find_app_root(PROJECT_ROOT, QG_ROOT)
    except DiscoveryError as exc:
        print(f"discovery failed: {exc}")
        return ExitCodes.INFRA
    profile = discover(app_root)
    profile.app_root = str(app_root.relative_to(PROJECT_ROOT))
    profile.save(profile_path)
    print(profile.to_json())
    print(f"app root: {profile.app_root} ({source})")
    if profile.framework == "unsupported":
        print("unsupported stack: only python+fastapi and python+django (v0.1)")
        return ExitCodes.INFRA
    return ExitCodes.PASS


def cmd_setup() -> int:
    import subprocess

    venv = QG_ROOT / ".venv"
    if not (venv / "bin" / "python").exists():
        subprocess.run(["uv", "venv", str(venv)], check=True)
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(venv / "bin" / "python"),
                "-r",
                str(QG_ROOT / "config" / "tools.requirements.txt"),
            ],
            check=True,
        )
    profile_path = QG_ROOT / "artifacts" / "project-profile.json"
    if profile_path.exists():
        from orchestrator.profile import ProjectProfile

        profile = ProjectProfile.load(profile_path)
        if profile.docker:
            from orchestrator.sandbox import compose_up

            ctx = _fresh_ctx(project_root=PROJECT_ROOT / profile.app_root)
            proc = compose_up(ctx)
            print(proc.stdout or proc.stderr)
            if proc.returncode != 0:
                return ExitCodes.INFRA
        # Provision the analyzed project's declared deps so functional_testing
        # coverage means something. Best-effort: never crashes setup. Skipped
        # when no profile exists yet (run qg discover).
        if profile.framework != "unsupported":
            from orchestrator.adapters.base import get_adapter

            try:
                deps = get_adapter(profile.framework)().get_dependencies(
                    PROJECT_ROOT / profile.app_root
                )
            except Exception as exc:  # noqa: BLE001 — best-effort provisioning
                print(f"warning: could not read project dependencies: {exc}")
                deps = []
            if deps:
                reqs = QG_ROOT / "artifacts" / "project-requirements.txt"
                reqs.write_text("\n".join(deps) + "\n")
                # Project deps go into a DEDICATED venv (artifacts/deps-venv),
                # never the gate venv: installing them there could clobber the
                # gate's pinned tool versions (e.g. the project needs
                # ruff>=0.8 but the gate pins ruff==0.6.9), silently breaking
                # reproducibility of the gate's own checks.
                deps_venv = QG_ROOT / "artifacts" / "deps-venv"
                proc = subprocess.run(
                    [
                        "uv",
                        "venv",
                        "--python",
                        str(venv / "bin" / "python"),
                        str(deps_venv),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc.returncode != 0:
                    print(
                        "warning: could not create deps venv "
                        f"(functional_testing will fail): {proc.stderr.strip()}"
                    )
                else:
                    # pytest comes FIRST: it's a tool the gate provides (most
                    # projects don't declare it), and installing it before
                    # -r reqs lets a project that pins its own pytest in
                    # requirements.txt still win. coverage rides along last:
                    # the requirements rarely declare it, but the metrics
                    # step needs it.
                    for extra in (["pytest"], ["-r", str(reqs)], ["coverage"]):
                        proc = subprocess.run(
                            [
                                "uv",
                                "pip",
                                "install",
                                "--python",
                                str(deps_venv / "bin" / "python"),
                                *extra,
                            ],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        if proc.returncode != 0:
                            print(
                                "warning: could not install project test deps "
                                f"(functional_testing will fail): {proc.stderr.strip()}"
                            )
                            break
    print("setup complete")
    return ExitCodes.PASS


def cmd_run(trigger: str) -> int:
    from orchestrator.discovery import DiscoveryError, discover, find_app_root
    from orchestrator.reporting import write_summary
    from orchestrator.run import run_gate

    triggers_path = QG_ROOT / "config" / "triggers.yml"
    triggers = (
        yaml.safe_load(triggers_path.read_text()) if triggers_path.exists() else {}
    )
    if trigger not in triggers:
        print(f"unknown trigger: {trigger} (known: {', '.join(sorted(triggers))})")
        return ExitCodes.INFRA
    try:
        app_root, _source = find_app_root(PROJECT_ROOT, QG_ROOT)
    except DiscoveryError as exc:
        print(f"discovery failed: {exc}")
        return ExitCodes.INFRA
    analyzed = _analyze_and_guard()
    if analyzed is None:
        return ExitCodes.INFRA
    profile = discover(app_root)
    if profile.framework == "unsupported":
        print("unsupported stack: only python+fastapi and python+django (v0.1)")
        return ExitCodes.INFRA
    ctx = _fresh_ctx(project_root=app_root)
    ctx.analyzed = analyzed
    ctx.profile = profile.to_dict()
    results, status = run_gate(ctx, trigger=trigger)
    _, js = write_summary(ctx, results, status, trigger)
    print(f"status: {status}")
    print(f"report: {js}")
    return STATUS_TO_EXIT[status]


def cmd_run_skill(skill_name: str) -> int:
    from orchestrator.discovery import DiscoveryError, find_app_root
    from skills import get_skills

    skills = get_skills()
    if skill_name is None:
        print(f"usage: qg run-skill <skill> — available: {', '.join(sorted(skills))}")
        return ExitCodes.INFRA
    if skill_name not in skills:
        print(f"unknown skill: {skill_name} — available: {', '.join(sorted(skills))}")
        return ExitCodes.INFRA
    try:
        app_root, _source = find_app_root(PROJECT_ROOT, QG_ROOT)
    except DiscoveryError as exc:
        print(f"discovery failed: {exc}")
        return ExitCodes.INFRA
    analyzed = _analyze_and_guard()
    if analyzed is None:
        return ExitCodes.INFRA
    ctx = _fresh_ctx(project_root=app_root)
    ctx.analyzed = analyzed
    result = skills[skill_name]().run(ctx)
    print(json.dumps(result.to_dict(), indent=2))
    return STATUS_TO_EXIT[result.status.value]


def cmd_get_profile() -> int:
    path = QG_ROOT / "artifacts" / "project-profile.json"
    if not path.exists():
        print("no profile yet — run `qg discover`")
        return ExitCodes.PASS
    print(path.read_text())
    return ExitCodes.PASS


def cmd_get_results() -> int:
    last = QG_ROOT / "artifacts" / "last_run.txt"
    if not last.exists():
        print("no runs yet")
        return ExitCodes.PASS
    path = QG_ROOT / "artifacts" / last.read_text().strip() / "results.json"
    print(path.read_text())
    return ExitCodes.PASS


def cmd_get_report() -> int:
    last = QG_ROOT / "artifacts" / "last_run.txt"
    if not last.exists():
        print("no runs yet")
        return ExitCodes.PASS
    path = QG_ROOT / "reports" / last.read_text().strip() / "summary.json"
    print(path.read_text())
    return ExitCodes.PASS


def cmd_status() -> int:
    profile = QG_ROOT / "artifacts" / "project-profile.json"
    last = QG_ROOT / "artifacts" / "last_run.txt"
    # (QG_ROOT / ".env.qg") as a condition would always be truthy — Path
    # objects don't evaluate to their existence. Must call .exists().
    print(f"init: {'yes' if (QG_ROOT / '.env.qg').exists() else 'no (run qg init)'}")
    print(f"profile: {'yes' if profile.exists() else 'no (run qg discover)'}")
    if last.exists():
        run_id = last.read_text().strip()
        summary = QG_ROOT / "reports" / run_id / "summary.json"
        if summary.exists():
            data = json.loads(summary.read_text())
            print(f"last run: {run_id} status={data.get('status')}")
        else:
            print(f"last run: {run_id} status=n/a")
    else:
        print("last run: none")
    return ExitCodes.PASS


def cmd_cleanup(yes: bool) -> int:
    if not yes:
        print("cleanup removes artifacts/ and reports/; pass --yes to confirm")
        return ExitCodes.PASS

    for d in (QG_ROOT / "artifacts", QG_ROOT / "reports"):
        if d.exists():
            shutil.rmtree(d)
    from orchestrator.sandbox import compose_down

    proc = compose_down(_fresh_ctx())
    if proc.returncode != 0:
        return ExitCodes.INFRA
    print("cleaned")
    return ExitCodes.PASS


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="qg", description="Portable AI Quality Gate")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("discover")
    sub.add_parser("setup")
    run_p = sub.add_parser("run")
    run_p.add_argument("--trigger", default="pre_production")
    rs = sub.add_parser("run-skill")
    rs.add_argument("skill_name", nargs="?")
    sub.add_parser("get-profile")
    sub.add_parser("get-results")
    sub.add_parser("get-report")
    sub.add_parser("status")
    cl = sub.add_parser("cleanup")
    cl.add_argument("--yes", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "init": cmd_init,
        "discover": cmd_discover,
        "setup": cmd_setup,
        "run": lambda: cmd_run(args.trigger),
        "run-skill": lambda: cmd_run_skill(args.skill_name),
        "get-profile": cmd_get_profile,
        "get-results": cmd_get_results,
        "get-report": cmd_get_report,
        "status": cmd_status,
        "cleanup": lambda: cmd_cleanup(args.yes),
    }
    return handlers[args.command]()


if __name__ == "__main__":
    sys.exit(main())
