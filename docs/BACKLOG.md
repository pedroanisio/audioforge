# Backlog

## Disclaimer

This work is subject to the methodological caveats and commitments described in DISCLAIMER.md.
> No statement or premise not backed by a real logical definition or verifiable reference should be taken for granted.

Deferred work captured so it is not lost. Nothing here blocks current use unless a current task explicitly promotes it.

**System of record:** `docs/backlog.yml`, structured by `docs/schema/backlog.schema.json`. The YAML is canonical; this table is a rendered view. Effort is expressed as **complexity** (["XS","S","M","L","XL"]), never time. `Owner` records the provenance boundary so concurrent work stays attributable.

Validate the backlog:

```bash
node scripts/check-backlog-governance.mjs
```

## Items

| ID | Item | Category | Type | Status | Cx | Priority | Owner |
|----|------|----------|------|--------|----|----------|-------|
| BL-001 | Govern the backlog with schema and drift checks | docs | infra | ready | S | high | shared |

See `backlog.yml` for each item's full description, rationale, acceptance criteria, dependencies, related decisions, and references.
