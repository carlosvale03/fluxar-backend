# LESSONS - auto-maintained by scripts/lessons.py

> Machine-owned. Do NOT hand-edit. Changes are overwritten on the next `lessons.py` write.
> Canonical state lives in `.specs/lessons.json`. Edit lessons only via the script.
> promote_threshold=2 distinct features · window_days=45 · quarantine_threshold=2

## Confirmed (load these at Specify/Design)

Corroborated across multiple features. Safe to apply as guidance.

_none_

## Candidates (under observation - do NOT load as guidance yet)

Seen once or not yet corroborated. Tracked, not trusted.

### L-001 - When auditing owner isolation, check every serializer that nests a related object for display, not only the writable relations
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `serializers` · harmful: 0
- features: isolamento-entre-usuarios
- evidence: ISOL-15 budgets/serializers.py:13 (serializers)
- last seen: 2026-09-27T19:01:02Z

### L-002 - Filter reverse-relation traversals such as subcategories by the owner of the starting object in every service that sums them
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `services` · harmful: 0
- features: isolamento-entre-usuarios
- evidence: ISOL-14 budgets/services.py:24 (services)
- last seen: 2026-09-27T19:01:02Z

### L-003 - State whether a rule about already-invalid persisted relations also applies to partial updates that omit the relation
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `spec` · harmful: 0
- features: isolamento-entre-usuarios
- evidence: spec.md edge case 6 (ISOL-02, ISOL-17) (spec)
- last seen: 2026-09-27T19:01:03Z

### L-004 - When an edge case cites a rule owned by another spec, either assert its observable outcome or mark it explicitly as deferred
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `spec` · harmful: 0
- features: isolamento-entre-usuarios
- evidence: spec.md edge case 5 (IMPORT-21) (spec)
- last seen: 2026-09-27T19:01:03Z

### L-005 - Define the expected response per endpoint kind when one rule covers both list filters and single-resource reports
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `spec` · harmful: 0
- features: isolamento-entre-usuarios
- evidence: ISOL-13 tests/isolamento/test_relatorios.py:46 (spec)
- last seen: 2026-09-27T19:01:03Z

### L-006 - Include server-set relations in cross-owner data corrections even when the API never accepts them as input
- signal: `spec_deviation` · recurrence: 1 feature(s) · scope: `data-migration` · harmful: 0
- features: isolamento-entre-usuarios
- evidence: SPEC_DEVIATION core/isolation.py:28 (data-migration)
- last seen: 2026-09-27T19:01:03Z

## Quarantined (failed when applied - ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_
