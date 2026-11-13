# Solidity Verification Harness

> The discipline this project uses to prove a contract module is correct — not that it compiles, not that tests pass, but that an **independent lens has shown, function by function, with cited source and executed pinned-fork evidence, that every value path does exactly what it claims**, and a machine gate has confirmed that proof is complete.
>
> This repository is the versioned source for the doctrine. Global Solidity rules may be installed separately; verify their version and reconcile differences before treating them as equivalent. The census implementation is in `tools/`.

## Why

Contract code is adversarial, immutable once deployed, and moves money. "It compiled" and "the suite is green" are the two most expensive false comforts in the domain. This harness replaces conviction-by-vibes with **coverage + citation + executed proof + independent audit**, checked by a machine gate that becomes a merge requirement once the owner configures and verifies the branch protections, so it cannot quietly lapse.

## The tenets

1. **Fork verbatim, add sauce.** For anything a value-validated reference already does, fork it 1-for-1; the burden of proof is on *adding* complexity. Name every divergence in a source-map comment.

2. **Primary-source discipline.** No claim about another contract/chain/standard without an inline `file:line` / on-chain citation. Equivalence and absence claims require end-to-end verification; absence is proven from the specific code, never inferred from silence. On pushback, **verify — don't argue**. Tag claims `[verified: cite]` / `[ASSUMPTION]`.

3. **Author ≠ checker.** The seat/model that builds a module never clears it. The per-function checkpoint is authored by a different lens; a top-severity oracle's lens differs from the builder's. Decorrelated blind spots.

4. **Per-function checkpoint, contract-by-contract, no drift.** Each module closes only with a per-function plan (intent, logic, reentrancy, intended-vs-actual, value-flow, classes) by the non-builder lens. Finish + verify one contract before the next.

5. **Citations as proof-of-work.** Every authored row carries a `[file:line]` citation to the exact source range. No citation ⇒ not done. A `.sol` line is a *source* citation, not a *prior-audit* citation; both must resolve to real targets.

6. **Author in the target format, from source.** Read the gate/schema first, read the source item-by-item, author each item directly in-target. Never prose-draft-then-reformat. If a machine gate exists, it *is* the format spec.

7. **Mechanical enforcement — the census gate.** A CI check, required once the owner configures and verifies the branch protections, reads the checker's plan + evidence against the *compiled* source and refuses to close a module unless coverage, value-edges, call-resolutions, obligations, provenance, and evidence are all complete. Convention drifts; a required check does not.

8. **Verified proof-of-check (pinned-fork evidence).** A row/obligation is PASS only with a replayable evidence record: live fork pinned at run start (chain id + block number + block hash + `pinned_at_run_start`), hashed test sources + raw artifacts, derived action counts, and per-edge witnesses reconciling the exact identity claimed (`owed==delivered==debit>0`; burn/lock `minted==burned/locked>0, residue==0`), bound by an assertion hash. Never a test name or the word "PASS".

9. **Gate-green ≠ correct authoring.** A green gate proves coverage and binding, never that the content is true. Before landing, adversarially audit content: prove every label (assert the observable), bind each evidence to the *exact* assertion (not a weaker neighbour), resolve every citation, derive every number, run the check at its strictest setting, and report the shortcuts you found and fixed.

10. **Every recurring finding becomes a per-function class.** Fold each audit finding into a named bug class on the checkpoint and into the gate, and source every pattern as "not novel" (prior-audit citation) or explicitly "novel — no prior audit".

11. **No shortcuts on consequence paths.** Money, reentrancy, access-control, migration, and cross-contract accounting get the strongest model and the most adversarial verification. Verification is not routine work; a weak verifier ships a false green.

