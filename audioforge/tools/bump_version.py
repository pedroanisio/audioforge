"""Version-bump tool + consistency gate (roadmap item AF-R09).

`audioforge/version.py` (`ENGINE_VERSION`, `DSL_VERSION`) is the single source of
truth. Every other version literal must agree; this tool both *gates* that and
*performs* a coordinated bump so the sites cannot half-drift.

    python -m audioforge.tools.bump_version --check          # fail if any site disagrees
    python -m audioforge.tools.bump_version 2.17.0            # bump engine, rewrite all sites
    python -m audioforge.tools.bump_version 2.17.0 --dsl 2.0  # bump engine + DSL
    python -m audioforge.tools.bump_version 2.17.0 --dry-run  # print the plan, write nothing

Managed sites: `audioforge/version.py`, `pyproject.toml [project].version`,
`README.md` banner, and a new `CHANGELOG.md` section skeleton. `make version-check`
runs `--check`; `tests/test_version_sources.py` remains the pytest guard.

⚠ ARCHITECTURAL CONTRACT (PALS's LAW): a version scattered across files is a
claim that can silently disagree. The `--check` gate makes disagreement a loud
failure, not a shipped inconsistency.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION_PY = ROOT / "audioforge" / "version.py"
PYPROJECT = ROOT / "pyproject.toml"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"

_SEMVER = r"[0-9]+\.[0-9]+\.[0-9]+"
_DSLVER = r"[0-9]+\.[0-9]+"


def truth() -> tuple[str, str]:
    """(engine, dsl) from the single source of truth, audioforge/version.py."""
    txt = VERSION_PY.read_text(encoding="utf-8")
    engine = re.search(r'ENGINE_VERSION\s*=\s*"([^"]+)"', txt).group(1)
    dsl = re.search(r'DSL_VERSION\s*=\s*"([^"]+)"', txt).group(1)
    return engine, dsl


def _found_versions() -> dict[str, tuple[str | None, str | None]]:
    """{site: (engine_found, dsl_found)} for every non-source-of-truth site."""
    out: dict[str, tuple[str | None, str | None]] = {}
    pj = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"', PYPROJECT.read_text(encoding="utf-8"))
    out["pyproject.toml"] = (pj.group(1) if pj else None, None)
    readme = README.read_text(encoding="utf-8")
    re_ = re.search(rf"Engine\s+({_SEMVER})", readme)
    rd = re.search(rf"DSL\s+({_DSLVER})", readme)
    out["README.md"] = (re_.group(1) if re_ else None, rd.group(1) if rd else None)
    return out


def check() -> tuple[bool, list[str]]:
    """Every managed site must match version.py. Returns (ok, report)."""
    engine, dsl = truth()
    report: list[str] = []
    ok = True
    for site, (e_found, d_found) in _found_versions().items():
        if e_found != engine:
            ok = False
            report.append(f"{site}: engine {e_found!r} != source-of-truth {engine!r}")
        if d_found is not None and d_found != dsl:
            ok = False
            report.append(f"{site}: dsl {d_found!r} != source-of-truth {dsl!r}")
    if ok:
        report.append(f"all version sites agree: engine {engine}, dsl {dsl}")
    return ok, report


def _sub_once(path: Path, pattern: str, repl: str, plan: list[str], dry: bool) -> None:
    text = path.read_text(encoding="utf-8")
    new, n = re.subn(pattern, repl, text, count=1)
    if n == 0:
        raise RuntimeError(f"{path.name}: no site matched /{pattern}/ — cannot bump safely")
    try:
        label = path.relative_to(ROOT)
    except ValueError:
        label = path.name  # sandboxed copy outside the repo (tests)
    if new != text:
        plan.append(f"  {label}: updated")
        if not dry:
            path.write_text(new, encoding="utf-8")
    else:
        plan.append(f"  {label}: already current")


def bump(new_engine: str, new_dsl: str | None = None, dry_run: bool = False) -> list[str]:
    """Rewrite every managed site to new_engine/new_dsl and insert a CHANGELOG stub."""
    if not re.fullmatch(_SEMVER, new_engine):
        raise ValueError(f"engine version {new_engine!r} is not MAJOR.MINOR.PATCH")
    old_engine, old_dsl = truth()
    new_dsl = new_dsl or old_dsl
    if new_dsl is not None and not re.fullmatch(_DSLVER, new_dsl):
        raise ValueError(f"dsl version {new_dsl!r} is not MAJOR.MINOR")
    plan = [f"bump engine {old_engine} -> {new_engine}, dsl {old_dsl} -> {new_dsl}"
            + ("  (dry run)" if dry_run else "")]
    _sub_once(VERSION_PY, r'(ENGINE_VERSION\s*=\s*)"[^"]+"', rf'\g<1>"{new_engine}"', plan, dry_run)
    _sub_once(VERSION_PY, r'(DSL_VERSION\s*=\s*)"[^"]+"', rf'\g<1>"{new_dsl}"', plan, dry_run)
    _sub_once(PYPROJECT, r'(?m)(^\s*version\s*=\s*)"[^"]+"', rf'\g<1>"{new_engine}"', plan, dry_run)
    _sub_once(README, rf"Engine\s+{_SEMVER}", f"Engine {new_engine}", plan, dry_run)
    _sub_once(README, rf"DSL\s+{_DSLVER}", f"DSL {new_dsl}", plan, dry_run)
    if CHANGELOG.exists():
        _sub_once(
            CHANGELOG,
            r"(## \[Unreleased\]\n)",
            rf"\g<1>\n## [{new_engine}]\n\n_Engine {new_engine} · DSL {new_dsl}._\n",
            plan,
            dry_run,
        )
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m audioforge.tools.bump_version",
        description="Gate (--check) or perform a coordinated version bump across all sites.",
    )
    parser.add_argument("engine_version", nargs="?", help="new engine version MAJOR.MINOR.PATCH")
    parser.add_argument("--dsl", help="new DSL version MAJOR.MINOR (default: keep current)")
    parser.add_argument("--check", action="store_true", help="assert all sites agree; write nothing")
    parser.add_argument("--dry-run", action="store_true", help="print the bump plan; write nothing")
    args = parser.parse_args(argv)

    if args.check or not args.engine_version:
        ok, report = check()
        stream = sys.stdout if ok else sys.stderr
        for line in report:
            stream.write(f"version-check: {line}\n")
        if not ok:
            stream.write("version-check: run `python -m audioforge.tools.bump_version <version>` "
                         "to bump all sites atomically.\n")
        return 0 if ok else 1

    for line in bump(args.engine_version, args.dsl, dry_run=args.dry_run):
        print(line)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
