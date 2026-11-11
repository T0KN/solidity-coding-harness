# Solidity Coding Harness

A drop-in starting point for Solidity/Foundry repos that ships with a **verification harness**. The census workflow is supplied; it becomes a merge requirement only after the owner configures and verifies the branch protections. A module cannot merge until an *independent lens* has proven, function by function, with cited source and executed pinned-fork evidence, that every value path does exactly what it claims — and a machine gate has confirmed that proof is complete.

> **Use this as a template.** In GitHub → this repo → **Settings → General → ✔ Template repository**. Then start every new project with **"Use this template" → Create a new repository**. The census workflow is supplied; it becomes a merge requirement only after the owner configures and verifies the branch protections.

## ▶ Starting a project here — read me first (you don't need to remember any commands)

When you create a repo from this template and begin a project:

1. **You (coordinator):** create the repo, then hand it to your build + checker agents with **one line**:
   > *"This repo ships the checkpoint-census harness. Run `python3 tools/census_selftest.py` to confirm it's healthy, then set up `tools/census_manifest.json` for our contracts and follow `docs/SOLIDITY_VERIFICATION_HARNESS.md` as we build — the CI gate must be green before any merge."*
2. **The agent** runs the self-test (a ~1-second health check → `36 tests OK`) and fills in the manifest with your actual contracts. The census workflow is supplied; it becomes a merge requirement only after the owner configures and verifies the branch protections.

The repository supplies the census code and workflow. The owner must configure and test the day-one protections; the additional project machinery listed in working rule 38 is not included.

## Day-one repo setup (do this before the first agent touches the repo)

A gate that nothing enforces is only advice, and a local hook is not enforcement: a text-matching hook cannot see a merge performed inside a script. The intended enforcement boundary is the host configuration, verified by the tests below. On day one, as the repo owner, in the browser:

1. **A ruleset on `main`** (Settings → Rules → Rulesets → New branch ruleset, enforcement Active):
   - require a pull request before merging, with review from code owners required (item 3); no agent identity merges into `main` at any tier (`docs/WORKING_RULES.md` rule 1);
   - require status checks to pass, with "branches up to date" ticked: add the gate's `census` check (workflow `checkpoint-census`), the lens status (item 4) and every other CI check the moment it first reports;
   - restrict deletions and block force pushes;
   - **no bypass list.** In an emergency, switch the ruleset off yourself and back on.
2. **Use separate service identities for coordinator/builders and lenses.** Give each only the permissions its role needs, never Administration or Secrets. Keep the lens credential outside the coordinator's readable and writable environment; separate token files alone do not establish that boundary.
3. **Configure and test the owner boundary.** Configure owner review for every owner-tier path, including `.github/CODEOWNERS` itself, and PR-only integration. Verify that the coordinator cannot merge owner-tier changes, including after owner approval, and cannot merge anything into `main`. Required review alone is not evidence that the merger is restricted.
4. **Configure and test independent lens acceptance.** Choose the exact status-check or review mechanism the host will enforce. Verify its authorized issuer, exact reviewed commit and integration binding. Verify that coordinator credentials cannot create a substitute acceptance. Do not assume reviews and commit statuses are interchangeable.
5. **Record the host tests before enabling coordinator merges.** Using disposable fixtures, test missing owner review, code-owner review with the configured general-approval count, missing or failing checks, stale-head acceptance, acceptance from the wrong issuer, direct pushes with missing and passing checks, owner-tier integration merges and every coordinator merge into `main`. Record the repository, identities, permissions and ruleset configuration tested. Repeat affected tests after those inputs change. A result establishes the tested configuration and cases only; an unverified boundary leaves coordinator merging disabled.
6. **Local hooks are defence in depth.** Your guard hook may refuse merge and force commands by their text, and it names the one permitted merge script by absolute path and checksum, an exception you write yourself (rule 1i). It cannot see inside a script, so it never replaces items 1-5.
7. **CI order:** the secret scan runs first, in its own job, on a fresh checkout with the base branch's config; every job that runs repo code depends on it.
8. **Gate files** (the workflows, CI scripts and scan config) are tier 2: they change only through a labelled PR that you merge.
9. **A daily off-machine backup** of every repo (all refs as git bundles) plus uncommitted worktree changes.

## What you get

- **`docs/SOLIDITY_VERIFICATION_HARNESS.md`** — the doctrine (20 tenets + the trust boundary): tenets 12-20 cover decisive controls, real committed inputs, constants bound to bytes, frozen source, off-chain predicates, analyzer dispositions, acceptance authenticated from outside its index, closing records and the deploy ceremony. Read it first.
- **`docs/WORKING_RULES.md`** — how the seats work day to day (39 rules): merge tiers priced by undo cost (rule 1), no force flags or pushed-branch rewrites (rule 23), and §6 "Lanes, gates and landings" (rules 24-39).
- **`docs/SEAT_OPERATIONS.md`** — how a coordinator runs its seats, including §11, headless one-shot lanes: the capability table per lane type, verbatim commits of author-lane work, the published gate file, and no added writable roots.
- **`tools/`** — the **census gate**: compiler census, plan/provenance adapters, evidence schema, a template manifest, and a **36-test self-test**. It becomes a required CI check once the owner has configured and verified branch protection. (A shared tier gate, `tools/tier/`, is planned: it is to be added by a separate PR after both lenses, per rule 1j.)
- **`.github/workflows/checkpoint-census.yml`** — the gate wired as a status check (add it to branch protection).
- **`foundry.toml`, `.gitignore`, `.env.example`** — a sane Foundry baseline.
- **`CLAUDE.md`** — governance for any AI/agent seat working the repo (points at the doctrine and the rules).
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
- **controls are decisive and bound to bytes** — every negative control is shown failing with its guard removed; positive controls read the real committed input; constants are re-earned on the merged tree (tenets 12-15).
- **merges are priced by undo cost** — a script decides the tier from what changed and fails closed; the coordinator merges tier 1 only, never into `main`; a local hook is defence in depth, and the host-side controls are the enforcement once the owner has configured and tested them (rule 1).
- **landings are checked by script, then by a non-author lens** — the coordinator's landing record names a real implementation commit, nothing was rewritten, and the selftest is re-run by the coordinator (rules 33-34).
- **no force flags, ever** — no agent rewrites a pushed branch or runs a force flag; a refused destructive action is never retried (rule 23).

Full detail: [`docs/SOLIDITY_VERIFICATION_HARNESS.md`](docs/SOLIDITY_VERIFICATION_HARNESS.md) and the gate spec [`tools/CHECKPOINT_CENSUS.md`](tools/CHECKPOINT_CENSUS.md). Requires Foundry + Python 3.11+.
