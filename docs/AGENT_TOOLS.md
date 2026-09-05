---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Claims
    require verification against the implementation and its acceptance tests.
  generated_by: "GPT-6 via Codex"
  date: "2026-09-05"
---

# AudioForge Agent Tools

The typed agent facade is `audioforge.agent_tools.run_tool(operation, request)`.
Every response has schema `audioforge.agent-tools/1` and contains:

- `ok`
- `diagnostics`
- `artifacts`
- `engine_version`
- `dsl_version`

Supported operations are `compile`, `validate`, `plan`, `render`, `analyze`,
`decompile`, `import`, `export`, and `repair`. `tool_schemas()` returns the
request/response skeletons for constrained callers.

`run_tool("plan", {"spec": spec})` returns a canonical
`audioforge.render-plan/1` artifact plus `plan_hash`. Use it before render when
an agent needs to inspect sampled routes, synthetic articulation fallbacks,
synth/native routes, routing policy effects, or stale-plan diagnostics.

The plan also lists every virtual section player and declares approximate
technique, legato and section routes. Use `routing.fallbacks: forbid` to reject
those routes. A plan proves the selected implementation path, not realism.

`validate` follows SDK resource and route validation. Loop-safe assets also render a buffer to measure seams and tails. Set request `resolve: false` for structural validation only.

Every diagnostic in the envelope carries `code` (ADR-0008): a key of
`capability_manifest()["diagnostic_codes"]` (see `docs/DIAGNOSTIC_CODES.md`) or `null`
when no registered code applies. Branch on `code`, not on `message` text; the message
keeps its human-readable `code:` prefix.

`run_tool("analyze", {"audio": samples, "sample_rate": 48000,
"context": {"stereo": "mono", "expect_bass": false}})` separates measured
observations from context-dependent recommendations. Context may instead be a
compiled spec; SDK asset analysis passes its spec automatically. Authored rests
are not missing audio. MCP exposes the same request schema and implementation.

Set `performance_seed` and `variant` explicitly to choose a take. Keep them and
layer names/event IDs stable across mix A/B comparisons. The manifest includes
both `performance_hash` and complete `spec_hash`.

Run `python -m audioforge.tools.musical_acceptance --out DIR` to render the
seven measured acceptance cases and a standalone listening-review page. Add
`--baseline-root CHECKOUT` for a comparison. The page embeds WAVs and exports
listener-entered judgments; it never invents ratings. See [migration and
review details](MIGRATION_3.md).
