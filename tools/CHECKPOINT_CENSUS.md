# Checkpoint census gate

This implements CHECKPOINT_STANDARD §5 in the existing required CI job
`build · lint · fork probes · code-absence`. `tools/code_absence.sh` invokes the
gate unconditionally and propagates its exit status; `--selftest` invokes its
synthetic acceptance/mutation tests. No workflow or branch-rule change is needed.

The gate checks whether known obligations have current, reproducible evidence.
It does **not** prove economics, callee trust, harness correctness, or that a
declared actor population exhausts the supported population. Those remain the
independent checker/SME/audit review. Names of signers and oracle authors are
reviewed attestations, not cryptographic identity verification.

## Running it

```sh
python3 tools/checkpoint_census.py --selftest
python3 tools/checkpoint_census.py
python3 tools/checkpoint_census.py --release launch
bash tools/code_absence.sh --selftest
bash tools/code_absence.sh
```

Each invocation prints its run ID. A normal invocation writes `report.json`,
`source-census.json`, and its compiler command/log in a new temporary directory.
Use `--output <new-directory> --run-id <id>` to retain them elsewhere. An optional
`--build-info <file>` reuses a compiler capture **only after validating every
input source against current bytes**. A stale capture or compiler failure fails
closed; it cannot become an empty passing denominator. No RPC/key is needed.

## Module manifest and denominator

`census_manifest.json` is the module inventory. Its `m2-checkpoint` release requires
the closed escrow and built ClassicHook group (hook, router, Incinerator, split,
interfaces). M2 remains awaiting the independent checkpoint; `built` does not
mean its evidence is complete. Future contract modules come from IG v2 chapter 2;
their source paths are provisional, updated when their own builds are authorized.
The Safe is configuration, not a custom source module. The per-launch buyback
module is absent and is excluded from M2.

Supported statuses are `planned`, `not_implemented`, `in_progress`, `built`, and
`closed`. A release names the modules it must contain. Missing source always
emits `NOT_IMPLEMENTED`, including for modules outside that release. It fails
when required by the release or declared built/closed. An interface/abstract
declaration alone is not an implementation. Unassigned production sources,
overlapping module source patterns, unknown release names, and unfinished
required modules fail.

The manifest also pins minimum inventory kinds across each built module. Escrow
requires physical/claims/mixed (`src/escrow/IFeeEscrow.sol:23-31`); the M2 group
requires claims plus the router's physical forwarding
(`src/hook/AttributionRouter.sol:93-106`). These cannot disappear merely because
an edge author omitted an inventory. Each edge's declared kinds must then have
actual witnesses under its paired obligation.

The compiler AST/ABI supplies selectors, overrides, public getters, constructors,
receive/fallback, inherited methods, modifier/helper call effects, and source
hashes. All own function/modifier definitions are enumerated. Required rows cover
public/external methods, getters, constructors, state-changing/value-moving
internal functions, and production library functions (including pure fee math).
Pure/view internal helpers and modifier definitions remain visible; their effects
are checked through caller rows without demanding separate administrative boilerplate.
Inherited value-moving definitions are included; library calls are followed and recorded
on their callers, and production libraries have their own rows. Interface
declarations require a concrete implementation in the same module; its row
covers the implementation, while the interface still needs a provenance row.

Calls through interface declarations and low-level/assembly/indirect calls remain
`UNKNOWN` until explicitly reviewed. Operation names and call effects produce
conservative `value_candidates`; they do not infer beneficiary identity or
economic intent. Each candidate must be mapped to a checker-authored value edge.
One function may have multiple edges (e.g. escrow credit and Incinerator burn).
Every edge needs its corresponding round-trip/conservation obligation. Value
functions also require conservation and double-assignment fuzz/invariant
obligations: these are the hard outcome checks behind advisory CEI observations.

## Checker documents and source currency

The parser accepts the two labelled-section matrices and the Markdown table
committed by Claude at `ab2689c`, as well as JSON. It expands grouped signatures
to compiler IDs, validates supplied selectors, and resolves nominal type names
against the compiler's source signatures. A bare name or `(...)` shorthand is
accepted only when unique in the named contract and bound to reviewed source.
Overloads require an unambiguous signature/selector. Explanatory inline code in
a table cell is not a function. Missing columns, duplicate rows, unknown
functions, and unfinished cells remain failures; prose `PASS` never generates
an evidence record.

All nine matrix columns are required. `intent + source` additionally needs an
explicit `novel — no prior audit`, `audit[<catalog-id>]`, or `prior-audit:` citation
with a report link/path. A DR or Pons source citation alone is not a prior audit.
An `audit_citations` dictionary resolves catalog IDs to report citations.

Machine details may be appended to the **checker-owned** Markdown document in a
fenced `checkpoint-census` JSON block. Unknown optional fields are retained.
JSON documents use the same keys; `functions`/`rows` hold matrix rows. The current
human matrices need no wholesale format conversion. Supplemental metadata uses:

```json
{
  "author_lens": "claude",
  "source_hashes": {"src/example/Example.sol": "<sha256>"},
  "dependency_hashes": {"lib/example/Dependency.sol": "<sha256>"},
  "row_annotations": {
    "src/example/Example.sol:Example.claim()": {
      "evidence_ids": ["claim-result"],
      "required_actions": ["credit", "claim"],
      "fuzz_cells": [{"cell_id": "conservation", "required_actions": ["credit", "claim"], "evidence_ids": ["claim-result"]}]
    }
  }
}
```

