# Solidity Coding Harness

A drop-in starting point for Solidity/Foundry repos that ships with a **merge-blocking verification harness** baked in. A module cannot merge until an *independent lens* has proven, function by function, with cited source and executed pinned-fork evidence, that every value path does exactly what it claims — and a machine gate has confirmed that proof is complete.

> **Use this as a template.** In GitHub → this repo → **Settings → General → ✔ Template repository**. Then start every new project with **"Use this template" → Create a new repository** — the whole harness comes pre-wired.

## What you get

- **`docs/SOLIDITY_VERIFICATION_HARNESS.md`** — the doctrine (11 tenets + the trust boundary). Read it first.
- **`tools/`** — the **census gate**: compiler census, plan/provenance adapters, evidence schema, a template manifest, and a **36-test self-test**. This is the required CI check.
- **`.github/workflows/checkpoint-census.yml`** — the gate wired as a status check (add it to branch protection).
- **`foundry.toml`, `.gitignore`, `.env.example`** — a sane Foundry baseline.
- **`CLAUDE.md`** — governance for any AI/agent seat working the repo (points at the doctrine).
- **`docs/deep/AUDIT_PROVENANCE.md`** — an empty provenance ledger to fill per contract.

## Quickstart

```bash
# 1. Install Foundry if needed:  curl -L https://foundry.paradigm.xyz | bash && foundryup
# 2. Prove the harness works (needs only Foundry — no external deps):
python3 tools/census_selftest.py          # → 36 tests OK
# 3. Point the gate at your project:
#    edit tools/census_manifest.json  → set "chain_id" and one entry per module
# 4. As you build, author each module's per-function plan (by the CHECKER lens, from source, with
#    [file:line] citations) and produce pinned-fork evidence; then:
python3 tools/checkpoint_census.py --release checkpoint   # must be 0 hard failures to merge
```

## The rules (non-negotiable)

- **author ≠ checker** — the seat/model that builds a module never clears it.
- **per-function checkpoint, contract-by-contract** — finish + verify one contract before the next.
- **citations as proof-of-work** — every row cites `[src/…:start-end]`; no citation ⇒ not done.
- **pinned-fork proof-of-check** — a row/obligation is PASS only with real evidence (chain-pinned fork + hashed tests + per-edge witnesses), never a test name.
- **gate-green ≠ correct** — a green gate proves coverage/binding, not truth. The adversarial content audit is done *on top of* a green gate, before landing.

Full detail: [`docs/SOLIDITY_VERIFICATION_HARNESS.md`](docs/SOLIDITY_VERIFICATION_HARNESS.md) and the gate spec [`tools/CHECKPOINT_CENSUS.md`](tools/CHECKPOINT_CENSUS.md). Requires Foundry + Python 3.11+.
