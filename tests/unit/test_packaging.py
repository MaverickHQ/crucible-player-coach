"""Packaging contracts — pinned because v2.0.0 shipped with two latent defects
that the unit test suite couldn't catch:

D1 — `.gitignore` had an unanchored `artifacts/` pattern that matched both
the runtime `./artifacts/` dump directory AND the `player_coach/artifacts/`
Python module. Hatchling honours `.gitignore` when collecting wheel files,
so `pip install player-coach-core` users got a package missing
`player_coach.artifacts.writer` — every CoachLoop import chain broke at
runtime.

D2 — `pyproject.toml` declared only `ewm-core` as a dependency. The actual
runtime imports `yfinance`, `arch`, `hmmlearn`, and `anthropic` (via the
[llm] extra). `pip install player-coach-core` users hit `ModuleNotFoundError`
the moment they tried to import `BacktestRunner`.

Both bugs predated v1.0.0 (May 2026). Nobody noticed because development
happens from `git clone` where `requirements.txt` covers everything. These
tests turn each defect into a hard contract.
"""
from __future__ import annotations

import ast
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# D1 — .gitignore must not match any tracked player_coach file
# ---------------------------------------------------------------------------


def _hatchling_style_gitignore_match(rel_path: str, patterns: list[str]) -> str | None:
    """Mimic hatchling's pathspec-based gitignore matcher: a pattern without
    a leading `/` matches the path *at any depth*; with `/` it only matches
    the repo root. Crucially this does NOT do git's "tracked overrides
    ignore" check — so a pattern like `artifacts/` matches both `./artifacts/`
    AND `./player_coach/artifacts/`, which is what hatchling sees when
    deciding what to ship in the wheel. Returns the matched pattern or None.
    """
    parts = rel_path.split("/")
    for raw in patterns:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        anchored = line.startswith("/")
        is_dir = line.endswith("/")
        name = line.strip("/").lstrip("/")
        # Only handle simple-name patterns — that's what bit us in
        # `artifacts/`. Real pathspec is more powerful; this is the
        # narrowest matcher that catches the specific defect class.
        if "*" in name or "?" in name or "[" in name:
            continue
        if anchored:
            if is_dir and parts[0] == name and len(parts) > 1:
                return line
            if not is_dir and parts[0] == name:
                return line
        else:
            # Unanchored — matches at any depth.
            if is_dir and name in parts[:-1]:
                return line
            if not is_dir and name in parts:
                return line
    return None


