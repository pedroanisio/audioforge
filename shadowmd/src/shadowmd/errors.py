"""Typed errors for the ShadowMD library.

Libraries raise typed errors; the CLI (``cli.py``) is the only layer that
turns them into exit codes and human messages. See CLAUDE.md "Code Quality".
"""

from __future__ import annotations


class ShadowError(Exception):
    """Base class for all ShadowMD errors."""


class RepositoryNotFound(ShadowError):
    """No ``.shadowmd`` control directory was found at or above a path."""


class RepositoryExists(ShadowError):
    """``shadowmd init`` was run inside an already-initialized repository."""


class FileNotTracked(ShadowError):
    """An operation targeted a file that is not under ShadowMD control."""


class FileAlreadyTracked(ShadowError):
    """``inject`` targeted a file that is already under ShadowMD control."""


class ProjectionViolation(ShadowError):
    """The visible file's hash does not match the index (external write).

    Carries the offending path and both hashes so the CLI can render the
    integrity-violation report from §11 without re-hashing.
    """

    def __init__(self, path: str, expected: str, actual: str) -> None:
        self.path = path
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Integrity violation: {path} was modified outside ShadowMD.\n"
            f"  Expected: {expected}\n"
            f"  Actual:   {actual}"
        )


class LockError(ShadowError):
    """A repo or file lock could not be acquired (held by another operation)."""


class SnapshotNotFound(ShadowError):
    """A snapshot id (or ``--snapshot`` selector) did not resolve."""


class TransactionError(ShadowError):
    """An invalid transaction transition (e.g. ``commit`` with no ``begin``)."""
