"""Project profile: what discovery knows about the analyzed project."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ProjectProfile:
    language: str = "unknown"
    framework: str = "unsupported"
    db: str | None = None
    cache: str | None = None
    docker: bool = False
    test_system: str | None = None
    endpoints: list[dict] = field(default_factory=list)
    # App dir relative to the project root; "." when the app is at the root
    # (spec §10.1).
    app_root: str = "."

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())

    @classmethod
    def load(cls, path: Path) -> ProjectProfile:
        return cls(**json.loads(path.read_text()))
