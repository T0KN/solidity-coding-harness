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
1. The limit reading in every hand-back is the budget instrument, taken from the tool's own rate-limit record or its screen, never recalled or inferred from an estimate. Seats sharing an account coordinate through their coordinators when the reading gets tight; the owner decides the split.
2. Never a spend cap on a task, and never a floor or reserve held on a meter. The control is planning before dispatch: the right seat, the deliverable, what exists, the estimate as a number.
3. Never park work behind a reset while another account has room: run it now on the account with room, and let a meter at zero wait for its reset while the other account carries on.
4. Never resume a large-context thread for a small fix; dispatch a fresh one.

## 9. What never changes without the owner's word
Repository settings and rulesets; a shared home's `config.toml`; the approval policy, the sandbox mode or the writable roots of any seat (never widened); the start command's model; any seat's checkout being deleted or moved. A coordinator proposes; the owner says the word; the change is recorded in git.

## 10. Alignment
Each coordinator aligns its seats to this page once (one tooling PR per repository where a dispatcher must carry the start command) and reports the alignment in its next status: the start command as launched, the watcher paths, and the owner's standing word on git prompts, if given.

## 11. Headless one-shot lanes (the `exec` form)
Added 2026-11 after a night of parallel one-shot lanes. A headless lane is one non-interactive run in its own tmux window: the brief on standard input, a sandbox mode, approvals off, output to a log. It runs once, prints its final line and exits; nothing re-dispatches it (`WORKING_RULES.md` rule 19). Nobody presses anything here, unlike the interactive seat of §2-§4: with approvals off, a command the sandbox refuses fails instead of prompting, so the sandbox is the wall, and §9's never-widen rule binds harder.
1. **The launch line lives in one dispatch script with a selftest, never hand-rolled.** The script sets the home, the tree (`--cd`), the model, the sandbox mode (`-s read-only` or `-s workspace-write`) and the effort, reads the brief from standard input, writes the log, and prepends the lane type's contract (item 2) to the brief. It refuses a brief with no recorded lens verdict or brief-lint pass (`WORKING_RULES.md` rule 28), and it refuses `danger-full-access`, every approval- or sandbox-bypass flag and any `--add-dir` (item 5). (2026-11: a dispatcher with a selftest already existed, and lanes were launched by hand all night instead.)
2. **Capability table.** The dispatcher attaches the row; a brief never asks a lane for more (`WORKING_RULES.md` rule 24).

| Lane | Sandbox | Can | Cannot | Hands back |
|---|---|---|---|---|
| Author | `workspace-write` on its own tree | edit the brief's allowed paths; offline build, lint and non-fork tests; write the fork-run list (exact commands, environment, expected counts) | any network, loopback included (no RPC, no fork test, no local cache server); git metadata writes (`.git` is read-only: no add, commit or branch); system counters such as `sysctl`; temp files, which may be denied | the changed files in place, its own commit message file, the run records, the final line |
| Run | a lane with network, outside the author's sandbox, behind the gate wrapper | run the author lane's fork-run list through the read cache; capture evidence; commit the evidence on its own branch | rewrite history; broadcast to a live chain; run a heavy tool outside the wrapper | the evidence commits, the run records, the final line naming the commit |
| Lens | `read-only` | read the tree and the named sources; replay selftests, in memory when temp files are denied | write anything; network; git writes | a verdict, findings with exact rewrites, and how each selftest was run |

3. **The coordinator commits an author lane's work verbatim, with the lane's own message file.** It checks `git status --short` against the brief's allowed paths, stages exactly those paths and commits with `git commit -F <the lane's message file>`. It never edits the lane's files first; a fix is a new lane task. That commit is the implementation commit the landing check (`WORKING_RULES.md` rule 34) and the tracker line name.
4. **A published gate file.** A sandboxed lane cannot read the machine's counters, so the coordinator publishes the resource reading in one file the lanes can read: the time, the memory and disk readings, the heavy-process count, and OPEN or CLOSED. A reading older than its stated validity counts as CLOSED. The gate wrapper (`WORKING_RULES.md` rule 25) reads this file and takes the lock. A lane that cannot read it prints a distinct `GATE-UNREADABLE` line and stops; a denied probe is never read as open or as blocked.
5. **Never add a writable root.** §2's withdrawal binds every headless lane: `--add-dir <repo>/.git` (or any added root over git metadata) makes `.git/hooks` and `.git/config` lane-writable, and a hook planted there later runs unsandboxed in the coordinator's or the owner's git, with nothing of it in a PR diff. It was nearly repeated in 2026-11: a `.git` root was added to a headless lane's launch so that the lane could commit. It was caught against this page, the lanes were relaunched with none, and the hooks and config were checked untouched; no write occurred. The answer is item 3, never a wider sandbox, and the dispatch script refuses any added root.
6. **Lens lanes replay selftests in memory when the sandbox denies temp files, and say so.** The verdict states for each selftest whether it ran as written, was replayed in memory (and how), or did not run. A lens never reports a run it did not do. The coordinator's own re-run of the selftest (`WORKING_RULES.md` rule 34) is the run of record.
7. **Homes and meters.** A lane runs in a home that only its own project has used: a home keeps a local memory database, and a mixed one reads another project's context into the lane. No agent copies or moves credential files; moving a home to another account is the owner's own login. A headless lane's limit reading (§7, §8) comes from the tool's own rate-limit record in the home's newest session log, never from memory.
8. **Wait and land by script.** Each headless dispatch gets a process-id watcher in the same turn (`WORKING_RULES.md` rule 33) and is landed only through the land check (rule 34). Lane state lives in one registry file that survives a coordinator restart, beside the lane-status file of §5.
