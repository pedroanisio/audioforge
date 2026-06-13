"""Command-line interface — the *only* write API for managed files.

Graceful handling lives here (CLAUDE.md: typed errors in libraries, graceful
handling in applications). Every library ``ShadowError`` is turned into a clean
message and an exit code; nothing else leaks a traceback to the user.

Exit codes:
    0  success
    1  generic ShadowMD error
    2  integrity violation (external modification detected)
    3  usage error
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from . import __version__, patchtools, protection
from . import diff as diffmod
from . import fsck as fsckmod
from . import gc as gcmod
from . import restore as restoremod
from . import status as statusmod
from .errors import ProjectionViolation, ShadowError
from .repo import ShadowRepository

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_VIOLATION = 2
EXIT_USAGE = 3


# --- helpers -------------------------------------------------------------

def _repo() -> ShadowRepository:
    return ShadowRepository.discover()


def _relpath(repo: ShadowRepository, p: str) -> str:
    absolute = Path(p).resolve()
    try:
        return str(absolute.relative_to(repo.layout.root))
    except ValueError:
        raise ShadowError(
            f"{p} is outside the repository at {repo.layout.root}"
        ) from None


def _out(msg: str = "") -> None:
    print(msg)


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


# --- command handlers ----------------------------------------------------

def cmd_init(args: argparse.Namespace) -> int:
    repo = ShadowRepository.init(Path(args.path or "."))
    _out(f"Initialized empty ShadowMD repository in {repo.layout.control}")
    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    repo = _repo()
    st = statusmod.gather(repo)
    _out(f"branch: {st.branch}")
    _out(f"HEAD:   {st.head or '(no snapshots yet)'}")
    _out(f"auto-snapshot: {'on' if st.auto_snapshot else 'off'}")
    if st.in_transaction:
        _out(f"transaction OPEN: {st.transaction_message or ''}")
    _out("")
    if not st.files:
        _out("no files tracked")
    else:
        for f in st.files:
            flag = {"clean": " ", "drifted": "!", "missing": "?"}[f.state]
            _out(f" {flag} {f.path}  [{f.state}]")
    if st.stale_locks:
        _out("\nstale locks (clear with `shadowmd unlock --stale`):")
        for lk in st.stale_locks:
            _out(f"  {lk['name']}  pid={lk['pid']} reason={lk['reason']}")
    return EXIT_OK


def cmd_inject(args: argparse.Namespace) -> int:
    repo = _repo()
    rels = [_relpath(repo, p) for p in args.files]
    injected = repo.inject_many(rels)
    for mf in injected:
        _out(f"injected {mf.path}  {mf.file_id}")
    return EXIT_OK


def cmd_eject(args: argparse.Namespace) -> int:
    repo = _repo()
    rel = _relpath(repo, args.file)
    repo.eject(rel)
    _out(f"ejected {rel} (history retained)")
    return EXIT_OK


def cmd_edit(args: argparse.Namespace) -> int:
    repo = _repo()
    rel = _relpath(repo, args.file)
    repo.verify(rel)
    content = repo.current_content(rel)
    suffix = Path(rel).suffix or ".txt"
    tmp = repo.layout.tmp / f".edit.{os.getpid()}{suffix}"
    tmp.write_bytes(content)
    try:
        _launch_editor(tmp)
        new_content = tmp.read_bytes()
    finally:
        tmp.unlink(missing_ok=True)
    changed = repo.mutate_file(rel, new_content, args.message or f"edit {rel}")
    _out(f"{'updated' if changed else 'no changes to'} {rel}")
    return EXIT_OK


def _launch_editor(path: Path) -> None:
    editor = (
        os.environ.get("SHADOWMD_EDITOR")
        or os.environ.get("VISUAL")
        or os.environ.get("EDITOR")
    )
    if not editor:
        raise ShadowError("no editor set; export $EDITOR (or $SHADOWMD_EDITOR)")
    subprocess.run([*editor.split(), str(path)], check=True)


def cmd_append(args: argparse.Namespace) -> int:
    repo = _repo()
    rel = _relpath(repo, args.file)
    changed = repo.append(rel, args.text, args.message)
    _out(f"{'updated' if changed else 'no changes to'} {rel}")
    return EXIT_OK


def cmd_prepend(args: argparse.Namespace) -> int:
    repo = _repo()
    rel = _relpath(repo, args.file)
    changed = repo.prepend(rel, args.text, args.message)
    _out(f"{'updated' if changed else 'no changes to'} {rel}")
    return EXIT_OK


def cmd_replace(args: argparse.Namespace) -> int:
    repo = _repo()
    rel = _relpath(repo, args.file)
    content = Path(args.content_file).read_bytes()
    changed = repo.replace(rel, content, args.message)
    _out(f"{'updated' if changed else 'no changes to'} {rel}")
    return EXIT_OK


def cmd_apply(args: argparse.Namespace) -> int:
    repo = _repo()
    rel = _relpath(repo, args.file)
    repo.verify(rel)
    patch = Path(args.patch).read_bytes()
    new_content = patchtools.apply_unified(repo.current_content(rel), patch)
    changed = repo.mutate_file(rel, new_content, args.message or f"apply {args.patch} to {rel}")
    _out(f"{'updated' if changed else 'no changes to'} {rel}")
    return EXIT_OK


def cmd_mv(args: argparse.Namespace) -> int:
    repo = _repo()
    repo.move(_relpath(repo, args.old), _relpath(repo, args.new))
    _out(f"moved {args.old} -> {args.new}")
    return EXIT_OK


def cmd_rm(args: argparse.Namespace) -> int:
    repo = _repo()
    rel = _relpath(repo, args.file)
    repo.remove(rel)
    _out(f"removed {rel} (history retained)")
    return EXIT_OK


def cmd_begin(args: argparse.Namespace) -> int:
    repo = _repo()
    repo.begin(args.message)
    _out(f"transaction started: {args.message}")
    return EXIT_OK


def cmd_commit(args: argparse.Namespace) -> int:
    repo = _repo()
    snap = repo.commit()
    _out(f"committed transaction as {snap.id}")
    return EXIT_OK


def cmd_abort(args: argparse.Namespace) -> int:
    repo = _repo()
    repo.abort()
    _out("transaction aborted; touched files rolled back")
    return EXIT_OK


def cmd_snapshot(args: argparse.Namespace) -> int:
    repo = _repo()
    snap = repo.snapshot(args.message)
    _out(f"created snapshot {snap.id}")
    return EXIT_OK


def cmd_log(args: argparse.Namespace) -> int:
    repo = _repo()
    snaps = repo.snapshots.list()
    if not snaps:
        _out("no snapshots yet")
        return EXIT_OK
    for snap in reversed(snaps):
        _out(f"{snap.created_at}  {snap.id}  {snap.message}")
    return EXIT_OK


def cmd_timeline(args: argparse.Namespace) -> int:
    repo = _repo()
    rel = _relpath(repo, args.file)
    mf = repo.index.get(rel)
    file_id = mf.file_id
    _out(rel)
    _out("")
    last_hash: str | None = None
    for snap in repo.snapshots.list():
        match = next((m for m in snap.root.values() if m.file_id == file_id), None)
        if match is None:
            continue
        marker = "" if match.content_hash != last_hash else "  (unchanged)"
        rename = f"  [as {match.path}]" if match.path != rel else ""
        _out(f"{snap.created_at}  {snap.id}  {snap.message}{rename}{marker}")
        last_hash = match.content_hash
    return EXIT_OK


def cmd_cat(args: argparse.Namespace) -> int:
    repo = _repo()
    rel = _relpath(repo, args.file)
    snap = repo.snapshots.load(repo.snapshots.resolve(args.snapshot))
    match = snap.root.get(rel) or next(
        (m for m in snap.root.values() if m.path == rel), None
    )
    if match is None:
        raise ShadowError(f"{rel} not present in snapshot {snap.id}")
    sys.stdout.buffer.write(repo.store.read(match.content_hash))
    return EXIT_OK


def cmd_diff(args: argparse.Namespace) -> int:
    repo = _repo()
    rel = _relpath(repo, args.file)
    if args.against_index:
        old = repo.current_content(rel)
        target = repo.layout.root / rel
        new = target.read_bytes() if target.exists() else b""
        text = diffmod.unified(old, new, old_label=f"{rel} (index)", new_label=f"{rel} (working)")
    else:
        if not (args.from_snapshot and args.to_snapshot):
            raise ShadowError("diff needs either --against-index or both --from and --to")
        old = _snapshot_blob(repo, args.from_snapshot, rel)
        new = _snapshot_blob(repo, args.to_snapshot, rel)
        text = diffmod.unified(
            old, new, old_label=f"{rel}@{args.from_snapshot}", new_label=f"{rel}@{args.to_snapshot}"
        )
    sys.stdout.write(text)
    if text and not text.endswith("\n"):
        _out()
    return EXIT_OK


def _snapshot_blob(repo: ShadowRepository, selector: str, rel: str) -> bytes:
    snap = repo.snapshots.load(repo.snapshots.resolve(selector))
    match = snap.root.get(rel)
    if match is None:
        raise ShadowError(f"{rel} not present in snapshot {snap.id}")
    return repo.store.read(match.content_hash)


def cmd_restore(args: argparse.Namespace) -> int:
    repo = _repo()
    rel = _relpath(repo, args.file) if args.file else None
    snap = restoremod.restore(repo, args.snapshot, rel)
    what = "whole tree" if rel is None else rel
    _out(f"restored {what} from {args.snapshot} (new snapshot {snap.id})")
    return EXIT_OK


def cmd_verify(args: argparse.Namespace) -> int:
    repo = _repo()
    rel = _relpath(repo, args.file)
    repo.verify(rel)
    _out(f"{rel}: projection intact")
    return EXIT_OK


def cmd_repair(args: argparse.Namespace) -> int:
    repo = _repo()
    rel = _relpath(repo, args.file)
    repo.repair(rel)
    _out(f"{rel}: external change discarded; projection restored from canonical state")
    return EXIT_OK


def cmd_absorb(args: argparse.Namespace) -> int:
    repo = _repo()
    rel = _relpath(repo, args.file)
    changed = repo.absorb(rel, args.message)
    _out(f"{'absorbed external change into' if changed else 'nothing to absorb for'} {rel}")
    return EXIT_OK


def cmd_protect(args: argparse.Namespace) -> int:
    repo = _repo()
    rel = _relpath(repo, args.file)
    target = repo.layout.root / rel
    protection.make_readonly(target)
    if args.strict:
        protection.set_immutable(target)
        _out(f"{rel}: strict protection enabled (chattr +i)")
    else:
        _out(f"{rel}: read-only (0444) reasserted")
    return EXIT_OK


def cmd_unprotect(args: argparse.Namespace) -> int:
    repo = _repo()
    rel = _relpath(repo, args.file)
    target = repo.layout.root / rel
    if args.strict:
        protection.clear_immutable(target)
        _out(f"{rel}: strict protection cleared (chattr -i); still 0444 + hash-verified")
    else:
        _out(f"{rel}: managed files stay 0444 + hash-verified; use `eject` to release fully")
    return EXIT_OK


def cmd_fsck(args: argparse.Namespace) -> int:
    repo = _repo()
    report = fsckmod.check(repo, repair_journal=not args.no_repair)
    for path in report.drift:
        _out(f"DRIFT     {path} (modified outside ShadowMD)")
    for path in report.missing_files:
        _out(f"MISSING   {path} (tracked but absent)")
    for h in report.missing_blobs:
        _out(f"NO-BLOB   {h}")
    for seq in report.rolled_forward:
        _out(f"RECOVERED seq {seq} rolled forward")
    for seq in report.rolled_back:
        _out(f"RECOVERED seq {seq} rolled back")
    for seq in report.unresolved:
        _out(f"UNRESOLVED seq {seq} (needs manual review)")
    _out("fsck: OK" if report.ok else "fsck: problems found")
    return EXIT_OK if report.ok else EXIT_ERROR


def cmd_gc(args: argparse.Namespace) -> int:
    repo = _repo()
    result = gcmod.collect(repo, dry_run=args.dry_run)
    verb = "would remove" if args.dry_run else "removed"
    _out(
        f"reachable blobs: {result.reachable}; "
        f"{verb} {result.removed_count} orphan(s); kept {result.kept}"
    )
    return EXIT_OK


def cmd_unlock(args: argparse.Namespace) -> int:
    repo = _repo()
    if not args.stale:
        raise ShadowError("unlock currently supports only --stale")
    cleared = repo.locks.clear_stale()
    _out(f"cleared {len(cleared)} stale lock(s): {', '.join(cleared) if cleared else '(none)'}")
    return EXIT_OK


# --- parser --------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="shadowmd", description=__doc__.split("\n")[0])
    p.add_argument("--version", action="version", version=f"shadowmd {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def add(
        name: str,
        handler: Callable[[argparse.Namespace], int],
        help_: str,
    ) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(func=handler)
        return sp

    sp = add("init", cmd_init, "initialize a repository")
    sp.add_argument("path", nargs="?", default=".")

    add("status", cmd_status, "show repository and per-file status")

    sp = add("inject", cmd_inject, "place files under ShadowMD control")
    sp.add_argument("files", nargs="+")

    sp = add("eject", cmd_eject, "release a file (history retained)")
    sp.add_argument("file")

    sp = add("edit", cmd_edit, "edit a file via $EDITOR through the write path")
    sp.add_argument("file")
    sp.add_argument("-m", "--message", default=None)

    sp = add("append", cmd_append, "append text to a file")
    sp.add_argument("file")
    sp.add_argument("text")
    sp.add_argument("-m", "--message", default=None)

    sp = add("prepend", cmd_prepend, "prepend text to a file")
    sp.add_argument("file")
    sp.add_argument("text")
    sp.add_argument("-m", "--message", default=None)

    sp = add("replace", cmd_replace, "replace a file's content from another file")
    sp.add_argument("file")
    sp.add_argument("--content-file", dest="content_file", required=True)
    sp.add_argument("-m", "--message", default=None)

    sp = add("apply", cmd_apply, "apply a unified diff to a file")
    sp.add_argument("file")
    sp.add_argument("patch")
    sp.add_argument("-m", "--message", default=None)

    sp = add("mv", cmd_mv, "rename/move a managed file")
    sp.add_argument("old")
    sp.add_argument("new")

    sp = add("rm", cmd_rm, "remove a file from the working tree (history retained)")
    sp.add_argument("file")

    sp = add("begin", cmd_begin, "open a transaction group")
    sp.add_argument("-m", "--message", required=True)
    add("commit", cmd_commit, "commit the open transaction as one snapshot")
    add("abort", cmd_abort, "abort the open transaction, rolling files back")

    sp = add("snapshot", cmd_snapshot, "create a snapshot")
    sp.add_argument("-m", "--message", required=True)

    add("log", cmd_log, "list snapshots newest-first")

    sp = add("timeline", cmd_timeline, "show a single file's history")
    sp.add_argument("file")

    sp = add("cat", cmd_cat, "print a file's content from a snapshot")
    sp.add_argument("file")
    sp.add_argument("--snapshot", required=True)

    sp = add("diff", cmd_diff, "unified diff (against index or between snapshots)")
    sp.add_argument("file")
    sp.add_argument("--from", dest="from_snapshot", default=None)
    sp.add_argument("--to", dest="to_snapshot", default=None)
    sp.add_argument("--against-index", dest="against_index", action="store_true")

    sp = add("restore", cmd_restore, "restore a file or the whole tree from a snapshot")
    sp.add_argument("file", nargs="?", default=None)
    sp.add_argument("--snapshot", required=True)

    sp = add("verify-projection", cmd_verify, "check a file against its index hash")
    sp.add_argument("file")

    sp = add("repair", cmd_repair, "discard external change, restore projection")
    sp.add_argument("file")
    sp.add_argument("--restore-projection", action="store_true",
                    help="confirm discarding the external change")

    sp = add("absorb", cmd_absorb, "accept an external change into history")
    sp.add_argument("file")
    sp.add_argument("-m", "--message", required=True)

    sp = add("protect", cmd_protect, "reassert read-only / enable strict mode")
    sp.add_argument("file")
    sp.add_argument("--strict", action="store_true")

    sp = add("unprotect", cmd_unprotect, "clear strict mode")
    sp.add_argument("file")
    sp.add_argument("--strict", action="store_true")

    sp = add("fsck", cmd_fsck, "verify integrity and recover the journal")
    sp.add_argument("--no-repair", action="store_true", help="report only; do not recover")

    sp = add("gc", cmd_gc, "reclaim unreachable blobs")
    sp.add_argument("--dry-run", action="store_true")

    sp = add("unlock", cmd_unlock, "clear stale locks")
    sp.add_argument("--stale", action="store_true")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ProjectionViolation as exc:
        _err(str(exc))
        _err("\nResolve with: `shadowmd repair FILE --restore-projection` (discard) "
             "or `shadowmd absorb FILE -m MSG` (keep).")
        return EXIT_VIOLATION
    except ShadowError as exc:
        _err(f"error: {exc}")
        return EXIT_ERROR
    except BrokenPipeError:  # pragma: no cover - e.g. piping `cat` into `head`
        return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
