"""
The purity lint. This is the mechanism, not a suggestion.

`app/stats/` is pure: no database, no network, no clock, no module-level mutable
state, seeded randomness only. That rule is what makes every statistical service
testable offline against a known analytic answer, and it is the reason the whole
engine can be exercised without Postgres.

A rule enforced by review decays. This walks every module under `app/stats/`,
parses it, and fails if one imports `app.repository`, `app.services`,
`sqlalchemy`, `httpx` or `requests`, or reads a clock. It runs on every commit,
so a future violation is caught by CI rather than by whoever happens to read the
diff.

Deliberately AST-based rather than grep-based: a comment mentioning sqlalchemy
should not fail the build, and `import sqlalchemy as sa` inside a function
should.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

STATS_ROOT = pathlib.Path(__file__).resolve().parents[3] / "app" / "stats"

# The forbidden roots, from docs/RULES.md and the working agreement's rule 4.
FORBIDDEN_IMPORT_ROOTS = (
    "app.repository",
    "app.services",
    "sqlalchemy",
    "httpx",
    "requests",
    "aiohttp",
    "urllib",
    "socket",
    "psycopg",
    "asyncpg",
    "redis",
    "boto3",
    "app.models",
    "app.core",
    "app.api",
    "app.verticals",
)

# Reading a clock makes a function non-deterministic and silently changes every
# params_hash. "Now" arrives as StreamWindow.end (spine rule S6).
FORBIDDEN_CALLS = (
    "datetime.now",
    "datetime.utcnow",
    "date.today",
    "time.time",
    "time.monotonic",
    "os.urandom",
    "uuid.uuid4",
    "uuid.uuid1",
)


def stats_modules() -> list[pathlib.Path]:
    return sorted(p for p in STATS_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def _parse(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_roots(tree: ast.Module) -> list[tuple[str, int]]:
    """Every module name this file imports, wherever the import sits."""
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # a relative import cannot leave the package
                continue
            if node.module:
                found.append((node.module, node.lineno))
    return found


def _dotted(node: ast.AST) -> str:
    """"a.b.c" for an attribute chain, so datetime.datetime.now resolves."""
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def test_stats_package_is_not_empty():
    """A lint that silently walks zero files passes forever and proves nothing."""
    modules = stats_modules()
    assert len(modules) > 20, "expected the whole stats package, found " + str(len(modules))


@pytest.mark.parametrize("path", stats_modules(), ids=lambda p: p.name)
def test_module_imports_nothing_impure(path: pathlib.Path):
    tree = _parse(path)
    violations = [
        (name, lineno)
        for name, lineno in _imported_roots(tree)
        for root in FORBIDDEN_IMPORT_ROOTS
        if name == root or name.startswith(root + ".")
    ]
    assert not violations, (
        str(path.relative_to(STATS_ROOT.parent.parent))
        + " breaks the purity rule by importing "
        + ", ".join(name + " (line " + str(line) + ")" for name, line in violations)
        + ". Services fetch; app/stats/ does mathematics. If you need data you do not have, "
        "raise InsufficientData or return Evidence(insufficient_data=True)."
    )


@pytest.mark.parametrize("path", stats_modules(), ids=lambda p: p.name)
def test_module_reads_no_clock(path: pathlib.Path):
    tree = _parse(path)
    violations = [
        (_dotted(node.func), node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _dotted(node.func).endswith(FORBIDDEN_CALLS)
    ]
    assert not violations, (
        str(path.name)
        + " reads a clock or an unseeded source of entropy: "
        + ", ".join(name + " (line " + str(line) + ")" for name, line in violations)
        + ". Nothing in app/stats/ reads a clock: 'now' arrives as StreamWindow.end, "
        "and randomness takes an explicit seed argument (spine rule S6)."
    )


@pytest.mark.parametrize("path", stats_modules(), ids=lambda p: p.name)
def test_module_has_no_mutable_module_level_state(path: pathlib.Path):
    """
    A module-level list or dict that a function mutates makes two identical calls
    return different answers, which is exactly the bug the reproducibility test
    in bandits.freeze_and_report would eventually catch, months later, in a
    committee meeting.

    Two exceptions. `__all__` is a list by convention and is never mutated. The
    registry's own REGISTRY and PACKS dicts are written once at import and only
    read afterwards, and the test asserting the registry matches
    docs/STATS_CATALOG.md is what keeps that honest.
    """
    tree = _parse(path)
    allowed = {"__all__"}
    if path.name == "registry.py":
        allowed |= {"REGISTRY", "PACKS"}
    offenders: list[str] = []
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for target in targets:
            if not isinstance(target, ast.Name) or target.id in allowed:
                continue
            value = node.value
            if isinstance(value, (ast.List, ast.Dict, ast.Set)):
                offenders.append(target.id + " (line " + str(node.lineno) + ")")
            elif isinstance(value, ast.Call) and _dotted(value.func) in ("list", "dict", "set", "Counter"):
                offenders.append(target.id + " (line " + str(node.lineno) + ")")
    assert not offenders, (
        path.name
        + " declares mutable module-level state: "
        + ", ".join(offenders)
        + ". Use a tuple, a frozenset, or a Mapping built once and never written."
    )


def test_lint_catches_a_deliberate_violation(tmp_path: pathlib.Path):
    """
    The lint's own known-answer test.

    A lint nobody has watched fail is a lint nobody knows works. This plants each
    kind of violation and asserts the detectors fire, so the passing runs above
    mean something.
    """
    impure = tmp_path / "impure.py"
    impure.write_text(
        "import sqlalchemy\n"
        "from app.repository import RequestRepository\n"
        "from datetime import datetime\n"
        "CACHE = {}\n"
        "def go():\n"
        "    return datetime.utcnow()\n"
    )
    tree = _parse(impure)

    hits = [
        name
        for name, _ in _imported_roots(tree)
        for root in FORBIDDEN_IMPORT_ROOTS
        if name == root or name.startswith(root + ".")
    ]
    assert set(hits) == {"sqlalchemy", "app.repository"}

    clock_hits = [
        _dotted(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _dotted(node.func).endswith(FORBIDDEN_CALLS)
    ]
    assert clock_hits == ["datetime.utcnow"]

    state_hits = [
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and isinstance(node.value, (ast.Dict, ast.List, ast.Set))
    ]
    assert state_hits == ["CACHE"]


def test_a_comment_mentioning_sqlalchemy_does_not_fail(tmp_path: pathlib.Path):
    """The lint is AST-based for this reason: prose about the rule is not a breach of it."""
    benign = tmp_path / "benign.py"
    benign.write_text(
        "# This module must never import sqlalchemy or app.repository.\n"
        'DOC = "app.services fetches; we do mathematics"\n'
        "def go():\n"
        "    return 1\n"
    )
    tree = _parse(benign)
    hits = [
        name
        for name, _ in _imported_roots(tree)
        for root in FORBIDDEN_IMPORT_ROOTS
        if name == root or name.startswith(root + ".")
    ]
    assert hits == []
