"""Discovery: detect stack → ProjectProfile (spec §10).

App-root resolution (spec §10.1): the analyzed app may live in a
subdirectory (monorepo). Priority: settings.json override > heuristic
scan of common app dirs > project root itself. Ambiguity never guesses —
it raises DiscoveryError and asks for the override.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from orchestrator.adapters.base import get_adapter
from orchestrator.profile import ProjectProfile

# Candidate dirs probed when the root itself is not an app (spec §10.1).
APP_ROOT_CANDIDATES = ("backend", "src", "app", "server", "api")


class DiscoveryError(Exception):
    """App-root could not be resolved unambiguously (spec §10.1)."""


def settings_error(qg_root: Path | None) -> str | None:
    """Error message when settings.json exists but is invalid JSON.

    Lets callers fail closed (refuse to run) instead of silently treating a
    hand-edited settings file as "no settings". Returns None when the file
    is absent or parses.
    """
    if qg_root is None:
        return None
    path = qg_root / "settings.json"
    if not path.exists():
        return None
    try:
        json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return f"{path} is invalid JSON — fix it or delete it"
    return None


def load_project_settings(qg_root: Path | None) -> dict:
    """Project settings from quality-gate/settings.json (may be absent).

    Discover/setup must not break on a malformed file: returns {} and
    warns on stderr. Guarded runs fail closed via settings_error().
    """
    if qg_root is None:
        return {}
    err = settings_error(qg_root)
    if err:
        print(
            f"WARNING: {err} — ignored (gate runs without settings)",
            file=sys.stderr,
        )
        return {}
    path = qg_root / "settings.json"
    try:
        data = json.loads(path.read_text())
    except OSError:
        return {}
    return data.get("project", {}) or {}


def _looks_like_app(candidate: Path) -> bool:
    """Cheap framework-agnostic probe; adapters do the real detection."""
    if not (candidate / "pyproject.toml").exists() and not (
        candidate / "requirements.txt"
    ).exists():
        return False
    return (candidate / "app" / "main.py").exists() or (
        candidate / "manage.py"
    ).exists()


def find_app_root(
    project_root: Path, qg_root: Path | None = None
) -> tuple[Path, str]:
    """Resolve which directory holds the app to analyze.

    Returns (app_root, source) with source in {"settings", "heuristic",
    "root"}. Raises DiscoveryError when the override points nowhere or
    the heuristic is ambiguous.
    """
    settings = load_project_settings(qg_root)
    override = (settings.get("app_root") or "").strip()
    if override:
        target = project_root / override
        if not target.is_dir():
            raise DiscoveryError(
                f"app_root from settings.json does not exist: {override}"
            )
        return target, "settings"
    matches = [".", *APP_ROOT_CANDIDATES]
    hits = [name for name in matches if _looks_like_app(project_root / name)]
    if len(hits) > 1:
        raise DiscoveryError(
            "ambiguous app root: multiple candidates look like apps "
            f"({', '.join(sorted(hits))}); set project.app_root in "
            "quality-gate/settings.json"
        )
    if len(hits) == 1:
        name = hits[0]
        return project_root / name, ("root" if name == "." else "heuristic")
    return project_root, "root"


def _detect_framework(project_root: Path) -> str:
    for name in ("fastapi", "django"):
        try:
            adapter = get_adapter(name)()
            if adapter.detect(project_root):
                return name
        except Exception:  # noqa: BLE001, S112 — probing; failure = "not this stack"
            continue
    return "unsupported"


def discover(project_root: Path, out_path: Path | None = None) -> ProjectProfile:
    root = Path(project_root)
    framework = _detect_framework(root)
    db, cache = None, None
    deps = []
    try:
        adapter = get_adapter(framework)() if framework != "unsupported" else None
        deps = adapter.get_dependencies(root) if adapter else []
    except Exception:  # noqa: BLE001 — deps are best-effort for stack detection
        deps = []
    dep_text = " ".join(deps).lower()
    if "postgres" in dep_text or "psycopg" in dep_text:
        db = "postgres"
    if "redis" in dep_text:
        cache = "redis"
    endpoints = []
    for candidate in ("openapi.json", "openapi.yaml", "swagger.json"):
        p = root / candidate
        if p.exists():
            try:
                data = (
                    json.loads(p.read_text())
                    if p.suffix == ".json"
                    else yaml.safe_load(p.read_text())
                )
            except (json.JSONDecodeError, yaml.YAMLError):
                # A malformed spec must not crash discovery — treat as no
                # endpoints rather than failing the whole gate.
                continue
            for path, ops in (data or {}).get("paths", {}).items():
                for method in ("get", "post", "put", "delete"):
                    if method in ops:
                        endpoints.append({"method": method.upper(), "path": path})
            break
    profile = ProjectProfile(
        language="python",
        framework=framework,
        db=db,
        cache=cache,
        docker=(root / "Dockerfile").exists() or (root / "docker-compose.yml").exists(),
        test_system="pytest" if (root / "pyproject.toml").exists() else None,
        endpoints=endpoints,
    )
    if out_path:
        profile.save(out_path)
    return profile
