"""Version contract for public AudioForge runtime surfaces."""
from __future__ import annotations

ENGINE_VERSION = "2.15.0"
DSL_VERSION = "1.8"
VERSION_SOURCE = "audioforge.version"


def version_contract() -> dict[str, str]:
    """Return the runtime version fields exposed to docs, CLI, and agents."""
    return {
        "engine_version": ENGINE_VERSION,
        "dsl_version": DSL_VERSION,
        "source": VERSION_SOURCE,
    }


def version_banner() -> str:
    """Return the canonical CLI-facing version banner."""
    return f"audioforge engine {ENGINE_VERSION} dsl {DSL_VERSION}"
