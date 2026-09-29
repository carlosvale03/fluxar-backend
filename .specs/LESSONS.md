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
- evidence: ISOL-14 budgets/services.py:24 (services) (+1 more)
- last seen: 2026-09-27T19:26:59Z

### L-003 - State whether a rule about already-invalid persisted relations also applies to partial updates that omit the relation
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `spec` · harmful: 0
- features: isolamento-entre-usuarios
- evidence: spec.md edge case 6 (ISOL-02, ISOL-17) (spec)
- last seen: 2026-09-27T19:01:03Z

### L-004 - When an edge case cites a rule owned by another spec, either assert its observable outcome or mark it explicitly as deferred
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `spec` · harmful: 0
- features: isolamento-entre-usuarios
- evidence: spec.md edge case 5 (IMPORT-21) (spec) (+2 more)
- last seen: 2026-09-27T19:55:27Z

### L-005 - Define the expected response per endpoint kind when one rule covers both list filters and single-resource reports
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `spec` · harmful: 0
- features: isolamento-entre-usuarios
- evidence: ISOL-13 tests/isolamento/test_relatorios.py:46 (spec) (+2 more)
- last seen: 2026-09-27T19:55:27Z

### L-006 - Include server-set relations in cross-owner data corrections even when the API never accepts them as input
- signal: `spec_deviation` · recurrence: 1 feature(s) · scope: `data-migration` · harmful: 0
- features: isolamento-entre-usuarios
- evidence: SPEC_DEVIATION core/isolation.py:28 (data-migration)
- last seen: 2026-09-27T19:01:03Z

### L-007 - Test each defensive fallback branch with the specific input it exists to block, not only with an ordinary valid object
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: isolamento-entre-usuarios
- evidence: M13 core/fields.py:42 (test_campo.py:96) (tests)
- last seen: 2026-09-27T19:26:59Z

### L-008 - State whether server-side operations that copy or batch-update already-linked records must re-check the ownership of the relations they carry
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `spec` · harmful: 0
- features: isolamento-entre-usuarios
- evidence: spec-precision gap 3: accounts/services.py:132, transactions/serializers.py:291, budgets/views.py:100 (spec) (+2 more)
- last seen: 2026-09-27T20:27:25Z

### L-009 - When auditing owner isolation, include reports and exports that render related-object names through the user's own records, not only serializers
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `reports-exports` · harmful: 0
- features: isolamento-entre-usuarios
- evidence: ISOL-15 reports/services.py:396, data_exchange/services.py:524 (sonda S1, rodada 3) (reports-exports) (+1 more)
- last seen: 2026-09-27T20:27:24Z

### L-010 - Forge cross-owner fixtures with every relation pointing at the victim's objects so an owner filter cannot be swapped for a relation filter unnoticed
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: isolamento-entre-usuarios
- evidence: N03 accounts/services.py:135 (test_pagamento_fatura.py:27) (tests) (+1 more)
- last seen: 2026-09-27T20:27:25Z

### L-011 - When code adds a SPEC_DEVIATION, pin its full documented response (status, code and side effects) in the test, not only the absence of the forbidden outcome
- signal: `spec_deviation` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: autenticacao
- evidence: SPEC_DEVIATION api/views.py:151; tests/autenticacao/test_verificacao.py:61 (tests)
- last seen: 2026-09-28T21:22:00Z

## Quarantined (failed when applied - ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_
