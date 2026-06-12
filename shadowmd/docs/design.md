---
title: "ShadowMD — A CLI-Only, Nix-Like Immutable Overlay Layer for Markdown Files"
version: 2
status: draft-design
date: 2026-06-12
disclaimer: >
  No information in this document should be taken for granted. Any statement
  or premise not backed by a real logical definition or a verifiable reference
  may be invalid, erroneous, or a hallucination. Platform-specific claims
  (POSIX rename atomicity, chmod/chattr semantics, Windows file-attribute
  behavior) must be verified against the cited primary sources and tested on
  target systems before being relied upon.
references:
  - "POSIX rename(): https://pubs.opengroup.org/onlinepubs/9699919799/functions/rename.html"
  - "Python os.replace: https://docs.python.org/3/library/os.html#os.replace"
  - "Git object model: https://git-scm.com/book/en/v2/Git-Internals-Git-Objects"
  - "Nix store / content addressing: https://nixos.org/manual/nix/stable/store/"
  - "chattr(1): https://man7.org/linux/man-pages/man1/chattr.1.html"
---

# ShadowMD

**ShadowMD is a Nix-like immutable shadow store and CLI-controlled mutation layer for Markdown timelines.** It makes Markdown files read-only projections of an immutable, time-traveling content store.

---

# 1. Purpose

ShadowMD is a local-first versioning and overlay system for Markdown files.

It creates a hidden control layer inside a project directory and converts selected Markdown files into managed, read-only artifacts. Once a file is injected into ShadowMD, direct editing of the physical Markdown file is forbidden. All changes must happen through the ShadowMD CLI.

ShadowMD behaves like a simplified, Markdown-specific combination of:

* Nix-style immutable content-addressed storage
* Git-like snapshot history
* Time Machine-like restoration
* CLI-controlled write operations
* read-only projected working files

The user continues to see normal `.md` files in the working directory, but those files are projections of ShadowMD-managed state.

---

# 2. Core Principle

After a Markdown file is injected into ShadowMD:

```text
The visible Markdown file becomes a read-only projection.
The canonical state lives inside .shadowmd.
All changes must be performed through the ShadowMD CLI.
```

Direct modification is treated as an integrity violation.

ShadowMD is not just a backup tool. It is a controlled mutation layer.

---

# 3. Enforcement Model — What "Read-Only" Actually Guarantees

This section is deliberately honest about the strength of each layer, because the original framing ("direct save attempts should fail at the filesystem permission level") overstates what `chmod` provides.

ShadowMD enforcement has three layers, in increasing strength:

```text
Layer 1: chmod 0444          — accident protection (default)
Layer 2: projection hashing  — detection (always on, the real guarantee)
Layer 3: chattr +i (Linux)   — tamper resistance (optional, "strict")
```

## 3.1 Layer 1 — Permission bits (advisory)

`chmod 0444` stops casual saves: most editors will refuse to write, `>` redirection fails, sync tools see an ordinary read-only file.

It does **not** stop a determined or careless user, because:

* The file owner can always `chmod +w` the file back.
* If the parent directory is writable, the file can be **deleted and recreated** regardless of its own permission bits (POSIX `unlink` requires write permission on the *directory*, not the file).
* Some editors (notably `vim` with `:w!`) work around read-only files by removing and rewriting them.

Conclusion: permission bits are a guardrail against accidents, not an enforcement mechanism. They are still the right default because they catch the overwhelmingly common failure mode (absent-minded direct edits) at zero cost.

## 3.2 Layer 2 — Projection hash verification (authoritative)

The index records the expected SHA-256 of every projected file. Every CLI operation verifies the visible file against the expected hash before doing anything else. Any mismatch is reported as an integrity violation and blocks mutation until explicitly resolved (§11).

This is the layer ShadowMD actually relies on. It cannot prevent an external write, but it guarantees an external write can never be **silently absorbed** into history.

## 3.3 Layer 3 — Immutable flag (optional strict mode)

On Linux with supporting filesystems (ext4, xfs, btrfs), `chattr +i` makes a file unmodifiable, undeletable, and unrenameable even by its owner; only a process with `CAP_LINUX_IMMUTABLE` (typically root) can clear the flag. This is real tamper resistance but:

