# BACKLOG

Review follow-ups. Each item is attached to the first roadmap item where it becomes relevant, so nothing waits "until the end".
Rule: when a PR touches the listed area, fix the item in the same PR and tick it here. Keep this file in `docs/`.

Status: `[ ]` open, `[x]` done. Priority: **High** = fix before merge or before the named phase, **Low** = nice to have.

## Blocking for PR A

| # | Item | Source | Priority | Status |
|---|---|---|---|---|
| A1 | `@theme` must be `@theme inline` for portal-driven colors, otherwise every portal renders admin colors. Add a test that builds the CSS and checks `bg-primary` references `--portal-primary`. | PR #3 review | High | [x] |

## Fix in PR B (components and forms)

| # | Item | Source | Priority | Status |
|---|---|---|---|---|
| B1 | CSRF for HTMX: `hx-headers` with `X-CSRFToken` on `<body>` in `base.html`. Test that an HTMX POST from a form works. | PR #3 | High | [x] |
| B2 | Load Chart.js only where a `ChartCard` renders (via `extra_scripts`), not on every page. | PR #3 | Low | [x] |
| B3 | `VENDOR_VERSIONS.md`: note Font Awesome icons are CC BY 4.0 (attribution kept in the file header). | PR #3 | Low | [x] |
| B4 | Exclude `*.md` from `ruff format` so the docs code blocks do not fail `format --check`. | PR #3 | Low | [x] |
| B5 | Escaping tests: text props (`Badge`, `DataTable` cells) are escaped; no `\|safe` or `mark_safe` outside `Component.render`. | PR B plan | High | [x] |
| B6 | `/dev/components/` returns 404 under prod settings and uses fake data only. | PR B plan | High | [x] |

## Fix in PR C (pages and menus)

| # | Item | Source | Priority | Status |
|---|---|---|---|---|
| C1 | Menu items with a missing URL name render as disabled `#`, never `NoReverseMatch`; a test lists unbuilt items. | PR B/C plan | High | [ ] |
| C2 | Menu and mixin filtering use plain attributes (`user.allowed_menus`, `institute.features`) until `SubAdminProfile` and `Plan` exist. | PR B/C plan | High | [ ] |

## Fix in roadmap 0.5 (tooling, Docker, CI)

| # | Item | Source | Priority | Status |
|---|---|---|---|---|
| T1 | Tailwind build script: detect architecture (not only `linux-x64`) and verify the downloaded binary's checksum. | PR #3 | Low | [ ] |
| T2 | Build the Tailwind CSS in Docker and CI (the built `app.css` is gitignored). | PR #3 | High | [ ] |
| T3 | Dev and CI on PostgreSQL (dev currently SQLite, prod Postgres). | PR #1 | High | [ ] |
| T4 | `.env` is not loaded by anything. Use `uv run --env-file .env`, or add a loader (needs approval). Remove the unused `DEBUG` line from `.env.example`. | PR #1 | Low | [ ] |

## Fix in Phase 1 (accounts and institutes), listed as roadmap 1.0

| # | Item | Source | Priority | Status |
|---|---|---|---|---|
| P1 | Base `TenantAdmin` that uses `unscoped` (default manager is fail-closed, so Django admin shows nothing for tenant models). | PR #2 | High | [ ] |
| P2 | `createsuperuser` creates `role=super_admin`; otherwise the developer account gets a 403. | PR #2 | High | [ ] |
| P3 | Authenticated users with no institute can still reach logout. | PR #2 | Low | [ ] |
| P4 | `Institute.is_active`; `TenantMiddleware` returns 403 for an inactive institute. | PR #2 | High | [ ] |
| P5 | Rename `_is_super_admin` and `_user_institute_id` to public names. | PR #2 | Low | [ ] |
| P6 | PROTECT blocks deleting an institute with data (test). | PR #2 | High | [x] in PR #3 |
| P7 | Anonymous user with an institute id gets nothing from `for_user` (test). | PR #2 | High | [x] in PR #3 |

## Later (deployment hardening, Phase 12)

| # | Item | Priority | Status |
|---|---|---|---|
| L1 | If a Content-Security-Policy is added, switch Alpine to its CSP-compatible build (the standard build needs `unsafe-eval`). | Low | [ ] |
| L2 | Off-site backup copy of production data before real students are on it. | High | [ ] |
| L3 | Check payment method for the chosen host (Render or Pethost) works from Pakistan before relying on it. | Low | [ ] |

## How this file is used

- After each PR review I add the new findings here, with the PR number.
- Each Cursor prompt names the backlog ids to fix in that PR (for example "also fix B1 to B6").
- A PR is not ready to merge if it touches an area with an open High item and does not fix it.
