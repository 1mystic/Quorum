"""
A vertical is configuration, not code (docs/GLOSSARY.md). Each manifest is a JSON
file in app/verticals/manifests/ describing one kind of community: its labels,
which Insight Packs it turns on by default, its categories, its roles and its
auth mode.

This loader builds the data model side of C.3: it reads whatever manifests are
on disk and validates their shape. The seven manifests referenced in
docs/VERTICALS.md are the statistician's concurrent deliverable, not this
card's - so only two placeholders ship here, both marked provisional. They
exist to give TenantService.onboarding something real to load and to prove the
loader against a plausible shape; expect field names to shift once
docs/VERTICALS.md lands and this module is reconciled against it.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from functools import lru_cache

from app.exceptions import VerticalNotFoundError

MANIFEST_DIR = Path(__file__).parent / "manifests"


@dataclass(frozen=True)
class VerticalManifest:
    id: str
    label: str
    description: str
    default_packs: list[str] = field(default_factory=list)
    categories: dict[str, list[str]] = field(default_factory=dict)
    roles: list[str] = field(default_factory=list)
    auth_mode: str = "email_password"
    provisional: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "VerticalManifest":
        required = {"id", "label", "description"}
        missing = required - data.keys()
        if missing:
            raise ValueError(f"vertical manifest missing required fields: {sorted(missing)}")
        return cls(
            id=data["id"],
            label=data["label"],
            description=data["description"],
            default_packs=list(data.get("default_packs", [])),
            categories=dict(data.get("categories", {})),
            roles=list(data.get("roles", [])),
            auth_mode=data.get("auth_mode", "email_password"),
            provisional=bool(data.get("provisional", False)),
        )


@lru_cache(maxsize=1)
def _registry() -> dict[str, VerticalManifest]:
    registry: dict[str, VerticalManifest] = {}
    for path in sorted(MANIFEST_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        manifest = VerticalManifest.from_dict(data)
        registry[manifest.id] = manifest
    return registry


def get_manifest(vertical_id: str) -> VerticalManifest:
    manifest = _registry().get(vertical_id)
    if manifest is None:
        raise VerticalNotFoundError()
    return manifest


def list_manifests() -> list[VerticalManifest]:
    return list(_registry().values())