* requires elevated privileges to set and clear,
* is Linux-specific and filesystem-dependent,
* breaks ShadowMD's own write path unless the flag is toggled around every mutation.

It is therefore exposed as opt-in strict protection (`shadowmd protect FILE --strict`) and is never the default.

## 3.4 What about making the parent directory read-only?

The original design proposed `chmod 0555` on directories containing injected files. **This is dropped.** A read-only parent directory:

* prevents the user from creating *untracked* files next to managed ones (normal workflow breakage),
* breaks ShadowMD's own atomic update, because `rename()`/`os.replace()` into a directory requires **write permission on that directory**,
* still doesn't protect against the owner, who can `chmod` it back.

The cost/benefit is strictly worse than file-level `0444` plus hash verification. Directory-level protection is not part of the design.

## 3.5 Platform notes

* **macOS / BSD:** `chmod 0444` behaves as on Linux; `chattr` does not exist (the analogous `chflags uchg` could be a future strict backend).
* **Windows:** Python's `Path.chmod(0o444)` maps to `FILE_ATTRIBUTE_READONLY`. Note that `os.replace()` onto a read-only target **fails on Windows** (it succeeds on POSIX); the write path must clear the attribute on the target immediately before replacing it (§9.3).

---

# 4. Directory Layout

Given a normal folder:

```text
notes/
  article.md
  ideas/foo.md
```

ShadowMD initializes a hidden control directory:

```text
notes/
  article.md
  ideas/foo.md
  .shadowmd/
    config.json
    index.json
    HEAD
    refs/
    snapshots/
    blobs/
    locks/
    journal/
    tmp/
```

Note: there is no `deltas/` directory in the MVP layout. Deltas are demoted from a primary storage object to an on-demand computation and a future storage optimization (§5.3, §16.4).

## 4.1 `.shadowmd/config.json`

Repository configuration.

```json
{
  "version": 1,
  "tracked_extensions": [".md"],
  "readonly_projection": true,
  "mutation_mode": "cli-only",
  "auto_snapshot": true,
  "created_at": "2026-06-12T14:23:11Z"
}
```

## 4.2 `.shadowmd/index.json`

Current working projection index. The index itself is mutable state and **must be rewritten atomically** (write to `tmp/`, fsync, `os.replace`) — the same discipline applied to projected files.

```json
{
  "version": 1,
  "files": {
    "article.md": {
      "file_id": "f_01HX...",
      "path": "article.md",
      "content_hash": "sha256:abc...",
      "readonly": true,
      "last_snapshot": "snap_20260612T142311Z_8f3a"
    }
  }
}
```

Change from v1 of this design: the separate `projection_hash` field is removed. In the original schema it was always written equal to `content_hash` and verified against the same physical file, so it carried no information. One expected hash per file is sufficient: *index hash vs. actual file hash* is the only comparison that exists.

## 4.3 `.shadowmd/blobs/`

