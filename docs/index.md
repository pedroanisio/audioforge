---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 via Claude Code; revised by Claude Opus 5.5 via Claude Code"
  date: "2026-09-28"
---

# AudioForge

**Deterministic audio-asset generation for production pipelines.** A pinned spec
and engine version reproduce audio byte-for-byte within a verified numeric
environment; the golden and `verify` oracles check that rather than assume it
(ADR-0001, ADR-0007). Non-vocal by design: music, sound design, SFX, ambience, beats, loops, jingles, transitions,
and branded sonic identities.

```
.af DSL  ──compile──▶  JSON IR (hashed ground truth)  ──render──▶  WAV + manifest
 agents                inspectable, mutable, versioned            sha256-verified
```

## Start here

- **[Composition examples](examples/index.md)** — scores, local audio, render commands and source requirements.
- **[Cues for video](CUES.md)** — prebuilt music beds, stings and sound effects, resolved
  straight into scene-render documents.

- **[The DSL](DSL_SPEC.md)** — the `.af` authoring language.
- **[IR schema](IR_SCHEMA.md)** (prose) and the generated **[IR reference](reference.md)**
  — the JSON render contract.
- **[Capabilities](capabilities.md)** and **[diagnostic codes](DIAGNOSTIC_CODES.md)**
  — the machine-readable surface an agent consumes.
- **[Agent tools](AGENT_TOOLS.md)** — the in-process facade (and the MCP server,
  `python -m audioforge.mcp`).
- **[Codebase standards](codebase-standards.md)** and the **design records** in the
  nav — how the project stays trustworthy.

The reference, capabilities, diagnostic-codes and interop pages are **generated** from
the committed contract artifacts; the whole site is a product of the source tree, not a
parallel copy.

Rendering needs Python 3.10+ and a C compiler: engine 3.2 runs its DSP through native
kernels compiled on first use. Upgrading from 3.1 changes output bits (not audibly); see
"Engine 3.2: render cost and numeric drift" in the [migration guide](MIGRATION_3.md).
