# CLAUDE.md — Solidity project (governed by the Verification Harness)

**Read [`docs/SOLIDITY_VERIFICATION_HARNESS.md`](docs/SOLIDITY_VERIFICATION_HARNESS.md) before building.** If global Solidity rules are loaded, verify their version and reconcile conflicts with this repository before starting work.

## The seat model
- **Builder** writes the `.sol`. **Checker** (a *different* model/seat) authors the per-function checkpoint and clears the module. The seat that built a module never clears it.
- A top-severity oracle's lens differs from the builder's.

## Non-negotiables — binding policy, with enforcement coverage recorded separately
1. **Fork verbatim, add sauce** — burden of proof is on *adding* complexity; name every divergence.
2. **Primary-source discipline** — no claim about another contract/chain without an inline `file:line`/on-chain cite; verify-don't-argue; tag `[verified]`/`[ASSUMPTION]`; absence is proven, never inferred.
3. **Per-function checkpoint, contract-by-contract, no drift** — finish + verify one contract before the next.
4. **Citations as proof-of-work** — every plan row cites `[src/…:start-end]`; no citation ⇒ not done.
5. **Author in the target format from source** — read the gate/schema first; never prose-draft-then-reformat.
6. **Pinned-fork proof-of-check** — PASS needs real evidence (chain-pinned fork + hashed tests + raw artifacts + derived counts + per-edge witnesses), never a test name or the word "PASS".
7. **Gate-green ≠ correct** — after the gate is green, adversarially audit content before landing: prove every label, bind evidence to the *exact* assertion, resolve every citation, derive every number, run at strictest; report the shortcuts you fixed.
8. **No shortcuts on money/reentrancy/access/migration** — strongest model + adversarial verification; never downgrade a verifier to save tokens.
9. **Controls are decisive and bound to bytes** — every negative control is shown failing with its guard removed; a positive control reads the real committed input; calibration constants are re-earned on the merged tree; frozen source is compared by hash (doctrine tenets 12-15).
10. **Off-chain predicates, acceptance and the send** — an unenforced predicate is named off-chain with a refusing preflight; acceptance is authenticated from outside its index; each stage has a closing record; the deploy ceremony is rehearsed, verified by nonce, and runs only on the owner's word (tenets 16-20).
11. **Merges are priced by undo cost** — among agents, only the coordinator may merge the changes authorized by `docs/WORKING_RULES.md` rule 1, into the integration branch only. The owner retains every reserved merge and action.
12. **Lanes are fixed capability contracts; landings are checked by script** — author, run and lens lanes each get their contract from the dispatcher; a landing needs the land check plus a non-author lens; no force flag and no pushed-branch rewrite, ever (`docs/WORKING_RULES.md` rules 23-39, `docs/SEAT_OPERATIONS.md` §11).

## The gate
`tools/checkpoint_census.py` is a CI check (see `.github/workflows/checkpoint-census.yml`). The census workflow is supplied; it becomes a merge requirement only after the owner configures and verifies the branch protections. It reads the checker's plan + evidence against the *compiled* source and blocks the merge unless coverage, value-edges, call-resolutions, obligations, provenance, and evidence are all complete. It proves the checkpoint is complete and bound — **not** that its content is true (that's rule 7).

## Secrets
Never print, paste, or commit an RPC key or secret. Source it from a gitignored `.env`; redact it from all output.

## Working rules
The day-to-day operating rules for the seats (merge tiers, PRs, briefs, discipline, spend, handoffs, and §6 "Lanes, gates and landings") are in `docs/WORKING_RULES.md`. How a coordinator runs a builder seat day to day (the start command, one task per fresh thread, the approval relay, watchers, the stop rule, hand-backs, budget) and its headless one-shot lanes (§11: the capability table, verbatim commits, the published gate file, no added writable roots) is `docs/SEAT_OPERATIONS.md`, binding alongside it. They are binding alongside the harness; copy or link them into every project created from this template.

## Agent spend and seat tiers

**Agent spend and seat tiers (adopted 2026-10-10; an independent cross-vendor read concurred with changes, folded here).** The seat (the strongest available model, high) plans, checks and coordinates itself; a subagent exists for authorship separation or for volume, never for convenience. It governs the Anthropic subagents a coordinator dispatches (executors, checkers, lenses); the Codex builder seats keep their own thread rules (a fresh thread per task, continuation notes within a task, run until the tests pass and report real exit codes). Complex tooling, including drivers, runners and gate scripts, is written by the strongest available author. Fast models keep bounded edits and reading lanes. A model pin records the current routing; it is not an exception to this consequence rule. Mechanical work goes to Haiku 5.5 at high only when admitted by property: a pre-reviewed transformation and check pair, complete coverage, positive and negative controls, a constrained diff and a non-author checker; never canon text, obligation rows or money paths. Verification, gates and lenses never move to a cheaper model or effort, and independent evidence runs (captures, replays, adversarial checks, gate waves) stay with their owner; a coordinator's log is evidence to examine, not a verdict. Deterministic non-evidence runs longer than a few minutes run from the seat in the background and the agent receives the result. A subagent is one-shot and hands back; never resume one that has sat idle; a follow-up goes to a fresh agent with the findings pasted in. Plan each brief to finish in about forty tool calls, splitting at coherent artifact boundaries with an integration check; the count is a planning signal, not a stop rule. Run independent jobs in parallel, including independent Anthropic executors and checkers, up to `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`. Serialize only for dependencies or the resource gate. No availability probes, no forks for reads, greps instead of fact-finding agents. Every brief names the paths it may read and change, numbered steps, one pass check with its expected output, and "stop and report raw output on failure". Measure the whole workflow, repairs and rejected drafts included; a running subagent-token total goes in every status. Dispatch changes must respect the owner's control of seat settings under `docs/SEAT_OPERATIONS.md` §9; model routing must satisfy `docs/WORKING_RULES.md` rule 10.