def test_no_tracked_player_coach_file_matches_gitignore() -> None:
    """D1 — every file tracked under player_coach/ must NOT be matched by
    `.gitignore` under hatchling's pathspec semantics (unanchored patterns
    match at any depth, ignoring git's "tracked overrides ignore" rule).

    The v2.0.0 PyPI release shipped without `player_coach/artifacts/*`
    because `.gitignore:12` had `artifacts/` (unanchored), which matched
    both the runtime dump directory AND the Python sub-module. Anchor with
    a leading `/` (`/artifacts/`) so it only matches the repo root, or use
    a more specific path.
    """
    ls_files = subprocess.run(
        ["git", "ls-files", "player_coach/"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    tracked = ls_files.stdout.strip().splitlines()
    assert tracked, "expected tracked files under player_coach/"

    patterns = (REPO_ROOT / ".gitignore").read_text().splitlines()
    falsely_matched: list[tuple[str, str]] = []
    for f in tracked:
        hit = _hatchling_style_gitignore_match(f, patterns)
        if hit:
            falsely_matched.append((f, hit))

    assert not falsely_matched, (
        "tracked player_coach files are matched by .gitignore patterns; "
        "hatchling will silently drop them from the wheel:\n"
        + "\n".join(f"  {f}  ← rule: {rule}" for f, rule in falsely_matched)
        + "\n\nFix: anchor the offending pattern with a leading `/` so it "
        "only matches the repo root, e.g. `/artifacts/` instead of "
        "`artifacts/`."
    )


# ---------------------------------------------------------------------------
# D2 — declared deps must cover every non-stdlib runtime import
# ---------------------------------------------------------------------------


# stdlib modules + project-internal names that don't need declaring.
_STDLIB_AND_INTERNAL = {
    "player_coach",
    # core stdlib touched by player_coach
    "os", "sys", "json", "re", "typing", "pathlib", "dataclasses", "datetime",
    "collections", "functools", "itertools", "enum", "abc", "logging",
    "warnings", "math", "statistics", "uuid", "time", "contextlib", "copy",
    "threading", "queue", "io", "tempfile", "numbers", "zoneinfo",
    "__future__",
    # extension stdlib modules
    "sqlite3", "pickle", "asyncio", "concurrent",
}


def _collect_top_level_imports(pkg_dir: Path) -> set[str]:
    """Walk every .py under pkg_dir, AST-parse, return the set of top-level
    package names imported. Skips stdlib + the package itself."""
    found: set[str] = set()
    for py in pkg_dir.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module.split(".")[0])
    return found - _STDLIB_AND_INTERNAL


def _declared_distributions() -> set[str]:
    """Read pyproject.toml and return the set of declared distribution names
    across [project.dependencies] and every [project.optional-dependencies]
    table. Distribution names are normalised (lowercase, hyphen→underscore
    deferred to import-name comparison)."""
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    project = data["project"]
    names: set[str] = set()

    def _strip_extras_and_version(spec: str) -> str:
        # Take everything before the first non-name character.
        token = ""
        for ch in spec.strip():
            if ch.isalnum() or ch in "-_.":
                token += ch
            else:
                break
        return token.lower().replace("-", "_")

    for spec in project.get("dependencies", []):
        names.add(_strip_extras_and_version(spec))
    for extras in project.get("optional-dependencies", {}).values():
        for spec in extras:
            names.add(_strip_extras_and_version(spec))
    return names


# Mapping from distribution name (pyproject) → import name when they differ.
# Most packages use the same name for both; only the exceptions go here.
# ewm-core is special: it's our own sibling package and brings numpy/pandas
# transitively, so we accept those imports as covered by `ewm-core`.
_DIST_TO_IMPORTS = {
    "ewm_core": {"ewm_core", "numpy", "pandas", "pydantic"},
}


def _expand_declared_imports(declared_dists: set[str]) -> set[str]:
    """Expand declared distribution names into the import names they cover,
    including transitive deps we know about (numpy/pandas via ewm-core)."""
    expanded = set(declared_dists)
    for dist, imports in _DIST_TO_IMPORTS.items():
        if dist in declared_dists:
            expanded |= imports
    return expanded


def test_declared_dependencies_cover_runtime_imports() -> None:
    """D2 — every non-stdlib package that `player_coach/` imports must be
    declared in pyproject.toml's `dependencies` or `optional-dependencies`.
    Pre-v2.0.1, only `ewm-core` was declared, so a fresh pip install of
    `player-coach-core` could not even `import BacktestRunner` without
    `ModuleNotFoundError: yfinance`.
    """
    actual_imports = {
        name.lower().replace("-", "_")
        for name in _collect_top_level_imports(REPO_ROOT / "player_coach")
    }
    declared = _expand_declared_imports(_declared_distributions())
    missing = actual_imports - declared
    assert not missing, (
        "player_coach imports these packages but pyproject.toml doesn't "
        f"declare them (directly or via known transitives):\n"
        f"  {sorted(missing)}\n"
        f"Declared: {sorted(declared)}\n"
        "Add to [project.dependencies] (always-installed) or to a "
        "[project.optional-dependencies] table (extras like [llm])."
    )


def test_pyproject_declares_llm_extra_for_anthropic() -> None:
    """The CLAUDE.md install ladder documents `pip install
    player-coach-core[llm]` as the anthropic-enabled install. Pin that the
    extra exists and resolves to the anthropic SDK."""
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    optional = data["project"].get("optional-dependencies", {})
    assert "llm" in optional, (
        "[llm] extra is documented in CLAUDE.md but missing from pyproject.toml"
    )
    llm_specs = [s.lower() for s in optional["llm"]]
    assert any("anthropic" in spec for spec in llm_specs), (
        f"[llm] extra should pull anthropic; got {optional['llm']}"
    )


# Defensive sanity check — make sure tomllib is available (3.11+).
# Required so the two tests above don't get silently skipped on an older
# Python that lacks tomllib.
def test_tomllib_available() -> None:
    assert sys.version_info >= (3, 11), (
        "Repo requires Python 3.11+ for tomllib used in packaging tests"
    )
