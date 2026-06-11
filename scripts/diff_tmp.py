#!/usr/bin/env python3
"""Assert the diff between our codebase and the `_tmp/audioforge` tree.

`_tmp/audioforge` is a parallel copy of this project (the `audioforge/` package,
docs, tests, examples, presets) plus a few stand-alone tools. This walks both
source trees, compares them by relative path, and reports:

  · files only here          (we have, the copy doesn't)
  · files only in _tmp        (the copy has, we don't — candidate to merge)
  · files that differ         (same path, different content; with +/- lines)

Noise (caches, audio/render outputs, binaries, the _tmp tree itself) is skipped
so only mergeable source shows up.

Usage:
  python3 scripts/diff_tmp.py            # summary
  python3 scripts/diff_tmp.py --diffs    # + unified diff of every differing file
  python3 scripts/diff_tmp.py <relpath>  # unified diff of one file
"""
import difflib
import os
import sys

OURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEIRS = os.path.join(OURS, "_tmp", "audioforge")

SKIP_DIRS = {".git", "_tmp", "__pycache__", ".venv", ".pytest_cache",
             ".hypothesis", ".ruff_cache", ".mypy_cache",
             "libraries", "static", "tracks", "compare", "renders",
             "audio", "charts", "midi", "scores", "node_modules"}
SKIP_EXT = {".pyc", ".pyo", ".wav", ".mp3", ".m4a", ".mid", ".png", ".jpg",
            ".pdf", ".musicxml", ".zip", ".so", ".o"}
SKIP_SUFFIX = (".egg-info",)
TEXT_EXT = {".py", ".af", ".md", ".json", ".sh", ".c", ".h", ".txt", ".toml",
            ".cfg", ".ini", ".lock"}


def _walk(root):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS
                       and not any(d.endswith(s) for s in SKIP_SUFFIX)]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in SKIP_EXT:
                continue
            full = os.path.join(dirpath, fn)
            out[os.path.relpath(full, root)] = full
    return out


def _read(path):
    try:
        return open(path, encoding="utf-8", errors="replace").read().splitlines()
    except Exception:
        return None


def _delta(a, b):
    al, bl = _read(a), _read(b)
    if al is None or bl is None:
        return None
    add = sum(1 for ln in difflib.ndiff(al, bl) if ln.startswith("+ "))
    rem = sum(1 for ln in difflib.ndiff(al, bl) if ln.startswith("- "))
    return add, rem


def _udiff(rel, a, b):
    al, bl = _read(a) or [], _read(b) or []
    return "\n".join(difflib.unified_diff(
        bl, al, fromfile=f"_tmp/{rel}", tofile=f"ours/{rel}", lineterm=""))


def main(argv):
    if not os.path.isdir(THEIRS):
        print(f"no _tmp tree at {THEIRS}")
        return 2
    ours, theirs = _walk(OURS), _walk(THEIRS)

    # single-file diff mode
    if argv and not argv[0].startswith("-"):
        rel = argv[0]
        if rel in ours and rel in theirs:
            print(_udiff(rel, ours[rel], theirs[rel]) or "(identical)")
        else:
            print(f"{rel}: " + ("only in ours" if rel in ours else
                                "only in _tmp" if rel in theirs else "absent both"))
        return 0

    only_ours = sorted(set(ours) - set(theirs))
    only_theirs = sorted(set(theirs) - set(ours))
    common = sorted(set(ours) & set(theirs))
    differ = []
    for rel in common:
        d = _delta(ours[rel], theirs[rel])
        if d and (d[0] or d[1]):
            differ.append((rel, d[0], d[1]))

    print("=" * 70)
    print(f" diff: ours ({OURS})\n   vs  _tmp/audioforge")
    print("=" * 70)
    print(f"\nonly in OURS ({len(only_ours)}):")
    for r in only_ours:
        print(f"  + {r}")
    print(f"\nonly in _TMP ({len(only_theirs)})  <- candidate merges:")
    for r in only_theirs:
        print(f"  - {r}")
    print(f"\nDIFFER ({len(differ)})   [+N lines only in _tmp · -M lines only in ours]:")
    for rel, a, r in sorted(differ, key=lambda x: -(x[1] + x[2])):
        print(f"  ~ {rel:42} +{a} -{r}")
    print(f"\nidentical: {len(common) - len(differ)}  ·  "
          f"compared {len(set(ours) | set(theirs))} source files")

    if "--diffs" in argv:
        print("\n" + "=" * 70 + "\n unified diffs of differing files\n" + "=" * 70)
        for rel, _, _ in differ:
            ext = os.path.splitext(rel)[1].lower()
            if ext in TEXT_EXT:
                print(f"\n----- {rel} -----")
                print(_udiff(rel, ours[rel], theirs[rel]))

    return 1 if (only_theirs or differ) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
