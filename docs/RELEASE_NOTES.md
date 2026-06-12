# AudioForge Release Notes

## Current Runtime Contract

- Engine 2.15.0
- DSL 1.8
- Version source of truth: `audioforge.version`

Migration note: DSL 1.8 is the current documented authoring contract and is
backward compatible — existing DSL 1.7 (and 1.0-compatible) assets remain valid
with no source migration required.

Determinism note: `ENGINE_VERSION` is folded into the `spec_hash` payload
(`audioforge.determinism`). Re-rendering an unchanged spec under Engine 2.15.0
therefore yields a different render hash than under 2.14.0 by design; provenance
consumers that pinned 2.14.0 hashes must re-pin against this engine.

## History

### Engine 2.15.0 · DSL 1.8

- Engine and DSL minor version bump from Engine 2.14.0 · DSL 1.7.
- Backward compatible: no `.af` source migration required.
- Render hashes recompute under the new engine version (see Determinism note).

### Engine 2.14.0 · DSL 1.7

- Version metadata alignment; DSL 1.7 documented as the authoring contract.
- DSL 1.0-compatible assets remained valid with no source migration.
