# BACKLOG

Review follow-ups. Each item is attached to the first roadmap item where it becomes relevant, so nothing waits "until the end".
Rule: when a PR touches the listed area, fix the item in the same PR and tick it here. Keep this file in `docs/`.

Status: `[ ]` open, `[x]` done. Priority: **High** = fix before merge or before the named phase, **Low** = nice to have.

## Blocking for PR A

| # | Item | Source | Priority | Status |
|---|---|---|---|---|
| A1 | `@theme` must be `@theme inline` for portal-driven colors, otherwise every portal renders admin colors. Add a test that builds the CSS and checks `bg-primary` references `--portal-primary`. | PR #3 review | High | [x] on main |

## Fix in PR B (components and forms) - PR #4 review

| # | Item | Source | Priority | Status |
|---|---|---|---|---|
| B1 | CSRF for HTMX. **Reopened:** `app_shell.html` overrides `{% block body_attrs %}` and drops `hx-headers`, so every real portal page has no CSRF header (verified on the rendered gallery). Fix: put `hx-headers` on the `<body>` tag in `base.html` outside the overridable block (or use `{{ block.super }}` in the shell). Test must assert the **rendered** body tag has `hx-headers`, not just that the test client can send the header. | PR #4 | High | [ ] |
| B2 | Chart.js loads only with `ChartCard`. Done. Follow-up: the script tag repeats per card; load once per page. | PR #4 | Low | [x] (follow-up open) |
| B3 | `VENDOR_VERSIONS.md` notes Font Awesome icons are CC BY 4.0. | PR #3 | Low | [x] |
| B4 | `*.md` excluded from `ruff format`. | PR #3 | Low | [x] |
| B5 | Escaping tests. **Partial:** only `Badge` and `DataTable` are tested. Add one parametrized test that puts an XSS string in every text prop of every component (my probe: all 21 buildable ones escape correctly today). Add a guard test: no `\|safe` or `mark_safe` anywhere except `Component.render` and the crispy `whole_uni_form.html` (allowlist those two). | PR #4 | High | [ ] |
| B6 | `/dev/components/` returns 404 when `DEBUG=False`, fake data only. Done. | PR #4 | High | [x] |
| B7 | **New:** `TenantModelForm` accepts `institute` but never uses it: `save()` fails with `IntegrityError` on `institute_id` (verified). Set `instance.institute` for new objects and limit related choice fields to that institute. Test: saving creates the row in that institute and a form for institute A cannot select a B object. | PR #4 | High | [ ] |
| B8 | `ProgressBar`: coerce `value` to a number clamped 0 to 100 (it is interpolated into `style="width: ...%"`). | PR #4 | Low | [ ] |
| B9 | URL props (`Button`, `QuickAction`, `Tabs` `hx-get`, `SectionCard` link): reject `javascript:` and other unsafe schemes with a small `safe_url()` helper. | PR #4 | Low | [ ] |
| B10 | `CountdownCard` puts a value inside an Alpine expression string (`countdownCard('...')`), and `countdownCard` is not defined anywhere, so Alpine logs an error wherever the card renders. Use a `data-` attribute read by a defined Alpine component. Build it with roadmap 3.4 at the latest. | PR #4 | Medium | [ ] |

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
