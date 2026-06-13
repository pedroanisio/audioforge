"""Apply a unified diff to in-memory content (for ``shadowmd apply``).

``difflib`` produces unified diffs but does not apply them, and shelling out to
``patch``/``git apply`` would add a non-deterministic external dependency the
design explicitly avoids. This is a small, strict applier: it honours the hunk
headers, verifies every context and removed line against the source, and raises
``PatchError`` on any mismatch rather than guessing — corrupting a managed file
silently would violate PALS's Law.
"""

from __future__ import annotations

import re

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class PatchError(ValueError):
    """The patch did not apply cleanly against the given source."""


def _splitlines(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def apply_unified(original: bytes, patch: bytes) -> bytes:
    try:
        src_text = original.decode("utf-8")
        patch_text = patch.decode("utf-8")
    except UnicodeDecodeError as exc:  # pragma: no cover - defensive
        raise PatchError(f"apply requires UTF-8 text: {exc}") from exc

    src = _splitlines(src_text)
    patch_lines = patch_text.splitlines(keepends=True)

    result: list[str] = []
    src_idx = 0  # 0-based cursor into src
    i = 0
    n = len(patch_lines)
    saw_hunk = False

    while i < n:
        raw = patch_lines[i]
        line = raw.rstrip("\n")

        # Skip file headers and any preamble before the first hunk.
        if line.startswith(("--- ", "+++ ", "diff ", "index ")):
            i += 1
            continue

        m = _HUNK_RE.match(line)
        if not m:
            i += 1
            continue

        saw_hunk = True
        old_start = int(m.group(1))
        hunk_src = max(old_start - 1, 0)  # 0-based; unified uses 1-based, 0 for empty file

        if hunk_src < src_idx:
            raise PatchError(f"overlapping or out-of-order hunk at line {old_start}")
        # Copy untouched source up to the hunk.
        result.extend(src[src_idx:hunk_src])
        src_idx = hunk_src

        i += 1
        while i < n:
            hline = patch_lines[i]
            tag = hline[:1]
            body = hline[1:]
            if tag == "@" and hline.startswith("@@"):
                break  # next hunk
            if tag == "\\":  # "\ No newline at end of file"
                i += 1
                continue
            if tag in (" ", ""):
                if src_idx >= len(src) or src[src_idx] != body:
                    raise PatchError(
                        f"context mismatch near source line {src_idx + 1}"
                    )
                result.append(src[src_idx])
                src_idx += 1
            elif tag == "-":
                if src_idx >= len(src) or src[src_idx] != body:
                    raise PatchError(
                        f"deleted line does not match source at line {src_idx + 1}"
                    )
                src_idx += 1
            elif tag == "+":
                result.append(body)
            else:
                raise PatchError(f"unexpected patch line: {hline!r}")
            i += 1

    if not saw_hunk:
        raise PatchError("no @@ hunk header found in patch")

    result.extend(src[src_idx:])
    return "".join(result).encode("utf-8")
