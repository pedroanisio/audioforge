---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 via Claude Code"
  date: "2026-07-05"
---

# AudioForge

**Deterministic audio-asset generation for production pipelines.** One schema +
one engine version = byte-identical audio, every render, forever. Non-vocal by
design: music, sound design, SFX, ambience, beats, loops, jingles, transitions,
and branded sonic identities.

```
.af DSL  ──compile──▶  JSON IR (hashed ground truth)  ──render──▶  WAV + manifest
 agents                inspectable, mutable, versioned            sha256-verified
```

## Start here

- **[The DSL](DSL_SPEC.md)** — the `.af` authoring language.
- **[IR schema](IR_SCHEMA.md)** (prose) and the generated **[IR reference](reference.md)**
  — the JSON render contract.
- **[Capabilities](capabilities.md)** and **[diagnostic codes](DIAGNOSTIC_CODES.md)**
  — the machine-readable surface an agent consumes.
- **[Agent tools](AGENT_TOOLS.md)** — the in-process facade (and the MCP server,
  `python -m audioforge.mcp`).
- **[Codebase standards](codebase-standards.md)** and the **design records** in the
  nav — how the project stays trustworthy.

The reference and capabilities pages are **generated** from the committed contract
artifacts; the whole site is a product of the source tree, not a parallel copy.