Immutable full-content objects, addressed by content hash (same fan-out scheme as Git's loose objects and the Nix store):

```text
.shadowmd/blobs/sha256/ab/cdef...
```

## 4.4 `.shadowmd/snapshots/`

Immutable snapshot manifests:

```text
.shadowmd/snapshots/snap_20260612T142311Z_8f3a.json
```

## 4.5 `.shadowmd/refs/` and `HEAD`

Mutable named references to immutable snapshots:

```text
refs/main -> snap_20260612T142311Z_8f3a
HEAD      -> refs/main
```

## 4.6 `.shadowmd/locks/`

Operation locks (§9.1).

## 4.7 `.shadowmd/journal/`

Append-only **write-ahead** operation journal (§9.2). Every CLI mutation writes an intent entry before touching the working tree and a commit entry after.

## 4.8 `.shadowmd/tmp/`

Staging area for atomic writes. Must live on the same filesystem as the working tree, because `os.replace()` is only atomic within one filesystem (cross-device renames raise `EXDEV`).

---

# 5. Object Model

## 5.1 Blob

A blob is immutable full content, addressed by hash:

```json
{
  "hash": "sha256:abc...",
  "size": 1821,
  "created_at": "2026-06-12T14:23:11Z"
}
```

Writing a blob is itself atomic: write to `tmp/`, fsync, `os.replace` into `blobs/`. If the target path already exists, the content is identical by construction (content addressing) and the write is skipped.

## 5.2 Snapshot

A snapshot is an immutable manifest of all managed files:

```json
{
  "id": "snap_20260612T142311Z_8f3a",
  "created_at": "2026-06-12T14:23:11Z",
  "message": "initial import",
  "parent": null,
  "root": {
    "article.md": {
      "file_id": "f_abc",
      "path": "article.md",
      "content_hash": "sha256:123...",
      "size": 1821
    }
  }
}
```

Snapshots are full manifests; content is deduplicated through blobs. This makes restore simple and safe (no chain replay needed to materialize any state).

**Snapshot ID format.** Timestamp-only IDs (the original `snap_2026-06-12T14-23-11Z`) collide whenever two snapshots land in the same second — which auto-snapshot mode makes likely. IDs therefore append a short random suffix: `snap_<UTC compact timestamp>_<4 hex chars>`. (An alternative is content-addressing the manifest itself, Git-style; the suffix scheme is chosen for the MVP because it keeps IDs chronologically sortable by prefix.)

## 5.3 Deltas (derived data, not primary storage)

The original design stored, for every mutation, both the new full blob **and** a unified diff between old and new hashes. Since blobs alone fully determine every version, persisted deltas are redundant data with their own failure modes (a corrupt delta store that disagrees with the blob store).

Revised position:

* `shadowmd diff` **computes** unified diffs on demand from two blobs (Python `difflib.unified_diff` is sufficient and dependency-free). Unified diff remains the right display format for Markdown: readable, line-oriented, inspectable.
* Persisted deltas return later as a **storage compaction** strategy (§16.4), the same way Git keeps loose objects and repacks them into delta-compressed packfiles offline — not as part of the hot write path.

## 5.4 Journal entry

```json
{
  "seq": 142,
  "ts": "2026-06-12T15:02:44Z",
  "phase": "intent",
  "operation": "mutate",
  "path": "article.md",
  "old_hash": "sha256:abc...",
  "new_hash": "sha256:def...",
  "message": "expanded intro"
}
```

Each logical operation produces two entries: `intent` (before the working tree is touched, after the new blob is durably stored) and `commit` (after index update). `shadowmd fsck` uses unpaired `intent` entries to detect and roll forward/back interrupted operations (§9.2).

---

# 6. Stable File Identity

ShadowMD separates file identity from file path. A file has a stable `file_id`:

```json
{
  "file_id": "f_01HX...",
  "current_path": "article.md",
  "previous_paths": ["draft.md", "notes/draft.md"],
  "content_hash": "sha256:abc..."
}
```

This allows ShadowMD to track

```text
draft.md -> article.md -> essays/article.md
```

as the same logical Markdown document across its whole timeline.

## 6.1 Renames are explicit, not detected

Because injected files are read-only and every mutation flows through the CLI, renames are performed — and therefore *known*, not guessed:

```bash
shadowmd mv draft.md article.md
```

Heuristic rename detection (path disappeared + path appeared + identical or similar hash) is **not** part of the core model. It survives only in one narrow corner: `shadowmd absorb` (§11.2), where an external change is being reconciled and the tool may *suggest* a rename classification for the user to confirm. It never auto-classifies.

This is a simplification relative to v1 of the design, which specified both an explicit `mv` and a similarity-based detection rule. Keeping both creates two sources of truth for the same event; the explicit command wins.

---

# 7. Injection and Ejection

ShadowMD does not automatically control every Markdown file. A file must be explicitly injected:

```bash
shadowmd inject article.md
shadowmd inject notes/**/*.md
```

After injection:

1. The file receives a stable `file_id`.
2. Its current content is stored as an immutable blob.
3. An initial snapshot entry is recorded.
4. The visible file is set read-only (`0444`).
5. All future writes must go through the ShadowMD CLI.

The user can still open and read the file normally in editors, previewers, terminals, and Markdown renderers. Casual save attempts fail at the permission level (with the caveats of §3.1).

## 7.1 Ejection

```bash
shadowmd eject article.md
```

Ejection removes the file from ShadowMD control and restores normal write permissions (`0644` or the pre-injection mode recorded at inject time). Semantics the original design left unspecified, now fixed:

* The file's blobs and its appearances in existing snapshots are **retained**. History is never destroyed by ejection.
* The file's entry is removed from the index; future snapshots no longer include it.
* Objects that become unreachable only if snapshots are later deleted are reclaimed by `shadowmd gc`, never by `eject` itself.
* Re-injecting a previously ejected file creates a **new** `file_id` by default; `shadowmd inject --resume-identity f_01HX...` reattaches to the old timeline explicitly.

---

# 8. Mutation Rules

Direct editing is forbidden.

Invalid:

```bash
vim article.md        # blocked by 0444; if forced, detected as a violation
```

Valid:

```bash
shadowmd edit article.md
shadowmd append article.md "New paragraph"
shadowmd prepend article.md "Text"
shadowmd replace article.md --content-file new.md
shadowmd apply article.md patch.diff
shadowmd mv article.md essays/article.md
shadowmd rm article.md
```

ShadowMD is the sole write API for injected Markdown files. Every one of these commands is sugar over a single internal primitive (§9.4); none has its own write path.

---

# 9. The Canonical Write Path

This section consolidates what v1 of the design described four separate times (CLI write window, editing flow, atomic projection update, and mutation code), with conflicting details between the copies. There is exactly one write path.

## 9.1 Locking

Two lock levels, acquired in a fixed order to prevent deadlock:

```text
repo lock   — held by snapshot, restore, gc, fsck, begin/commit groups
file lock   — held per managed file by any mutation
order       — repo lock (if needed) before file lock; never the reverse
```

Implementation: lock files created with `O_CREAT | O_EXCL` in `.shadowmd/locks/`, containing PID, hostname, and timestamp. A lock whose PID no longer exists (same host) or whose age exceeds a configurable staleness bound is reported by `shadowmd status` and can be cleared with `shadowmd unlock --stale`. `O_EXCL` creation is atomic on POSIX local filesystems; this is a local-first tool, so network-filesystem lock semantics are out of scope (documented limitation).

## 9.2 Write-ahead journaling

v1 appended the journal entry *after* the projection update, which means a crash between projection write and journal write leaves a change history never heard about. Order is reversed — the journal is write-ahead:

```text
1. Store new blob (durable, content-addressed, idempotent)
2. Append journal "intent" entry  (fsync journal)
3. Update the projected file atomically (§9.3)
4. Rewrite index atomically
5. Append journal "commit" entry
```

Crash recovery (`shadowmd fsck`):

* `intent` without `commit`, projection hash == old hash → roll back: nothing happened visibly; mark entry aborted.
* `intent` without `commit`, projection hash == new hash → roll forward: redo index update, append `commit`.
* The new blob is durable before the intent entry, so both branches always have the content they need.

## 9.3 Atomic projection update

```text
target = article.md
temp   = .shadowmd/tmp/article.md.<random>

1. Write new content to temp
2. fsync temp
3. chmod temp to 0444                  # target is never writable, not even briefly
4. [Windows only] clear FILE_ATTRIBUTE_READONLY on target
5. os.replace(temp, target)            # atomic on POSIX same-filesystem rename
6. fsync parent directory              # make the rename itself durable
```

Corrections relative to v1:

* v1 step "temporarily unlock target path" is removed. POSIX `rename()` requires write permission on the **directory**, not the target file; making the target writable before replacing it only opens an unnecessary window in which the file is editable. The target's permission bits never change on POSIX. (On Windows the read-only attribute must be cleared first because `os.replace` onto a read-only file fails there — that is the only "unlock", and it is immediately superseded by the replace.)
* The temp directory `.shadowmd/tmp/` is required to be on the same filesystem as the working tree; otherwise `os.replace` raises `EXDEV` and atomicity is lost. `shadowmd init` verifies this.

References: POSIX `rename()` atomicity — pubs.opengroup.org (rename); Python `os.replace` cross-platform semantics — docs.python.org/3/library/os.html#os.replace.

## 9.4 The single mutation primitive

```python
def mutate_file(repo, path: str, new_content: bytes, message: str) -> None:
    repo.acquire_file_lock(path)
    try:
        repo.verify_projection(path)          # §11 — abort on drift

        old_hash = repo.index.files[path].content_hash
        new_hash = repo.store_blob(new_content)   # durable before journal

        if old_hash == new_hash:
            return                            # no-op; nothing recorded

        entry = repo.journal.intent(
            operation="mutate", path=path,
            old_hash=old_hash, new_hash=new_hash, message=message,
        )

        repo.write_projection_atomically(path, new_content)   # §9.3

        repo.index.update_file(path=path, content_hash=new_hash)
        repo.index.write_atomically()

        repo.journal.commit(entry)

        if repo.config.auto_snapshot and not repo.in_transaction:
            repo.snapshot(message)            # takes repo lock internally

    finally:
        repo.release_file_lock(path)
```

No command bypasses this primitive.

## 9.5 The `edit` flow

`shadowmd edit article.md` wraps the primitive with an editor session:

```text
1. Verify file is injected and projection is intact
2. Copy current content to a writable temp file in .shadowmd/tmp/
3. Open $EDITOR against the temp file
4. On editor exit, read temp content
5. mutate_file(path, new_content, message)
```

The user never edits the canonical projected file directly; they edit a ShadowMD-owned temporary copy.

---

# 10. Snapshot and Restore Semantics

## 10.1 Snapshot modes

**Manual:** mutations accumulate; snapshots are explicit.

```bash
shadowmd edit article.md
shadowmd snapshot -m "expanded introduction"
```

**Auto (default):** every CLI mutation creates a snapshot, except inside an explicit group:

```bash
shadowmd begin -m "restructure essay"
shadowmd mv draft.md essay.md
shadowmd edit essay.md
shadowmd append references.md "..."
shadowmd commit            # one snapshot for the whole group
```

`begin` takes the repo lock and opens a transaction marker in the journal; `commit` snapshots and releases; `shadowmd abort` rolls the group back by restoring each touched file's pre-transaction blob (possible because every step was journaled).

## 10.2 Restore never rewrites history

Restoring is itself a mutation, recorded going forward — Time Machine semantics, not Git `reset --hard` semantics:

```bash
shadowmd restore article.md --snapshot snap_a   # one file
shadowmd restore --snapshot snap_a              # whole tree
```

Both forms write the restored content through the canonical write path and then create a **new** snapshot whose manifest equals (in whole or part) the old one, with a message recording the provenance (`restored from snap_a`). `HEAD` only ever advances. This preserves invariant 4 (§17) — no snapshot is ever modified or orphaned by a restore — and means an accidental restore is itself undoable.

Inspecting without restoring:

```bash
shadowmd cat article.md --snapshot snap_a
shadowmd timeline article.md
shadowmd diff article.md --from snap_a --to snap_b
```

Example timeline output:

```text
article.md

2026-06-12 14:23:11  snap_..._8f3a  initial import
2026-06-12 15:02:44  snap_..._b21c  expanded intro
2026-06-12 16:19:10  snap_..._09de  renamed from draft.md
```

---

# 11. Integrity Model

Before any operation, ShadowMD verifies:

```text
sha256(current visible file) == index.content_hash
```

On mismatch:

```text
Integrity violation:
article.md was modified outside ShadowMD.
Expected: sha256:abc...
Actual:   sha256:def...
```

All mutation commands abort on violation. Recovery is explicit:

```bash
shadowmd diff article.md --against-index        # inspect the drift
shadowmd repair article.md --restore-projection # discard external change
shadowmd absorb article.md -m "manual emergency edit"   # keep it
```

## 11.1 External change policy

Default: **reject**. Nothing enters history without an explicit command.

## 11.2 Absorption

`absorb` stores the external content as a new blob, journals it with `operation: "absorb"` (distinguishable forever from CLI mutations), updates the index, snapshots, and re-asserts read-only permissions. Absorption never happens silently, and the journal makes every absorption auditable.

---

# 12. CLI Commands

## 12.1 Repository

```bash
shadowmd init
shadowmd status
shadowmd fsck
shadowmd gc
shadowmd unlock --stale
```

## 12.2 Injection

```bash
shadowmd inject FILE...
shadowmd eject FILE
```

## 12.3 Mutation

```bash
shadowmd edit FILE
shadowmd append FILE TEXT
shadowmd prepend FILE TEXT
shadowmd replace FILE --content-file NEW.md
shadowmd apply FILE PATCH.diff
shadowmd mv OLD.md NEW.md
shadowmd rm FILE
shadowmd begin -m MSG / shadowmd commit / shadowmd abort
```

## 12.4 Snapshots, history, restore

```bash
shadowmd snapshot -m MSG
shadowmd log
shadowmd timeline FILE
shadowmd cat FILE --snapshot ID
shadowmd diff FILE [--from ID --to ID | --against-index]
shadowmd restore [FILE] --snapshot ID
```

## 12.5 Protection and verification

```bash
shadowmd protect FILE [--strict]     # --strict = chattr +i where supported
shadowmd unprotect FILE [--strict]
shadowmd verify-projection FILE
shadowmd repair FILE --restore-projection
shadowmd absorb FILE -m MSG
```

---

# 13. Design Lineage

ShadowMD preserves the following properties from its inspirations:

## 13.1 From Nix

* **Content addressing:** `sha256(content) -> blob path`.
* **Immutability:** once written, blobs and snapshots are never modified.
* **Mutable refs over immutable objects:** `refs/main -> snap_...`, `HEAD -> refs/main`.
* **Garbage collection:** objects unreachable from any ref or snapshot are reclaimable via `shadowmd gc`.
* **Reproducible projection:** any snapshot can deterministically rematerialize the visible Markdown tree.

## 13.2 From Git

* The blob/manifest/ref object model and the loose-object fan-out layout.
* On-demand diffs between any two content states.
* The future packfile-style compaction strategy (§16.4).

## 13.3 From Time Machine

* Restores are forward-recorded events, not history rewinds (§10.2).
* Per-file timelines (`shadowmd timeline`) and whole-tree point-in-time restore.

---

# 14. Minimal Python Architecture

```text
shadowmd/
  __main__.py
  cli.py
  repo.py          # repository discovery and initialization
  config.py
  index.py         # atomic index read/write
  store.py         # content-addressed blob storage
  snapshot.py      # snapshot creation and loading
  projection.py    # atomic read-only file projection (§9.3)
  protection.py    # permission enforcement (§3)
  mutation.py      # the single mutation primitive (§9.4)
  journal.py       # write-ahead operation log (§9.2)
  locks.py         # repo/file lock hierarchy (§9.1)
  restore.py
  status.py
  diff.py          # on-demand unified diffs (difflib)
  gc.py
  fsck.py          # integrity verification + journal recovery
```

(Relative to v1: `delta.py`, `blob.py`, and `rename.py` are gone — deltas are computed on demand in `diff.py`, blob logic lives in `store.py`, and rename heuristics were cut in §6.1. `locks.py` is added.)

## 14.1 Core interfaces

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BlobRef:
    algorithm: str
    digest: str

    @property
    def uri(self) -> str:
        return f"{self.algorithm}:{self.digest}"


@dataclass(frozen=True)
class ManagedFile:
    file_id: str
    path: str
    content_hash: str
    readonly: bool


@dataclass(frozen=True)
class Snapshot:
    id: str
    created_at: str
    parent: str | None
    message: str
    root: dict[str, ManagedFile]


class ProjectionViolation(Exception):
    pass


class ShadowRepository:
    def __init__(self, root: Path):
        self.root = root
        self.store = root / ".shadowmd"

    def verify_projection(self, path: str) -> None: ...
    def inject(self, path: str) -> None: ...
    def mutate_file(self, path: str, new_content: bytes, message: str) -> None: ...
    def snapshot(self, message: str) -> Snapshot: ...
    def restore(self, snapshot_id: str, path: str | None = None) -> None: ...
```

## 14.2 Protection implementation

```python
import stat
from pathlib import Path

READONLY = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH          # 0444
OWNER_RW = READONLY | stat.S_IWUSR                              # 0644


def make_readonly(path: Path) -> None:
    path.chmod(READONLY)


def make_writable_by_owner(path: Path) -> None:
    path.chmod(OWNER_RW)


def is_readonly(path: Path) -> bool:
    return not bool(path.stat().st_mode & stat.S_IWUSR)
```

On Windows, `chmod(0o444)` sets `FILE_ATTRIBUTE_READONLY`; `is_readonly` works unchanged. Strict mode shells out to `chattr ±i` and must verify both privilege and filesystem support before claiming success.

---

# 15. MVP Scope

The first working version supports:

```bash
shadowmd init
shadowmd inject FILE
shadowmd status
shadowmd edit FILE
shadowmd append FILE TEXT
shadowmd snapshot -m MESSAGE
shadowmd log
shadowmd timeline FILE
shadowmd cat FILE --snapshot ID
shadowmd diff FILE [--from ID --to ID | --against-index]
shadowmd restore [FILE] --snapshot ID
shadowmd verify-projection FILE
shadowmd repair FILE --restore-projection
shadowmd absorb FILE -m MSG
shadowmd fsck
```

MVP requirements:

```text
- Hidden .shadowmd folder
- Explicit injection / ejection
- Read-only (0444) projected Markdown files
- CLI-only mutation through one primitive
- Content-addressed blob store (full blobs only)
- Snapshot manifests with collision-safe IDs
- On-demand unified diffs (difflib)
- Stable file_id, explicit renames
- Projection hash verification before every operation
- Atomic projection and index writes (same-filesystem tmp/)
- Write-ahead journal with fsck recovery
- Repo/file lock hierarchy with stale-lock detection
```

(`diff`, `repair`, `absorb`, and `fsck` are promoted into the MVP relative to v1: a tool whose core promise is "external changes are rejected" must ship the inspection and recovery commands for that rejection in its first version, or the first violation strands the user.)

---

# 16. Future Features (Non-Goals for MVP)

Explicitly out of MVP scope: FUSE, kernel overlayfs, background daemons, editor plugins, cloud sync, binary file optimization, multi-user collaboration, CRDTs.

## 16.1 Watch mode

```bash
shadowmd watch
```

Detect and report unauthorized external changes as they happen (inotify/FSEvents), instead of at next CLI use.

## 16.2 Historical mount

```bash
shadowmd mount .timeline
```

Expose snapshots as read-only folders:

```text
.timeline/
  20260612T142311Z/article.md
  20260612T150244Z/article.md
```

## 16.3 Branches

```bash
shadowmd branch experiment
shadowmd checkout experiment
```

`refs/` already supports this structurally; `checkout` is a whole-tree restore plus a `HEAD` retarget.

## 16.4 Storage compaction

Offline repacking of old blobs into delta-compressed archives (zstd-compressed unified diffs, or xdelta3/bsdiff for chains), with periodic full-content checkpoints to bound reconstruction cost — Git's loose-object/packfile split. This is where deltas re-enter the design: as a `gc`-time optimization, keyed by `(base_hash, target_hash)`, never on the hot write path.

## 16.5 Strict protection backends

`chattr +i` (Linux), `chflags uchg` (macOS/BSD), as verified opt-in modes.

## 16.6 Semantic Markdown operations

```bash
shadowmd section rename article.md "Introduction" "Opening"
shadowmd section append article.md "References" ref.md
shadowmd frontmatter set article.md status draft
shadowmd heading move article.md "Notes" --after "Background"
```

---

# 17. Safety Invariants

ShadowMD must enforce:

```text
 1. Injected Markdown files are read-only projections (0444),
    with drift detection as the authoritative guarantee (§3).
 2. All changes happen through the ShadowMD CLI's single
    mutation primitive.
 3. No blob is ever modified after creation.
 4. No snapshot is ever modified after creation; restores only
    ever create new snapshots.
 5. Every mutation verifies projection integrity first.
 6. Every mutation stores new content durably before journaling,
    and journals intent before touching the working tree.
 7. Projection and index updates are atomic (same-filesystem
    rename), and the target file is never left writable —
    on POSIX it is never made writable at all.
 8. External changes are rejected by default; absorbing one
    requires explicit user intent and is permanently journaled
    as an absorption.
 9. Ejection releases a file without destroying its history.
10. fsck can always resolve an interrupted operation to a
    consistent state using the write-ahead journal.
```

---

# 18. Summary

ShadowMD turns Markdown files into controlled, read-only projections backed by an immutable hidden store. The visible `.md` files remain easy to read, preview, sync, and inspect — but they are no longer the locus of mutation. The source of truth is `.shadowmd/`, and the only write API is the CLI:

```text
You do not edit Markdown files directly.
You ask ShadowMD to mutate them.
ShadowMD records every mutation immutably.
```
