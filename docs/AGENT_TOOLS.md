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
