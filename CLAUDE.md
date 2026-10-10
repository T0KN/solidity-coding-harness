# CLAUDE.md — Solidity project (governed by the Verification Harness)

**Read [`docs/SOLIDITY_VERIFICATION_HARNESS.md`](docs/SOLIDITY_VERIFICATION_HARNESS.md) before building.** The global ruleset at `~/.claude/rules/solidity/` also applies and is auto-loaded.

## The seat model
- **Builder** writes the `.sol`. **Checker** (a *different* model/seat) authors the per-function checkpoint and clears the module. The seat that built a module never clears it.
- A top-severity oracle's lens differs from the builder's.

## Non-negotiables (the harness enforces these)
1. **Fork verbatim, add sauce** — burden of proof is on *adding* complexity; name every divergence.
2. **Primary-source discipline** — no claim about another contract/chain without an inline `file:line`/on-chain cite; verify-don't-argue; tag `[verified]`/`[ASSUMPTION]`; absence is proven, never inferred.
3. **Per-function checkpoint, contract-by-contract, no drift** — finish + verify one contract before the next.
4. **Citations as proof-of-work** — every plan row cites `[src/…:start-end]`; no citation ⇒ not done.
5. **Author in the target format from source** — read the gate/schema first; never prose-draft-then-reformat.
6. **Pinned-fork proof-of-check** — PASS needs real evidence (chain-pinned fork + hashed tests + raw artifacts + derived counts + per-edge witnesses), never a test name or the word "PASS".
7. **Gate-green ≠ correct** — after the gate is green, adversarially audit content before landing: prove every label, bind evidence to the *exact* assertion, resolve every citation, derive every number, run at strictest; report the shortcuts you fixed.
8. **No shortcuts on money/reentrancy/access/migration** — strongest model + adversarial verification; never downgrade a verifier to save tokens.

## The gate
`tools/checkpoint_census.py` is a **required CI check** (see `.github/workflows/checkpoint-census.yml`). It reads the checker's plan + evidence against the *compiled* source and blocks the merge unless coverage, value-edges, call-resolutions, obligations, provenance, and evidence are all complete. It proves the checkpoint is complete and bound — **not** that its content is true (that's rule 7).

## Secrets
Never print, paste, or commit an RPC key or secret. Source it from a gitignored `.env`; redact it from all output.

## Working rules
The day-to-day operating rules for the seats (merges, PRs, briefs, discipline, spend, handoffs) are in `docs/WORKING_RULES.md`. How a coordinator runs a builder seat day to day (the start command, one task per fresh thread, the approval relay, watchers, the stop rule, hand-backs, budget) is `docs/SEAT_OPERATIONS.md`, binding alongside it. They are binding alongside the harness; copy or link them into every project created from this template.

## Agent spend and seat tiers

**Agent spend and seat tiers (adopted 2026-10-10 after a measured census and a three-way effort test; an independent cross-vendor read concurred with changes, folded here).** The seat (the strongest available model, high) plans, checks and coordinates itself; a subagent exists for authorship separation or for volume, never for convenience. Judgment authorship goes to the Opus 5.5 executor at its pinned effort; a pin changes only for a named task class after a repeated, controlled comparison, never after one job. Mechanical work goes to Haiku 5.5 at high only when admitted by property: a pre-reviewed transformation and check pair, complete coverage, positive and negative controls, a constrained diff and a non-author checker; never canon text, obligation rows or money paths. Verification, gates and lenses never move to a cheaper model or effort, and independent evidence runs (captures, replays, adversarial checks, gate waves) stay with their owner; a coordinator's log is evidence to examine, not a verdict. Deterministic non-evidence runs longer than a few minutes run from the seat in the background and the agent receives the result. A subagent is one-shot and hands back; never resume one that has sat idle; a follow-up goes to a fresh agent with the findings pasted in. Plan each brief to finish in about forty tool calls, splitting at coherent artifact boundaries with an integration check; the count is a planning signal, not a stop rule. One Anthropic executor or checker at a time per coordinator; parallel fan-out across Deep, GLM and Astra. No availability probes, no forks for reads, greps instead of fact-finding agents. Every brief names the paths it may read and change, numbered steps, one pass check with its expected output, and "stop and report raw output on failure". Measure the whole workflow, repairs and rejected drafts included; a running subagent-token total goes in every status. None of this changes a roster, a verifier or a model.
