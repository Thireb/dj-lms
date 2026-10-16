# CLAUDE.md

Put this file at the repo root, next to `AGENTS.md`.

@AGENTS.md

This project's coding rules live in `AGENTS.md` (imported above). Everything below is extra guidance for Claude Code.

## Role

- Claude Code **builds features and audits them**.
- Build one whole roadmap item per branch (for example 6.1), started from the latest `main`. Commit, but do not push. The user pushes and opens the PR.
- Do not wait for a merge. Start the next item on a new branch on top of the branch that waits (a stacked branch). If an item is bigger than about 10 files, split it into stacked branches in roadmap order; the owner approved this on 2026-10-16, so do not stop to ask which part comes first (AGENTS.md 8). If a lower branch changes in review, rebase the branches above it.
- One PR per phase (owner decision 2026-10-16). The part branches stay local. When a part is done and checked, merge it into the local phase branch `phase/<n>` with `git merge --no-ff <part>`, so each part stays one merge commit. The owner pushes `phase/<n>` and opens one PR. Run the full mutation check and the phase audit on `phase/<n>` before the handover.
- At the start of a phase, read its docs and send the owner one list of the doc gaps and decisions, so the build does not stop for questions later.
- Before handing over a branch, run the PR review procedure below on your own diff.
- With every branch, write the PR description from `.github/pull_request_template.md`. Always fill "Deviations from docs": each "(assumed)" choice, each doc gap, and each part left out on purpose. Write "None" only when there is none.
- A self-review is not independent. For larger PRs, the user also asks for a review in a fresh session.
- End every handover with the `gh` commands that push the branches and open the PRs, in stack order, each PR based on the branch below it (see "Handover commands").

## Read first

- `docs/BACKLOG.md` for open review items, `docs/ROADMAP.md` for build order.
- `docs/FEATURES.md`, `docs/ARCHITECTURE.md`, `docs/COMPONENTS.md`, `docs/UI-GUIDELINES.md`, `docs/SPEC-DETAILS.md` for the product rules.
- If code and docs disagree, report it. Do not silently pick one.

## Design skills (in the repo)

- `.claude/skills/` holds the design skills used for the Phase R redesign, pinned in `skills-lock.json`: `frontend-design` (Anthropic, Apache 2.0) and `ui-ux-pro-max` (MIT). Claude Code loads them for anyone who opens this repo.
- Use them for any UI work. The approved Lexicon direction in `UI-GUIDELINES.md` wins over their generic suggestions.
- They are excluded from ruff; do not edit them by hand. Update them from their source repos.

## Commands

- Tests, full suite: `uv run pytest -n auto` (parallel, about 40 s). While building, run only the files you changed: `uv run pytest tests/<app>/test_x.py`.
- The test database is kept between runs (`--reuse-db` in `pyproject.toml`). After switching to a branch with other migrations, add `--create-db` once.
- Mutation check while building: `uv run python scripts/mutation_check.py --changed` (only the entries for files changed since `origin/main`). Run the full check once at handover.
- Browser walk: `./scripts/browser-walk.sh` opens every portal page as its demo role at 360px and 1440px (status, sideways scroll, console errors, axe). `WALK_ONLY=teacher:quiz` walks some routes; `WALK_SHOTS=<dir>` saves screenshots. Add new pk routes to `OBJECTS` in `browser_walk/test_walk.py`.
- Lint: `uv run ruff check .`
- Format check: `uv run ruff format --check .`
- Build CSS (needed before UI tests): `./scripts/build-app-css.sh`

## PR review procedure

When asked to review a PR (use `gh pr view <n>` and `gh pr diff <n>`, or check out the branch):

1. Check scope: did the PR stay within the roadmap items and backlog ids it names? List anything extra.
2. Run pytest, ruff check and ruff format --check. Report exact results.
3. Mutation-test every fix: undo it, confirm a test fails, then restore it. A fix with no failing test is a gap. Run `uv run python scripts/mutation_check.py` (commit first: entries run on HEAD in throwaway worktrees, one per core minus 2, so the working tree stays free; `--jobs N` changes the count). Every entry must print CAUGHT. Add an entry for each new fix.
4. Probe real output, not only unit tests: render pages, check HTML, run the failing case by hand.
5. Security pass, in this order:
   - Tenant isolation: the manager must fail closed; no unscoped queries in views; `unscoped` only where `AGENTS.md` allows it.
   - Access control: every view declares `allowed_roles`; admin views use `MenuRequiredMixin`.
   - Output escaping: no `|safe` or `mark_safe` outside the two allowed places.
   - CSRF on HTMX requests, unsafe URL schemes, user input in attributes.
6. Check the PR description has an honest "Deviations from docs" section.
7. Report in three groups: **Verified**, **Must fix before merge**, **Can wait**.
8. Add new findings to `docs/BACKLOG.md` with the PR number. Mark fixed items done.

## Rules for reviews

- Never leave temporary probe files or edits behind. Run `git status` at the end and report if it is not clean.
- Do not merge, push, or approve PRs. Recommend only.
- Use fake data only. Never put real student data, credentials or secrets in files.
- Do not copy the reference product's name, logo, text or assets into any file.
- Be specific: file path, line, and a reproducible command for every finding.

## Writing style for reports

- Short, plain sentences. One-line bullets. No filler.
- Lead with the decision: merge, fix first, or blocked.

## Parallel sessions

- Each Claude Code session works in its own git worktree under `.claude/worktrees/<name>` (gitignored), never in another session's tree. Copy `static/css/app.css` into a new worktree (it is built, not in git).
- Each worktree uses its own test database: set `TEST_DB_NAME=lms_test_<name>` for every pytest run there. The mutation check and the browser walk already use their own.
- Do not use bare `git stash`: the stash is shared by all worktrees.

## Handover commands

At the end of a phase, give the owner one block for the phase branch (changed 2026-10-16: before, every part branch got its own PR):

```bash
git push -u origin phase/6
gh pr create --base main --head phase/6 --title "Phase 6: ..." --body-file <path to PR body>
```

The PR body lists each part with its summary and "Deviations from docs", then the phase checks and the audit. Merge it with a merge commit (not squash), so the part merge commits stay in the history.

A branch outside a phase (a fix or tooling) still gets its own block:

```bash
git push -u origin chore/x
gh pr create --base main --head chore/x --title "chore: ..." --body-file <path>
```

## Out of scope for now

- No Zoom, Google, WhatsApp or payment integrations. Manual meeting links only.
- Deployment (Pethost, Docker) is Phase 12. Do not set it up unless asked. Local dev and CI do not use Docker.
