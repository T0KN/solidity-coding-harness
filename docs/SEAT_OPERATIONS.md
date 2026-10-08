# Seat operations — how a coordinator runs a builder seat

Binding alongside `WORKING_RULES.md`. Every coordinator (one per repository) runs its builder seats from this page, aligns its tooling to it once, and changes it only by a pull request here. Written 2026-10-07 after two coordinators on one machine had drifted apart: one dispatched by relaunching the seat's window per task, the other by pasting into a standing session; one seat prompted for every git write, the other did not; neither had a page to point at. The rules below are the union of what worked, stated once.

## 1. Seats, accounts, homes
1. A **seat** is one Codex CLI session in one tmux session, pointed at one repository checkout. A seat does one task at a time, hand-dispatched by its coordinator.
2. A **Codex home** (`CODEX_HOME=<dir>`) is one logged-in account. Two seats may share a home — they then share that account's weekly limit and nothing else. Separate repositories never share a home's **config file**: a shared home's `config.toml` is changed only by the owner, never by a coordinator.
3. Each seat gets its own checkout. A second seat on a repository that already has a seat starts its thread with `/new` → **New worktree** (a Codex-managed worktree), never in another seat's checkout, never in the coordinator's.

## 2. The start command (the standard launch)
```
tmux new-session -d -s <seat> -n "<SEAT NAME>" -x 200 -y 50 -c <repo> \
  "CODEX_HOME=<home> codex --model <model>"
```
- **No sandbox widening.** An earlier version of this page added `.git` as a writable root so that fetch/branch/commit/push would not prompt. **Withdrawn 2026-10-07:** the sandbox has no finer grain than a directory, so that root also makes `.git/hooks` and `.git/config` seat-writable — a seat could install a hook that later runs unsandboxed in the coordinator's or the owner's git, or rewrite the credential helper that emits the token — and nothing of it shows in a PR diff (found by the app coordinator's Sonnet read, reproduced with Codex's own sandbox tooling). No `approval_policy` change either. The seat runs Codex's defaults; git-metadata writes prompt.
- **How those prompts are handled:** the owner may give a standing word that standard git prompts on the seat's OWN branches (fetch, branch, commit, push; never `main`, never another seat's branch) are pressed by the coordinator without relaying. Everything else is relayed (§4). Never "don't ask again".
- The launch command lives wherever the seat is actually launched from: if a dispatcher script relaunches the window per task, the command lives in that script; if the session persists and tasks are pasted in, the command is recorded in the repository's ops notes. Either way it is in git, not in a chat.
- The owner trusts the repository folder once at the seat's first start (Codex asks; the coordinator never answers that prompt).

## 3. One task per fresh thread
1. Every task is a **brief** committed or saved at a path the seat can read; the dispatch line is `Read the brief at <path> and execute it exactly`.
2. Every task starts with `/new` (a fresh thread: roughly half the tokens of a continued one). A seat that owns its checkout chooses **Current checkout**; a second seat chooses **New worktree**.
3. Briefs carry: context and authorization; the exact base commit and branch; scope by plan rows; what stays untouched; the stop rule (§6); the deliverable and its path; DO NOT lines; an **estimate as a number, never a cap**.
4. Before dispatch the coordinator runs the five-line pre-dispatch check: seat, deliverable, what already exists, the estimate, the base commit verified at source.

## 4. The approval relay
1. Each seat pane has a **silent watcher** that exits when an approval prompt is waiting (and on a timeout, when it is re-armed). It is a read-only script allowed by a permission rule so it never needs a judge.
2. When a prompt waits, the coordinator sends the owner the **exact prompt text and its numbered choices** (one phone push when the owner is away) and presses **only the choice the owner names**. The coordinator never answers a prompt on its own, never picks "always allow / don't ask again", and never presses a model-downgrade option.
3. The watcher can fire on the `/new` thread picker; the coordinator looks before relaying.
4. Under the owner's standing word (§2), standard git prompts on the seat's own branches are pressed by the coordinator; the relay stays armed for everything else.

## 5. The build watcher and the lane log
1. Each dispatch gets a background watcher in the same turn that appends to one lane-status file (dispatch time, boundary, result path) and exits at the seat's boundary, on a lost pane, or when free disk falls under **20 GB** (a Foundry or fork-cache run can fail at 10).
2. "Running" is never claimed without a same-turn check of the pane.

## 6. The stop rule (three classes)
1. **Connection failures** (DNS, RPC, a 5xx): retry up to three times with a pause, recorded; stop only if all three fail.
2. **The builder's own test or fixture errors:** fix, record the fix, continue.
3. **Production findings:** record the finding, leave its witness failing, continue the stage; never weaken or delete a test, never rename a failing witness as passing.
A seat stops only at a **stage boundary** (commit, push, stage note), or on a named stop condition in its brief (an unverified external dependency, a size bound crossed — then it hands back a measured list, never a silent cut).

## 7. The hand-back
Every stage note carries: the base and head commits; the delta map by plan row with `file:line`; every command with its real exit code and log path; the size ledger where a gate exists; what is still failing and why; what the brief asked that was not done; and the **account's limit reading** as the screen shows it (or "UNAVAILABLE", never a number inferred from an estimate). The builder reports; it never clears its own work.

## 8. Budget
1. The limit reading in every hand-back is the budget instrument. Seats sharing a home coordinate through their coordinators when the reading gets tight; the owner decides the split.
2. Never a spend cap on a task. The control is planning before dispatch: the right seat, the deliverable, what exists, the estimate as a number.
3. Never resume a large-context thread for a small fix; dispatch a fresh one.

## 9. What never changes without the owner's word
Repository settings and rulesets; a shared home's `config.toml`; the approval policy, the sandbox mode or the writable roots of any seat (never widened); the start command's model; any seat's checkout being deleted or moved. A coordinator proposes; the owner says the word; the change is recorded in git.

## 10. Alignment
Each coordinator aligns its seats to this page once (one tooling PR per repository where a dispatcher must carry the start command) and reports the alignment in its next status: the start command as launched, the watcher paths, and the owner's standing word on git prompts, if given.
