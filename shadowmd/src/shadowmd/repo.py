"""Repository discovery, initialization and operation orchestration.

``ShadowRepository`` owns the sub-objects (store, index, journal, locks,
snapshots) and exposes every high-level operation. Two locking rules are
enforced here, not in the callers:

* The repo lock is **reentrant within a process** (a depth counter) but still
  mutually exclusive **across processes** via ``O_EXCL``. This lets a mutation
  serialize its index write under the repo lock while restore (which already
  holds the repo lock) drives mutations without self-deadlock.
* Lock order is always repo-before-file. Nothing ever takes the repo lock while
  holding a file lock.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from . import protection
from .atomicio import OWNER_RW_MODE, atomic_write_bytes
from .config import Config
from .errors import (
    FileAlreadyTracked,
    RepositoryExists,
    RepositoryNotFound,
    ShadowError,
    TransactionError,
)
from .hashing import hash_bytes
from .ids import iso_now, new_file_id
from .index import Index
from .journal import Journal
from .jsonio import dumps, load_file
from .layout import CONTROL_DIRNAME, Layout
from .locks import LockManager
from .models import ManagedFile, Snapshot
from .mutation import mutate_file
from .projection import (
    verify_projection,
    write_projection_atomically,
)
from .snapshot import DEFAULT_BRANCH, SnapshotManager
from .store import BlobStore


class ShadowRepository:
    def __init__(self, root: Path) -> None:
        self.layout = Layout(root)
        self.config = Config.load(self.layout)
        self.store = BlobStore(self.layout)
        self.index = Index.load(self.layout)
        self.journal = Journal(self.layout)
        self.locks = LockManager(self.layout, self.config.lock_staleness_seconds)
        self.snapshots = SnapshotManager(self.layout)
        self._lock_depth = 0
        self._repo_lock_cm: Any = None
        self._suppress_depth = 0

    # --- discovery / init ------------------------------------------------
    @classmethod
    def discover(cls, start: Path | None = None) -> ShadowRepository:
        here = Path(start or Path.cwd()).resolve()
        for candidate in [here, *here.parents]:
            if (candidate / CONTROL_DIRNAME).is_dir():
                return cls(candidate)
        raise RepositoryNotFound(
            f"no {CONTROL_DIRNAME} directory found at or above {here}"
        )

    @classmethod
    def init(cls, root: Path) -> ShadowRepository:
        root = Path(root).resolve()
        layout = Layout(root)
        if layout.control.exists():
            raise RepositoryExists(f"{layout.control} already exists")
        for directory in layout.all_dirs():
            directory.mkdir(parents=True, exist_ok=True)
        cls._verify_same_filesystem(layout)
        Config().save(layout)
        Index().write_atomically(layout)
        # Establish the default branch ref namespace; HEAD is materialized on
        # the first snapshot.
        atomic_write_bytes(
            layout.head,
            f"ref: refs/{DEFAULT_BRANCH}\n".encode(),
            tmp_dir=layout.tmp,
            mode=OWNER_RW_MODE,
        )
        return cls(root)

    @staticmethod
    def _verify_same_filesystem(layout: Layout) -> None:
        """tmp/ must share a filesystem with the working tree or os.replace
        raises EXDEV and atomicity is lost (§4.8, §9.3)."""
        try:
            if os.stat(layout.tmp).st_dev != os.stat(layout.root).st_dev:
                raise ShadowError(
                    f"{layout.tmp} is on a different filesystem than {layout.root}; "
                    "atomic projection updates require them to share one filesystem"
                )
        except FileNotFoundError:  # pragma: no cover - dirs just created
            pass

    # --- reentrant repo lock --------------------------------------------
    @contextmanager
    def repo_locked(self) -> Iterator[None]:
        if self._lock_depth == 0:
            cm = self.locks.repo_lock()
            cm.__enter__()
            self._repo_lock_cm = cm
        self._lock_depth += 1
        try:
            yield
        finally:
            self._lock_depth -= 1
            if self._lock_depth == 0 and self._repo_lock_cm is not None:
                self._repo_lock_cm.__exit__(None, None, None)
                self._repo_lock_cm = None

    # --- transaction state ----------------------------------------------
    @property
    def in_transaction(self) -> bool:
        return self._suppress_depth > 0 or self.layout.txn.exists()

    @contextmanager
    def suppress_autosnapshot(self) -> Iterator[None]:
        self._suppress_depth += 1
        try:
            yield
        finally:
            self._suppress_depth -= 1

    def txn_record_touch(self, path: str, old_hash: str) -> None:
        """Record the pre-image of a file the first time a transaction touches
        it, so ``abort`` can roll back (§10.1)."""
        if not self.layout.txn.exists():
            return
        data = load_file(self.layout.txn)
        touched: dict[str, str] = data.setdefault("touched", {})
        touched.setdefault(path, old_hash)
        atomic_write_bytes(
            self.layout.txn, dumps(data), tmp_dir=self.layout.tmp, mode=OWNER_RW_MODE
        )

    # --- snapshots -------------------------------------------------------
    def snapshot(self, message: str) -> Snapshot:
        with self.repo_locked():
            return self._snapshot_locked(message)

    def _snapshot_locked(self, message: str) -> Snapshot:
        snap = self.snapshots.create(self.index, message)
        self.index.write_atomically(self.layout)
        return snap

    # --- the primitive ---------------------------------------------------
    def mutate_file(
        self, path: str, new_content: bytes, message: str, *, operation: str = "mutate"
    ) -> bool:
        with self.repo_locked():
            return mutate_file(self, path, new_content, message, operation=operation)

    def current_content(self, path: str) -> bytes:
        """The canonical bytes of a tracked file (read from the blob store)."""
        return self.store.read(self.index.get(path).content_hash)

    # --- injection / ejection -------------------------------------------
    def inject(self, relpath: str) -> ManagedFile:
        with self.repo_locked():
            target = self.layout.root / relpath
            if not target.is_file():
                raise ShadowError(f"cannot inject {relpath}: not a file")
            if relpath in self.index:
                raise FileAlreadyTracked(f"{relpath} is already tracked")

            content = target.read_bytes()
            original_mode = protection.current_mode(target)
            content_hash = self.store.store(content)
            mf = ManagedFile(
                file_id=new_file_id(),
                path=relpath,
                content_hash=content_hash,
                size=len(content),
                readonly=True,
                original_mode=original_mode,
            )
            entry = self.journal.intent(
                operation="inject",
                path=relpath,
                old_hash=None,
                new_hash=content_hash,
                message="inject",
            )
            self.index.add(mf)
            self.index.write_atomically(self.layout)
            protection.make_readonly(target)  # Layer 1 (§3.1)
            self.journal.commit(entry)

            if self.config.auto_snapshot and not self.in_transaction:
                self._snapshot_locked("inject " + relpath)
            return self.index.get(relpath)

    def inject_many(self, relpaths: list[str]) -> list[ManagedFile]:
        """Inject several files under a single snapshot."""
        with self.repo_locked(), self.suppress_autosnapshot():
            injected = [self.inject(p) for p in relpaths]
        if injected and self.config.auto_snapshot and not self.in_transaction:
            self.snapshot(f"inject {len(injected)} file(s)")
        return injected

    def eject(self, relpath: str) -> None:
        with self.repo_locked():
            mf = self.index.get(relpath)
            target = self.layout.root / relpath
            restore_mode = mf.original_mode if mf.original_mode is not None else OWNER_RW_MODE
            if target.exists():
                protection.make_writable_by_owner(target, restore_mode)
            entry = self.journal.intent(
                operation="eject",
                path=relpath,
                old_hash=mf.content_hash,
                new_hash=None,
                message="eject",
            )
            self.index.remove(relpath)
            self.index.write_atomically(self.layout)
            self.journal.commit(entry)
            # Blobs and existing snapshots are retained (§7.1). No gc here.

    # --- structural mutations -------------------------------------------
    def move(self, old: str, new: str) -> None:
        with self.repo_locked():
            mf = self.index.get(old)
            verify_projection(self.layout, mf)
            if new in self.index:
                raise FileAlreadyTracked(f"{new} is already tracked")
            new_target = self.layout.root / new
            if new_target.exists():
                raise ShadowError(f"cannot move onto existing file {new}")

            content = self.store.read(mf.content_hash)
            entry = self.journal.intent(
                operation="rename",
                path=old,
                old_hash=mf.content_hash,
                new_hash=mf.content_hash,
                message=f"rename {old} -> {new}",
                extra={"from": old, "to": new},
            )
            write_projection_atomically(self.layout, new, content)
            old_target = self.layout.root / old
            self._unlink_projection(old_target)
            self.index.rename(old, new)
            self.index.write_atomically(self.layout)
            self.journal.commit(entry)

            if self.config.auto_snapshot and not self.in_transaction:
                self._snapshot_locked(f"rename {old} -> {new}")

    def remove(self, relpath: str) -> None:
        with self.repo_locked():
            mf = self.index.get(relpath)
            verify_projection(self.layout, mf)
            entry = self.journal.intent(
                operation="rm",
                path=relpath,
                old_hash=mf.content_hash,
                new_hash=None,
                message="rm",
            )
            self._unlink_projection(self.layout.root / relpath)
            self.index.remove(relpath)
            self.index.write_atomically(self.layout)
            self.journal.commit(entry)

            if self.config.auto_snapshot and not self.in_transaction:
                self._snapshot_locked(f"rm {relpath}")

    @staticmethod
    def _unlink_projection(target: Path) -> None:
        if target.exists():
            try:
                target.chmod(OWNER_RW_MODE)
            except OSError:
                pass
            target.unlink()

    # --- content sugar (all over the single primitive) -------------------
    def append(self, relpath: str, text: str, message: str | None = None) -> bool:
        old = self.current_content(relpath)
        if old and not old.endswith(b"\n"):
            old += b"\n"
        new = old + text.encode("utf-8")
        if not new.endswith(b"\n"):
            new += b"\n"
        return self.mutate_file(relpath, new, message or f"append to {relpath}")

    def prepend(self, relpath: str, text: str, message: str | None = None) -> bool:
        block = text.encode("utf-8")
        if not block.endswith(b"\n"):
            block += b"\n"
        new = block + self.current_content(relpath)
        return self.mutate_file(relpath, new, message or f"prepend to {relpath}")

    def replace(self, relpath: str, new_content: bytes, message: str | None = None) -> bool:
        return self.mutate_file(relpath, new_content, message or f"replace {relpath}")

    # --- integrity: verify / repair / absorb ----------------------------
    def verify(self, relpath: str) -> None:
        verify_projection(self.layout, self.index.get(relpath))

    def repair(self, relpath: str) -> None:
        """Discard an external change by rewriting the canonical projection."""
        with self.repo_locked():
            mf = self.index.get(relpath)
            content = self.store.read(mf.content_hash)
            write_projection_atomically(self.layout, relpath, content)
            self.journal.marker("repair", message=f"restored projection of {relpath}")

    def absorb(self, relpath: str, message: str) -> bool:
        """Accept an external change into history (§11.2). Never silent."""
        with self.repo_locked():
            mf = self.index.get(relpath)
            target = self.layout.root / relpath
            if not target.exists():
                raise ShadowError(f"cannot absorb {relpath}: file is missing")
            new_content = target.read_bytes()
            new_hash = hash_bytes(new_content)
            if new_hash == mf.content_hash:
                return False  # nothing actually drifted
            self.store.store(new_content)
            entry = self.journal.intent(
                operation="absorb",  # distinguishable forever from CLI mutations
                path=relpath,
                old_hash=mf.content_hash,
                new_hash=new_hash,
                message=message,
            )
            self.index.update_content(relpath, content_hash=new_hash, size=len(new_content))
            self.index.write_atomically(self.layout)
            protection.make_readonly(target)  # re-assert read-only
            self.journal.commit(entry)
            if self.config.auto_snapshot and not self.in_transaction:
                self._snapshot_locked(message)
            return True

    # --- transactions (begin / commit / abort) --------------------------
    def begin(self, message: str) -> None:
        if self.layout.txn.exists():
            raise TransactionError("a transaction is already open")
        atomic_write_bytes(
            self.layout.txn,
            dumps({"message": message, "started_at": iso_now(), "touched": {}}),
            tmp_dir=self.layout.tmp,
            mode=OWNER_RW_MODE,
        )
        self.journal.marker("txn-begin", message=message)

    def commit(self) -> Snapshot:
        if not self.layout.txn.exists():
            raise TransactionError("no open transaction to commit")
        data = load_file(self.layout.txn)
        message = data.get("message", "transaction")
        with self.repo_locked():
            self._clear_txn()
            snap = self._snapshot_locked(message)
        self.journal.marker("txn-commit", message=message)
        return snap

    def abort(self) -> None:
        if not self.layout.txn.exists():
            raise TransactionError("no open transaction to abort")
        data = load_file(self.layout.txn)
        touched: dict[str, str] = data.get("touched", {})
        with self.repo_locked():
            # Clear the marker first so the rollback mutations are not themselves
            # recorded as transaction touches.
            self._clear_txn()
            for path, pre_hash in touched.items():
                if path not in self.index:
                    continue
                content = self.store.read(pre_hash)
                with self.suppress_autosnapshot():
                    mutate_file(self, path, content, f"abort: restore {path}", operation="abort")
        self.journal.marker("txn-abort", message=data.get("message", ""))

    def _clear_txn(self) -> None:
        try:
            self.layout.txn.unlink()
        except FileNotFoundError:
            pass