12. **Controls are decisive.** Every negative control is shown to fail when its guard is removed: the author deletes or inverts the guard, shows the control going red, and records the mutation and its exit code. A control that stays green with its guard gone proves nothing. (2026-11: lenses re-running mutations found real defects in every landing; the mutation is now the author's obligation, and the lens repeats it.)

13. **A positive control uses the real committed input.** It reads the same plan, manifest or record the production run will read, at its commit, never a mock-shaped twin of it. A mock proves the code against the author's assumption of the input. (2026-11: mocks passed a driver that rejected the real committed plan.)

14. **Calibration constants and gas budgets are bound to bytes.** Every number derived from a measurement (a gas budget, a hostile-path ceiling, a size bound) records the commit and source hashes it was measured on, and is re-earned on the merged tree before the merge. Evidence captured before a `src/` or `test/` change is re-run, never copied: `git diff --name-only <capture-commit>..HEAD -- src/ test/` must list nothing, or the run is redone. (2026-11: a hostile-budget calibration constant was stale on the merged tree.)

15. **Frozen source is frozen to the byte.** A comment edit changes the metadata hash, therefore the creation code, therefore every CREATE2 address planned from it. A frozen file is compared by hash, never by "no logic change". Declarations about frozen source (what it does, what it lacks, what a tool may assume) live in reviewed fixtures, never in edits to the source.

16. **A predicate the contract does not enforce is named as off-chain.** When correctness depends on a condition the bytecode never checks (an argument range, an ordering, an allow-list, a pairing), the plan names it OFF-CHAIN, gives it a preflight that refuses before submission, and tests that preflight in every mode it applies to (deploy, addition, edit). An unenforced predicate with no refusing preflight is an open finding.

17. **Analyzer findings and coverage failures are dispositioned per id by a non-builder.** Every static-analyzer finding id carries a non-builder disposition (fixed; false positive with its reason; accepted, with its owner) in a reviewed waiver set, and CI records the analyzer's version and exit code with the run. A coverage-tool failure is dispositioned with its reason, never skipped or ignored.

18. **Acceptance is authenticated from outside the index that claims it.** Consumers of an acceptance index take its commit and digest from outside it (the coordinator's own review, on the command line), never from the index's own fields; each entry's record is fetched at its commit and hash-checked; and the accepting document itself must name the condition and the record's digest or path at commit. An index entry alone never establishes acceptance. A record whose own text carries a non-final label (PARTIAL, PENDING, DRAFT, OPEN) is refused, a rehearsal-scope acceptance is refused by every live-write path, and a resume re-validates the whole chain.

19. **Every stage closes with a closing record.** It names the lenses assigned, the decorrelated lenses that actually executed (with their run ids), and every carried item with its owner and the gate that will close it. A stage with a carried item that has no owner or gate is not closed.

20. **The deploy ceremony is designed and tested before the send.** Resume after an interruption and recovery from a duplicate broadcast are built and rehearsed before the first transaction: a wallet can broadcast one signed transaction twice, and the duplicate's "nonce too low" error is not a failure. Verification is by nonce: read the sender's nonce and find the mined transaction for it before deciding anything, and never re-send on an error alone. Nothing is sent before every piece of readback evidence it depends on is validated. Frozen rehearsal evidence is loaded in one place: every digest the freeze records is verified from bytes read once, every consumer uses those retained bytes, and a file the freeze does not bind never feeds a decision. Wallet settings that a creation needs (a hardware wallet's blind signing) are on the operator checklist. Every one-way write (deploy, immutables, ownership, a multisig execution) is named one-way and runs only on the owner's word; a plan line, a green gate or a ratified ruling is never that word.

## The mechanical harness

The census gate enforces the coverage and binding checks listed below. It does not mechanically enforce every tenet; the additional project controls and their implementation status are recorded under working rule 38.

1. **compiles → census** — emits the authoritative per-function list from the compiled artifact (never a hand-written list);
2. **checks the checker's plan + evidence against that census** — a coverage/consistency check that never turns prose into evidence;
3. The census workflow is supplied; it becomes a merge requirement only after the owner configures and verifies the branch protections.

Reference implementation: `tools/checkpoint_census.py`, `census_source.py`, `census_documents.py`, `census_manifest.json`, `census_selftest.py` and `CHECKPOINT_CENSUS.md`. Reuse this repository as the template, configure its manifest, and have the owner configure and verify the required CI check.

## The trust boundary (never blur it)

The gate proves the plan is **complete and bound**. It does **not** prove the content is **true**. Tenet 9 — the adversarial content audit — is the human/LLM step done *on top of* a green gate, before landing. Treating green as done is the same shortcut this harness exists to prevent.
