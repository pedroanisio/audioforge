"""Distribution gate: build, inspect, install and render (``make package-check``).

An in-repo test run cannot see what the wheel drops: the engine imports and the
suite passes while ``pip install audioforge`` ships an engine with no C kernel
sources (ADR-0012: every render compiles them) and no bundled samples. This gate
proves the distributions themselves:

1. build the sdist and wheel (or take them from ``--dist``);
2. assert both carry every non-Python file under ``audioforge/``;
3. install the wheel into a fresh virtual environment and, from a directory
   outside the repository, print the version and render a spec that pins a
   bundled sample — which compiles the native kernels from the installed copy.

    python -m audioforge.tools.package_check                # build into a temp dir
    python -m audioforge.tools.package_check --dist dist    # check prebuilt dists
    python -m audioforge.tools.package_check --dist dist --no-smoke

⚠ ARCHITECTURAL CONTRACT (PALS's LAW): "the package installs" is a claim about
artifacts nobody inspects by hand; it is verified here, not assumed.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Not runtime data: interpreter caches and per-CPU kernel builds.
_IGNORED_SUFFIXES = {".py", ".pyc", ".so", ".dylib", ".dll"}

# A bundled one-shot pinned by content hash: rendering it proves the sample
# ships and resolves from the package, and any render compiles the kernels.
SMOKE_SAMPLE = ("deep_knock.wav",
                "d7e1dc7271508d6118aec993ff6a3dc4f0b53861f261e551af1eff0ce404b9c0")


def smoke_source() -> str:
    name, sha = SMOKE_SAMPLE
    return (
        "asset package_smoke {\n"
        "  kind: cue\n"
        "  duration: 2s\n"
        "  tempo: 120bpm\n"
        f'  layer knock : sample {{ file: "{name}"\n'
        f'    sha256: "{sha}"\n'
        "    gain: -6db\n"
        "    pattern: x...x...x...x... }\n"
        "  layer tone : notes {\n"
        "    osc: struck\n"
        "    notes: C4 @ 0b for 2b, G4 @ 2b for 2b\n"
        "    gain: -12db }\n"
        "  master { peak: -1db }\n"
        "}\n")


def required_package_data(root: Path = ROOT) -> list[str]:
    """Package-relative paths of every non-Python file under ``audioforge/``."""
    pkg = root / "audioforge"
    out = []
    for path in pkg.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix in _IGNORED_SUFFIXES:
            continue
        out.append(path.relative_to(pkg).as_posix())
    return sorted(out)


def _dist_members(dist: Path) -> set[str]:
    """Paths inside the distribution, relative to the ``audioforge`` package."""
    if dist.suffix == ".whl":
        with zipfile.ZipFile(dist) as z:
            names = z.namelist()
    elif dist.name.endswith(".tar.gz"):
        with tarfile.open(dist) as t:
            names = [n.split("/", 1)[1] for n in t.getnames() if "/" in n]
    else:
        raise ValueError(f"{dist.name}: not a wheel or sdist")
    prefix = "audioforge/"
    return {n[len(prefix):] for n in names if n.startswith(prefix)}


def missing_from_dist(dist: Path, required: list[str]) -> list[str]:
    members = _dist_members(dist)
    return [rel for rel in required if rel not in members]


def find_dists(directory: Path) -> tuple[Path, Path]:
    wheels = sorted(directory.glob("audioforge-*.whl"))
    sdists = sorted(directory.glob("audioforge-*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise FileNotFoundError(
            f"{directory}: expected one wheel and one sdist, found "
            f"{[p.name for p in wheels + sdists]}")
    return wheels[0], sdists[0]


def build(out_dir: Path) -> None:  # pragma: no cover - exercised by `make package-check`
    if shutil.which("uv"):
        cmd = ["uv", "build", "--sdist", "--wheel", "--out-dir", str(out_dir), str(ROOT)]
    else:
        cmd = [sys.executable, "-m", "build", "--sdist", "--wheel",
               "--outdir", str(out_dir), str(ROOT)]
    subprocess.run(cmd, check=True)
    shutil.rmtree(ROOT / "build", ignore_errors=True)  # setuptools' staging dir


def smoke(wheel: Path, work: Path) -> None:  # pragma: no cover - exercised by `make package-check`
    venv = work / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    bindir = venv / ("Scripts" if os.name == "nt" else "bin")
    py = bindir / ("python.exe" if os.name == "nt" else "python")
    subprocess.run([str(py), "-m", "pip", "install", "-q", str(wheel)], check=True)
    project = work / "project"
    project.mkdir()
    (project / "smoke.af").write_text(smoke_source(), encoding="utf-8")
    # Outside the repo, with a private kernel cache: nothing may leak in from
    # the source tree or a previous build.
    env = {**os.environ, "AUDIOFORGE_NATIVE_CACHE": str(work / "kernels")}
    env.pop("PYTHONPATH", None)
    run = dict(cwd=project, env=env, check=True)
    subprocess.run([str(bindir / "audioforge"), "--version"], **run)
    subprocess.run([str(py), "-c",
                    "import audioforge, pathlib, sys; "
                    "p = pathlib.Path(audioforge.__file__).resolve(); "
                    f"sys.exit(0 if {str(ROOT.resolve())!r} not in str(p) else "
                    "'imported from the source tree: ' + str(p))"], **run)
    subprocess.run([str(bindir / "audioforge"), "render", "smoke.af", "-o", "out"], **run)
    wavs = list((project / "out").rglob("*.wav"))
    if not wavs:
        raise RuntimeError("installed engine rendered no WAV")
    print(f"package-check: installed wheel rendered {wavs[0].relative_to(project)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m audioforge.tools.package_check",
                                     description=__doc__.splitlines()[0])
    parser.add_argument("--dist", type=Path, help="directory holding the built wheel + sdist")
    parser.add_argument("--no-smoke", action="store_true",
                        help="inspect contents only; skip the clean-venv install and render")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="audioforge-package-") as tmp:
        work = Path(tmp)
        dist_dir = args.dist
        if dist_dir is None:  # pragma: no cover - exercised by `make package-check`
            dist_dir = work / "dist"
            build(dist_dir)
        wheel, sdist = find_dists(dist_dir)
        required = required_package_data()
        failed = False
        for dist in (wheel, sdist):
            missing = missing_from_dist(dist, required)
            if missing:
                failed = True
                print(f"package-check: {dist.name} is missing {missing}", file=sys.stderr)
            else:
                print(f"package-check: {dist.name} carries all {len(required)} data files")
        if failed:
            return 1
        if not args.no_smoke:  # pragma: no cover - exercised by `make package-check`
            smoke(wheel, work)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
