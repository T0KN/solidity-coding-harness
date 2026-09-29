# Working rules — how a coordinator, a builder and the lenses work together

These are the operating rules that run alongside the verification harness (`SOLIDITY_VERIFICATION_HARNESS.md`). The harness says what must be proven; this file says how the seats work day to day so the proof happens without waste. They were distilled from a real build (Up Only, Sep 2026) and are binding on every project created from this template. Copy them into the project's `CLAUDE.md` or link this file from it.

## 1. Merges and PRs
1. **Merges are the human owner's.** No agent merges a PR, ever. Every agent pushes under the same identity, so the owner's merge is the only record that a person accepted a change.
2. **A PR opens only after its second lens has passed.** The PR body carries the verdict line: who reviewed, what they found, what was folded. CI green is never the review.
3. **One PR per real change; batch the rest.** Records, reports and hygiene changes accumulate on a staging branch (`docs/next`) and land as one PR.

## 2. Seats
4. **Author ≠ checker.** No seat clears its own work. A builder never approves its own PR; a checker never checks work its own model wrote; a top-severity oracle's lens differs from the builder's.
5. **Fresh thread per builder task; one task per thread.** A mid-task note goes into the live thread through a note script; a new task always respawns. Dispatch through a script that guards against the tool's own dialogs (updates, rate-limit model switches, slow-response menus): a bare Enter has switched models before.
6. **Briefs state reading scope** as exact files and line ranges, never "read in full"; they name the prior report if one exists; they require commit-early, real exit codes and log paths in the hand-back. Files stay under 800 lines; a seat that reads a 2,000-line file whole dies with nothing committed.
7. **Non-interactive lanes for the cheap seats.** Red-team and oracle seats run headless with auto-approval in their own clones and tmux windows, streaming to a log; the owner never approves their commands. The builder keeps manual approvals.

## 3. Discipline
8. **Primary-source discipline.** No claim about an external system without an in-context citation (a doc line, `file:line`, a decoded transaction, an RPC read); otherwise write "UNVERIFIED — not checked". "Probably/should/presumably" are banned as substitutes for looking. Equivalence and absence claims need end-to-end verification, never inference from silence. On pushback, re-read the source first. Tag material claims `[verified: <cite>]` or `[UNVERIFIED]`.
9. **Verify the claim, not its neighbour.** Reading the arithmetic at one line is not reading the guard on its input at another. Bind each proof to the exact property at its exact strength.
10. **Consequence paths get the strongest treatment.** Anything that moves or gates money, authenticates, or protects data gets the strongest model for review, an adversarial second lens from a different model family, a real-world test where one exists (a live-state fork beats a mock; a differential against the live reference beats both), and never self-clearance. Everything else can use cheaper models.
11. **Nothing ratified is re-decided by an executing seat.** If something looks like a product or design call, it is written as a question for the owner to take to the deciding gate, never as a recommendation in a record. Every parameter in a record cites the ruling that set it.
12. **Test against the live reference whenever one exists.** A forked contract carries a live-matrix differential against the original on a pinned fork of mainnet; every difference maps to a named, priced register entry or blocks close-out; the run re-executes at every checkpoint close and every fee-path change, with its run id cited.

## 4. Machinery and spend
13. **New machinery gets two questions before it is built:** is this a rabbit hole, and does it bring us closer to shipping? Prefer re-running an existing check over building a new one. Two HOLDs on the same artifact for new shapes means stop and re-open the design with the owner, never a third round.
14. **Spend is orchestration volume.** Task count and context size drive cost, not model choice; never downgrade a verifier to save tokens. Lenses read a verdict and a findings table, never a whole packet. Fix loops batch fixes before re-checking. Every checkpoint carries a written budget agreed with the owner before dispatch, with a hard stop in the brief.
15. **Tooling and CI changes are not "working" until their runtime capability is verified at source** (token scopes from the runner's permissions log, tools present on the runner), and their acceptance control is a mechanism-specific log line, never an outcome a silent failure also produces.
16. **A passing gate proves coverage and binding, never truth.** After any gate goes green, adversarially audit the content: does every claim prove its label, does every citation resolve to the exact assertion, is every number derived from a run.

## 5. Handoffs
17. **Everything through git.** Nothing reaches a seat from a chat, a scratchpad or a download; the repo is the handoff. Secrets only in gitignored files, never printed or committed.
18. **A module is not closed until its downstream handoff pack is delivered** (interfaces, events, product rules, fixtures, a paste-ready prompt), versioned, as a PR to the consuming repo. The pack carries the ratified canon behind every parameter it states, not only the parameter.
19. **No unattended loops.** A dispatched run finishes and reports; nothing re-dispatches itself.
20. **Status to the owner in one shape: done / running / your step.** Short turns; one thing per turn; never hold a turn waiting on a run.

## 6. Six learnings from the hardest week
Read a ruling for its purpose and ask before building · re-running beats proving · freeze the producer chain before the first capture · name the evidence producer path · the independent closer is never waived, and two HOLDs means stop · spend is orchestration volume.
