# Synthetic census fixtures

These are tooling inputs, not protocol contracts, per-function audit plans, or
independent security oracles. They are compiled only in temporary directories.

- `Fixture.sol.txt` supplies a small credit/claim surface. `census_selftest.py`
  builds a complete synthetic plan/result around it and then mutates one
  obligation at a time. The stranded-credit mutant removes its round-trip
  obligation while preserving the conservation and double-assignment records.
- `Surface.sol.txt` exercises inherited methods/getters, modifier/helper value
  effects, constructor effects, overloaded selectors, receive/fallback,
  unresolved calls, and a pure array allocation that must not count as contract
  creation or value movement.

Positive fixtures use visibly synthetic result records. The production CLI
rejects those records; only the in-process self-test harness permits them. The
mutations cover missing/stale rows and provenance, missing sinks/obligations,
zero or mismatched action counts, invented actor authority, incorrect delivery,
missing inventory/currency vectors, burn residue, transaction separation,
suppression bindings, independent oracle attribution, and CEI/outcome separation.
