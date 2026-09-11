# Solidity Verification Harness

> The discipline this project uses to prove a contract module is correct — not that it compiles, not that tests pass, but that an **independent lens has shown, function by function, with cited source and executed pinned-fork evidence, that every value path does exactly what it claims**, and a machine gate has confirmed that proof is complete.
>
> This doc is the project copy. The same doctrine is installed globally at `~/.claude/rules/solidity/` (auto-applied to all Solidity work); the mechanical enforcement is the checkpoint-census gate (reference implementation in `tools/`; portable template in `docs/deep/checkpoint-census-kit/`).

## Why

Contract code is adversarial, immutable once deployed, and moves money. "It compiled" and "the suite is green" are the two most expensive false comforts in the domain. This harness replaces conviction-by-vibes with **coverage + citation + executed proof + independent audit**, mechanically enforced so it cannot quietly lapse.

## The tenets

1. **Fork verbatim, add sauce.** For anything a value-validated reference already does, fork it 1-for-1; the burden of proof is on *adding* complexity. Name every divergence in a source-map comment.

2. **Primary-source discipline.** No claim about another contract/chain/standard without an inline `file:line` / on-chain citation. Equivalence and absence claims require end-to-end verification; absence is proven from the specific code, never inferred from silence. On pushback, **verify — don't argue**. Tag claims `[verified: cite]` / `[ASSUMPTION]`.

3. **Author ≠ checker.** The seat/model that builds a module never clears it. The per-function checkpoint is authored by a different lens; a top-severity oracle's lens differs from the builder's. Decorrelated blind spots.

4. **Per-function checkpoint, contract-by-contract, no drift.** Each module closes only with a per-function plan (intent, logic, reentrancy, intended-vs-actual, value-flow, classes) by the non-builder lens. Finish + verify one contract before the next.

5. **Citations as proof-of-work.** Every authored row carries a `[file:line]` citation to the exact source range. No citation ⇒ not done. A `.sol` line is a *source* citation, not a *prior-audit* citation; both must resolve to real targets.

6. **Author in the target format, from source.** Read the gate/schema first, read the source item-by-item, author each item directly in-target. Never prose-draft-then-reformat. If a machine gate exists, it *is* the format spec.

7. **Mechanical enforcement — the census gate.** A required CI check reads the checker's plan + evidence against the *compiled* source and refuses to close a module unless coverage, value-edges, call-resolutions, obligations, provenance, and evidence are all complete. Convention drifts; a required check does not.

8. **Verified proof-of-check (pinned-fork evidence).** A row/obligation is PASS only with a replayable evidence record: live fork pinned at run start (chain id + block number + block hash + `pinned_at_run_start`), hashed test sources + raw artifacts, derived action counts, and per-edge witnesses reconciling the exact identity claimed (`owed==delivered==debit>0`; burn/lock `minted==burned/locked>0, residue==0`), bound by an assertion hash. Never a test name or the word "PASS".

9. **Gate-green ≠ correct authoring.** A green gate proves coverage and binding, never that the content is true. Before landing, adversarially audit content: prove every label (assert the observable), bind each evidence to the *exact* assertion (not a weaker neighbour), resolve every citation, derive every number, run the check at its strictest setting, and report the shortcuts you found and fixed.

10. **Every recurring finding becomes a per-function class.** Fold each audit finding into a named bug class on the checkpoint and into the gate, and source every pattern as "not novel" (prior-audit citation) or explicitly "novel — no prior audit".

11. **No shortcuts on consequence paths.** Money, reentrancy, access-control, migration, and cross-contract accounting get the strongest model and the most adversarial verification. Verification is not routine work; a weak verifier ships a false green.

## The mechanical harness

The tenets above are only real because a **merge-blocking required check** enforces them. The census gate:

1. **compiles → census** — emits the authoritative per-function list from the compiled artifact (never a hand-written list);
2. **checks the checker's plan + evidence against that census** — a coverage/consistency check that never turns prose into evidence;
3. **is wired into branch protection** as a required status check.

Reference implementation: `tools/checkpoint_census.py` (+ `census_source.py`, `census_documents.py`, `census_manifest.json`, `census_selftest.py`, `CHECKPOINT_CENSUS.md`). Portable, project-agnostic template to reuse elsewhere: `docs/deep/checkpoint-census-kit/` — copy it into a new Foundry repo, set `chain_id` + modules in the manifest, wire the CI check.

## The trust boundary (never blur it)

The gate proves the plan is **complete and bound**. It does **not** prove the content is **true**. Tenet 9 — the adversarial content audit — is the human/LLM step done *on top of* a green gate, before landing. Treating green as done is the same shortcut this harness exists to prevent.
