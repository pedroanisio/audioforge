---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 via Claude Code"
  date: "2026-06-12"
---

# Disclaimer

ShadowMD makes guarantees about **immutability**, **atomicity**, and
**read-only projection** that rest on platform-specific behaviour. Those
guarantees are only as strong as the primary sources and the filesystem they
run on.

## Verified assumptions and their sources

- **`os.replace()` is atomic for same-filesystem renames.**
  POSIX `rename()` is specified to be atomic; Python's `os.replace` maps onto
  it. Cross-device renames raise `EXDEV` and are *not* atomic — which is why
  the staging directory `.shadowmd/tmp/` is required to live on the same
  filesystem as the working tree, and `shadowmd init` verifies this.
  - POSIX `rename()`: <https://pubs.opengroup.org/onlinepubs/9699919799/functions/rename.html>
  - Python `os.replace`: <https://docs.python.org/3/library/os.html#os.replace>

- **`chmod 0444` is advisory, not enforcement.** A file owner can restore
  write permission, and a writable parent directory permits delete-and-recreate
  regardless of the file's own mode. ShadowMD therefore treats permission bits
  as accident protection and relies on **projection-hash verification** as the
  authoritative guarantee. See the Enforcement Model section of the design doc.

- **`chattr +i` (strict mode) is Linux- and filesystem-specific** and requires
  `CAP_LINUX_IMMUTABLE`. It is opt-in, never the default, and ShadowMD verifies
  privilege and filesystem support before claiming success.
  - <https://man7.org/linux/man-pages/man1/chattr.1.html>

- **Windows differs:** `os.replace()` onto a read-only target fails on Windows
  (it succeeds on POSIX), so the read-only attribute is cleared on the target
  immediately before the replace. `chattr` does not exist on Windows.

## Epistemic commitment

> No statement or premise not backed by a real logical definition or verifiable
> reference should be taken for granted.

Where this software's behaviour depends on an unverified platform claim, that
claim is flagged in code comments and must be tested on the target system
before being relied upon. "I cannot verify this" is an acceptable answer;
a plausible-but-unverified guarantee is not.
