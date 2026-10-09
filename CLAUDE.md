# CLAUDE.md

Put this file at the repo root, next to `AGENTS.md`.

@AGENTS.md

This project's coding rules live in `AGENTS.md` (imported above). Everything below is extra guidance for Claude Code.

## Role

- Claude Code **builds features and audits them**.
- Build one roadmap item per branch, started from the latest `main`. Commit, but do not push. The user pushes and opens the PR.
- Before handing over a branch, run the PR review procedure below on your own diff.
- A self-review is not independent. For larger PRs, the user also asks for a review in a fresh session.

## Read first

- `docs/BACKLOG.md` for open review items, `docs/ROADMAP.md` for build order.
- `docs/FEATURES.md`, `docs/ARCHITECTURE.md`, `docs/COMPONENTS.md`, `docs/UI-GUIDELINES.md`, `docs/SPEC-DETAILS.md` for the product rules.
- If code and docs disagree, report it. Do not silently pick one.

## Design skills (in the repo)

- `.claude/skills/` holds the design skills used for the Phase R redesign, pinned in `skills-lock.json`: `frontend-design` (Anthropic, Apache 2.0) and `ui-ux-pro-max` (MIT). Claude Code loads them for anyone who opens this repo.
- Use them for any UI work. The approved Lexicon direction in `UI-GUIDELINES.md` wins over their generic suggestions.
- They are excluded from ruff; do not edit them by hand. Update them from their source repos.

## Commands

- Tests: `uv run pytest`
- Lint: `uv run ruff check .`
- Format check: `uv run ruff format --check .`
- Build CSS (needed before UI tests): `./scripts/build-app-css.sh`

## PR review procedure

When asked to review a PR (use `gh pr view <n>` and `gh pr diff <n>`, or check out the branch):

1. Check scope: did the PR stay within the roadmap items and backlog ids it names? List anything extra.
2. Run pytest, ruff check and ruff format --check. Report exact results.
3. Mutation-test every fix: undo it, confirm a test fails, then restore it. A fix with no failing test is a gap. Run `uv run python scripts/mutation_check.py` (commit first; it restores files with `git checkout`); every entry must print CAUGHT. Add an entry for each new fix.
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

## Out of scope for now

- No Zoom, Google, WhatsApp or payment integrations. Manual meeting links only.
- Deployment (Pethost, Docker) is Phase 12. Do not set it up unless asked. Local dev and CI do not use Docker.