Annotations add bindings; they cannot override the human row's columns/status.
Fuzz cells must identify the intended actions themselves. Every referenced
action needs an integer `successful_action_counts[action] > 0`; a boolean,
zero, missing key, unrelated positive count, or directed run is insufficient.

Alternatively, `reviewed_commit` binds to a checked-in source snapshot. The
preamble's explicit reviewed commit is recognized for the supplied matrices.
`census_snapshots.json` records the exact production and dependency bytes for
`a4f9840`; this is a code lookup, **not** an audit disposition. It lets shallow CI
checkouts validate that review without fetching old history. Never regenerate
the old commit's hashes from changed code. New code needs a new checker review
binding. Source and dependency hashes are checked for plans and evidence; test
source and raw-output hashes are checked for evidence as well.

The only accepted pattern ledger is `docs/deep/AUDIT_PROVENANCE.md`. Research is
not a fallback. It needs one `provenance` record per `src/**/*.sol` contract,
library, and interface, with exact `contract` (`path:Name`), `pattern`, and
`prior_audit` citation/novel marker, plus a document review binding. A Markdown
table with those columns is also accepted. An optional per-row `source_hash`
must match. Missing/stale/extraneous ledger rows fail.

## Value edges, obligations, and results

The checker supplies these arrays in its document's JSON block:

- `value_edges`: unique `edge_id`, compiler `function_id`, `source_hash`, covered
  `candidate_ids`, `source_account`, `destination_account`, `entitlement_owner`,
  `asset_expression`, `amount_expression`, `authorized_executor`, `sink_policy`,
  nonempty `inventory_kinds`, and nonempty `currencies`.
- `obligations`: unique `obligation_id`, `function_ids`, `edge_ids`, `kind`
  (`round_trip`, `conservation`, `double_assignment`), `mechanism`, `exact_assertion`,
  `reviewer`, `status`, `evidence_ids`, and `required_actions`. Conservation and
  double-assignment outcome twins use `fuzz` or `invariant`. A `top_severity`
  obligation additionally enforces different implementation/oracle lenses.
- `evidence`: unique `evidence_id`, `run_id`, `artifact_path`, `artifact_sha256`.
- `call_resolutions`: exact `function_id`, `call` from the compiler census,
  current `source_hash`, `resolved_target`, `rationale`, and `reviewer`.
- `advisories`: `rule`, `symbol`, `message`. These never fail CI by themselves.

Each evidence artifact is a JSON result record, bound to its exact bytes. It
contains `evidence_id`, `run_id`, `test_or_rule_id`, `execution_status: "PASS"`,
`assertion_result: true`, `mechanism`, source/dependency/test hashes,
`successful_action_counts`, `raw_artifacts` (path→SHA256), `obligation_ids`, and
`assertion_hashes` (obligation ID→SHA256 of its exact assertion text). Fork
evidence also identifies `substrate: "fork"`, the manifest `chain_id`, a nonzero
`fork_block_number`, `fork_block_hash`, and `pinned_at_run_start: true`. Pure/view
rows may cite `static` evidence. Value outcomes require fork evidence. Top
severity results identify `oracle_lens`. Production rejects artifacts labelled
`synthetic_fixture`; the CLI has no override for this.

`witnesses` in each result identify `edge_id`, `inventory_kind`, and `currency`.
Every declared inventory/currency pair must be covered. Withdrawal/forwarding
witnesses carry integer `owed`, `delivered`, `debit`, `sender_extra_debit`, and
`actor` with `mechanism: "self_call"`, `impersonated: false`, `holder`, `entrypoint`,
and `kind`. Required equality: `delivered == owed == debit > 0`; extra debit zero.
Burn/lock witnesses instead require `minted == burned/locked > 0`, `residue == 0`,
per currency. `distinct_transactions: true` on a burn obligation requires two
different transaction hashes, the same block hash, and increasing transaction
indices. The adapter checks recorded outcomes; the checker reviews that the
harness measures them from actual execution, including legitimate authority and
the full inventory/currency population.

## Suppressions

A `suppressions` entry binds exact `rule`, resolved function `symbol`, current
`source_hash`, `rationale`, at least two distinct `signers`, future timezone-aware
`expires_at`, the manifest's `milestone`, and a `re_review_trigger`. No wildcard
symbols or file exemptions. A valid exception is visibly `SUPPRESSED`, never
relabeled as a passing test. Allowed rules are `CELL_OUTCOME`,
`OBLIGATION_OUTCOME`, and `UNRESOLVED_CALL`. Structural completeness, source
currency, absent sinks, bad evidence, and vacuous successful-action counts cannot
be suppressed. Expired, stale, unmatched, and incomplete suppressions fail.

## Current checkpoint integration

The real matrices and canonical audit ledger are checker-owned inputs. Until
they land with complete rows, evidence bindings, and outcomes, the required check
is expected to fail. The build seat must not fill those gaps with its own oracle
results, downgrade built modules to planned, or silently use research provenance.
The tools evidence packet records the actual blockers and the synthetic test run
separately. The frozen M2 contracts and empty Claude oracle slots stay unchanged.
