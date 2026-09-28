---
disclaimer:
  notice: >-
    Example behavior must be verified against the installed engine and resources.
  generated_by: "Codex; revised by Claude Opus 5.5 via Claude Code"
  date: "2026-09-28"
---

# Python integration examples

See the [repository disclaimer](../DISCLAIMER.md).

These recipes demonstrate how to integrate AudioForge into a Python workflow.
For complete compositions, DSL sources and local rendered audio, use the
[composition examples](../docs/examples/index.md).

| Recipe | Purpose |
|---|---|
| [Agent loop](agent_loop.py) | Compile, inspect, repair and render through the SDK (`AudioForge`). |
| [Integration pipeline](integration_pipeline.py) | Compose a production workflow with the SDK. |
| [Custom plugin](custom_plugin.py) | Register custom synthesis and processing behavior. |
| [Reverb comparison](reverb_ab.py) | Render alternative reverb treatments. |

Run recipes from the repository root with the project's Python environment; rendering needs a C compiler (engine 3.2+).
Read each script's module documentation for required resources and output paths.

[Back to AudioForge](../README.md)
