"""ShadowMD — a CLI-only, Nix-like immutable overlay layer for Markdown files.

The visible Markdown file becomes a read-only projection. The canonical state
lives inside ``.shadowmd``. All changes must be performed through the CLI.

The package core is content-agnostic: the blob store, snapshots, journal,
locking and projection logic operate on bytes. "Markdown" is only the default
set of tracked extensions, which makes the same machinery reusable as a general
text-overlay tool.
"""

from .errors import (
    FileAlreadyTracked,
    FileNotTracked,
    LockError,
    ProjectionViolation,
    RepositoryExists,
    RepositoryNotFound,
    ShadowError,
    SnapshotNotFound,
    TransactionError,
)
from .repo import ShadowRepository

__all__ = [
    "FileAlreadyTracked",
    "FileNotTracked",
    "LockError",
    "ProjectionViolation",
    "RepositoryExists",
    "RepositoryNotFound",
    "ShadowError",
    "ShadowRepository",
    "SnapshotNotFound",
    "TransactionError",
]

__version__ = "0.1.0"
