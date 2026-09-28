---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 via Claude Code; revised by Claude Opus 5.5 via Claude Code"
  date: "2026-09-28"
---

# ShadowMD

**A CLI-only, Nix-like immutable overlay layer for Markdown files.**

ShadowMD turns Markdown files into controlled, read-only *projections* backed by
an immutable hidden store. The visible `.md` files stay easy to read, preview,
sync and inspect — but they are no longer the locus of mutation. The source of
truth is `.shadowmd/`, and the only write API is the CLI:

```text
You do not edit Markdown files directly.
You ask ShadowMD to mutate them.
ShadowMD records every mutation immutably.
```

## Disclaimer

This work is subject to the methodological caveats and commitments described in
[@DISCLAIMER.md](./DISCLAIMER.md).
> No statement or premise not backed by a real logical definition or verifiable reference should be taken for granted.

## Why

A managed file becomes a read-only projection of a content-addressed,
time-travelling store. Direct edits are caught (never silently absorbed),
history is immutable, and every change flows through a single audited write path
with write-ahead journaling and crash recovery. It borrows:

- **content addressing + immutability** from Nix,
- **the blob / manifest / ref object model and on-demand diffs** from Git,
- **forward-recorded restores** (an accidental restore is itself undoable) from
  Time Machine.

The full rationale — including an honest account of what `chmod 0444` does and
does *not* guarantee — lives in [docs/design.md](./docs/design.md).

## Not Markdown-specific

The core (blob store, snapshots, journal, locking, projection) is
content-agnostic and operates on bytes. "Markdown" is only the default value of
`tracked_extensions` in `.shadowmd/config.json`. Widen it and the same machinery
manages any text files — ShadowMD generalises to a text-overlay tool without a
rewrite.

## Install

```bash
pip install -e .            # from a checkout
pip install -e ".[dev]"     # with pytest, ruff, mypy
```

Zero runtime dependencies — the implementation is deliberately Python-stdlib only
(`hashlib`, `difflib`, `os.replace`, `argparse`).

## Quick start

```bash
shadowmd init                       # create .shadowmd/ in the current directory
shadowmd inject article.md          # take control; file becomes 0444
shadowmd append article.md "More."  # mutate through the CLI
shadowmd log                        # list snapshots
shadowmd timeline article.md        # one file's history
shadowmd diff article.md --against-index
shadowmd restore article.md --snapshot snap_...   # forward-recorded restore
```

If something edits the file behind ShadowMD's back, the next operation refuses
to proceed and tells you how to resolve it:

```text
Integrity violation: article.md was modified outside ShadowMD.
  Expected: sha256:abc...
  Actual:   sha256:def...

Resolve with: `shadowmd repair FILE --restore-projection` (discard) or `shadowmd absorb FILE -m MSG` (keep).
```

## Commands

| Group | Commands |
|---|---|
| Repository | `init`, `status`, `fsck`, `gc`, `unlock --stale` |
| Injection | `inject`, `eject` |
| Mutation | `edit`, `append`, `prepend`, `replace`, `apply`, `mv`, `rm`, `begin`/`commit`/`abort` |
| History | `snapshot`, `log`, `timeline`, `cat`, `diff`, `restore` |
| Integrity | `verify-projection`, `repair`, `absorb`, `protect [--strict]`, `unprotect` |

Every write command is sugar over one internal mutation primitive — no command
has its own write path. See the [design doc](./docs/design.md) §9.

## Enforcement, honestly

| Layer | Mechanism | Strength |
|---|---|---|
| 1 | `chmod 0444` | accident protection (default) |
| 2 | projection-hash verification | **detection — the real guarantee** |
| 3 | `chattr +i` (Linux, opt-in `--strict`) | tamper resistance |

Permission bits stop casual saves but not a determined owner. The authoritative
guarantee is Layer 2: an external write can never be *silently absorbed* into
history. `protect --strict` adds true immutability where the platform supports
it.

## Development

```bash
pytest                                  # run the suite
pytest --cov=shadowmd --cov-report=term # coverage (lib target 80%, CLI 60%)
ruff check src tests                    # lint
mypy                                    # strict type-check
```

Tests run against real `.shadowmd` repositories in temp directories — the
atomic-IO, locking and journal paths are exercised for real, not mocked.

## Architecture

```text
shadowmd/
  __main__.py     # `python -m shadowmd` entry point
  cli.py          # the only write API; typed errors -> exit codes
  errors.py       # typed errors (the CLI maps them to exit codes)
  repo.py         # discovery, init, operation orchestration, reentrant repo lock
  store.py        # content-addressed blob storage (sha256 fan-out)
  index.py        # atomic working-projection index
  snapshot.py     # immutable manifests, refs, HEAD
  mutation.py     # the single mutation primitive (§9.4)
  projection.py   # atomic read-only projection + integrity verification (§9.3, §11)
  journal.py      # write-ahead operation log (§9.2)
  locks.py        # repo/file lock hierarchy + stale detection (§9.1)
  fsck.py         # integrity verification + journal recovery
  restore.py gc.py status.py diff.py patchtools.py
  atomicio.py hashing.py protection.py config.py layout.py ids.py models.py jsonio.py
```

## License

MIT — see [LICENSE](./LICENSE).
