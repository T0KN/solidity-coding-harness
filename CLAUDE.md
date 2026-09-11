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
