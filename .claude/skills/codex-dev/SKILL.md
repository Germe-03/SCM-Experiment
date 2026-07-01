---
name: codex-dev
description: Use this whenever code needs to be written or changed in the SCM-Experiment / supplychainbench project (agent.py policies under team_bundle/, tests, manifest.json, etc). In this project, Claude does not write code directly — Claude drives the Codex CLI (`codex exec`) from the terminal to produce the actual code changes, then reviews the diff, runs validation, and reports back. Trigger this for any request to implement, change, fix, or tune a retailer/wholesaler/distributor/factory policy, or any other source change in this repo.
---

# Codex-Dev: Claude drives Codex for this repo

This project's ground rule: **Codex writes the code, Claude operates Codex.**
Don't write or edit `team_bundle/**` files directly with the Edit/Write tools.
Instead, delegate the implementation to the `codex` CLI as a subprocess, then
verify the result.

## Why this workflow

The user explicitly asked for this split: Claude plans, prompts, and verifies;
Codex is the one that produces the code. Treat every code-writing task in this
repo as "compose a good prompt for Codex, run it, check the outcome" rather
than editing files yourself.

## Preconditions (check once per session)

- `codex --version` should succeed (Codex CLI is installed globally via npm).
- `codex doctor` shows `auth is configured` — if not, tell the user auth needs
  to be set up (`codex login`) before anything else can run.
- The repo at `C:\Users\david\PycharmProjects\SCM-Experiment` is a git repo —
  always work with a clean-ish tree so Codex's diff is easy to review
  (`git status` before and after).
- Validation requires Python + the `supplychainbench` package
  (`supplychainbench test-bundle .` from `team_bundle/`). If `python`/`pip`
  aren't available, flag that to the user before promising test results —
  don't silently skip validation.

## Core command

Run Codex non-interactively, scoped to the repo, allowed to write files but
not to touch anything outside the workspace or reach the network beyond what
it needs. **Feed the prompt via a file on stdin and run in the background with
a log file** (see "Running Codex reliably" below for why):

```bash
# Write the prompt to a file first (avoids shell-quoting hell), then:
codex exec -C "C:\Users\david\PycharmProjects\SCM-Experiment" \
  -s workspace-write \
  -c model_reasoning_effort="medium" \
  --skip-git-repo-check \
  -o "<scratch>/codex_last.txt" \
  < "<scratch>/prompt.txt" \
  > "<scratch>/codex_log.txt" 2>&1
```

- `-C <dir>` sets Codex's working root — always point it at the repo (or a
  subfolder like `team_bundle/retailer` for a tightly scoped task).
- `-s workspace-write` lets it edit files and run commands inside that dir,
  but keeps it out of `danger-full-access`. Use `-s read-only` for
  investigation-only prompts (e.g. "explain how X works") where nothing
  should change.
- `-c model_reasoning_effort="medium"` — **important.** The user's global
  `~/.codex/config.toml` defaults to `xhigh`, which made a trivial scaffolding
  task idle/stall for *hours*. Use `medium` for normal coding, `low` for
  pure boilerplate; reserve `high`/`xhigh` for genuinely hard design work.
- Never add `--dangerously-bypass-approvals-and-sandbox` — `workspace-write`
  is enough for this project.
- `-o last_message.txt` captures Codex's final summary; parse it to confirm
  what it thinks it did (then verify independently with `git diff`).

## Running Codex reliably (hard-won lessons)

1. **Redirect stdin from a file (`< prompt.txt`).** In `exec` mode Codex reads
   stdin; when launched detached/in-background with an *open* stdin it prints
   "Reading additional input from stdin..." and **hangs forever** waiting for
   EOF. Passing the prompt as a positional arg is not enough — still redirect
   stdin (from the prompt file, or `/dev/null`). A file gives clean EOF.
2. **Never pipe the run through `tail`/`head`.** `tail` buffers until EOF, so
   the output file stays empty and you can't tell a working run from a hung
   one. Redirect straight to a log file (`> log.txt 2>&1`) so it streams live.
3. **Run in the background and monitor the log**, not the harness task file.
   Confirm the run actually started by checking the log has the Codex banner
   and a fresh `session id` within ~30s. A new rollout appears under
   `~/.codex/sessions/<date>/`; no rollout after a minute = it never started.
4. **If a run hangs, kill only your CLI process.** The npm CLI is
   `codex.exe` under `AppData\Roaming\npm\...`; the user also runs the **Codex
   Desktop App** (`WindowsApps\OpenAI.Codex\...\Codex.exe`) — never kill those.
   Identify by parent/path via `Get-CimInstance Win32_Process -Filter
   "Name='codex.exe'"` and `taskkill /PID <pid> /T /F` the CLI one.
5. **Verify independently.** Re-run the tests yourself with the venv
   (`.venv\Scripts\python.exe -m pytest ...`) rather than trusting Codex's
   summary alone.

## Workflow for a code-change request

1. **Scope the ask.** Figure out which tier(s)/file(s) are in play (e.g. "tune
   the wholesaler policy" → `team_bundle/wholesaler/agent.py` +
   `team_bundle/wholesaler/agent.yaml`). Skim the relevant
   `walkthrough_<tier>.md` in the repo root first — it has the contract,
   gotchas, and concrete policy ideas for that tier. Bring that context into
   the Codex prompt; don't make Codex rediscover it.
2. **Check git status** before running, so you can cleanly attribute the diff
   to this run.
3. **Write a specific, self-contained prompt** for Codex — it has no memory of
   this conversation. Include:
   - the exact file(s) to change
   - the constraints from `team_bundle/README.md` (only edit `step()` bodies
     and `agent.yaml` memory settings; don't import the instructor's
     `supplychainbench_v2.starters.*` reference implementations; don't reach
     outside `LocalObservation`)
   - the desired policy behavior in plain terms
   - an instruction to run `supplychainbench test-bundle .` from
     `team_bundle/` afterwards if the tool is available, and fix failures
     before finishing
4. **Run it**: `codex exec -C <repo> -s workspace-write "<prompt>"`.
5. **Review the diff yourself**: `git diff` (or `git diff --stat` first for a
   quick overview). Read the actual changed code — don't just trust Codex's
   own summary. Check it against the tier's contract (no forbidden imports,
   respects `memory_mode`, etc).
6. **Report to the user**: what changed, why, and the validation result. If
   `supplychainbench test-bundle .` isn't runnable (e.g. Python missing), say
   so explicitly rather than claiming it passed.

## Example prompts to Codex

Scoped, single-tier tuning:
```
In team_bundle/wholesaler/agent.py, replace the Mirror step() policy with a
base-stock policy: target_position = 24, order_qty =
max(0, target_position - (inventory_on_hand + pipeline_inventory - backlog)).
Keep it stateless (memory_mode: stateless in agent.yaml, already set).
Don't import from supplychainbench_v2.starters. Then run
`supplychainbench test-bundle .` from team_bundle/ and fix any failures.
```

Manifest/setup task:
```
Fill in team_bundle/manifest.json: set team_id to "scm-experiment" and
team_name to "SCM Experiment". Leave sdk_version and the agents mapping as-is.
```

## Iterating

If the user wants changes after reviewing, don't hand-edit — go back to
Codex with a follow-up prompt describing what's wrong, scoped to the same
files. Keep the loop: prompt → `codex exec` → `git diff` review → report.
