# AudioForge Agent Tools

The typed agent facade is `audioforge.agent_tools.run_tool(operation, request)`.
Every response has schema `audioforge.agent-tools/1` and contains:

- `ok`
- `diagnostics`
- `artifacts`
- `engine_version`
- `dsl_version`

Supported operations are `compile`, `validate`, `render`, `analyze`,
`decompile`, `import`, `export`, and `repair`. `tool_schemas()` returns the
request/response skeletons for constrained callers.
