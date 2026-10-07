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
| B1 | CSRF for HTMX. **Fixed (0.4c):** `PortalPageView.render_to_response` now passes `request` into shell `Component.render()` so `{{ csrf_token }}` in `base.html` is populated on portal pages. Tests in `tests/ui/test_portal_csrf.py` assert rendered `DemoTeacherDashboard` / `DemoAdminPeopleList` meta and body `hx-headers` match; HTMX POST with token passes, without header → 403. | PR #4 / 0.4c | High | [x] |
| B2 | Chart.js loads only with `ChartCard`. Done. Follow-up: the script tag repeats per card; load once per page. | PR #4 | Low | [x] (follow-up open) |
| B3 | `VENDOR_VERSIONS.md` notes Font Awesome icons are CC BY 4.0. | PR #3 | Low | [x] |
| B4 | `*.md` excluded from `ruff format`. | PR #3 | Low | [x] |
| B5 | Escaping tests. **Partial:** only `Badge` and `DataTable` are tested. Add one parametrized test that puts an XSS string in every text prop of every component (my probe: all 21 buildable ones escape correctly today). Add a guard test: no `\|safe` or `mark_safe` anywhere except `Component.render` and the crispy `whole_uni_form.html` (allowlist those two). | PR #4 | High | [x] on main |
| B6 | `/dev/components/` returns 404 when `DEBUG=False`, fake data only. Done. | PR #4 | High | [x] |
| B7 | **New:** `TenantModelForm` accepts `institute` but never uses it: `save()` fails with `IntegrityError` on `institute_id` (verified). Set `instance.institute` for new objects and limit related choice fields to that institute. Test: saving creates the row in that institute and a form for institute A cannot select a B object. | PR #4 | High | [x] on main |
| B8 | `ProgressBar`: coerce `value` to a number clamped 0 to 100 (it is interpolated into `style="width: ...%"`). | PR #4 | Low | [x] |
| B9 | URL props (`Button`, `QuickAction`, `Tabs` `hx-get`, `SectionCard` link, `CountdownCard` `meeting_link` - PR #6 review: `javascript:alert(1)` renders as the Join `href`): reject `javascript:` and other unsafe schemes with a small `safe_url()` helper. | PR #4 | Medium | [x] |
| B10 | `CountdownCard` puts a value inside an Alpine expression string (`countdownCard('...')`), and `countdownCard` is not defined anywhere, so Alpine logs an error wherever the card renders. Use a `data-` attribute read by a defined Alpine component. Build it with roadmap 3.4 at the latest. **PR #6:** injection closed (`x-data="countdownCard"` + `data-scheduled-at`, mutation-tested). | PR #4 | Medium | [x] in PR #6 |
| B11 | `CountdownCard` title escaping. **No actual bug:** the card never used `\|safe` and the title was already escaped (verified before PR #5). PR #5 passes `title` as a normal prop and adds a `<script>` title escaping test. | PR #4 | High | [x] in PR #5 |
| B12 | `scheduled_at_to_iso` calls `timezone.UTC`, which does not exist in Django 5.2 (`django.utils.timezone` has no `UTC`). Any naive datetime or offset-less string (`"2026-08-16 15:00"`) raises `AttributeError`, so the page 500s. Use `datetime.UTC`. Test: naive datetime and naive string both return a `+00:00` ISO string. | PR #6 | High | [x] in PR #6 |
| B13 | `scheduled_at_to_iso` lets `parse_datetime` raise `ValueError` on well-formed but impossible dates (`"2026-02-30T10:00:00"`, `"2026-13-01T10:00:00"`); the docstring and PR say invalid input returns `""`. Catch `ValueError`. Test both cases. | PR #6 | High | [x] in PR #6 |
| B14 | `scheduled_at_to_iso` keeps the input offset (`+05:00`) instead of converting to UTC; `ARCHITECTURE.md` section 9 says the `data-` attribute holds the UTC timestamp. Add `.astimezone(datetime.UTC)`. | PR #6 | Low | [x] in PR #6 |
| B15 | No test that `js/app.js` loads before Alpine in `base.html` (moving it after Alpine registers `countdownCard` too late; all tests still pass). No test runs `app.js` itself (removing the JS ISO check also passes). Add an order assertion; JS behaviour tests can wait for a JS test runner (needs approval). | PR #6 | Low | [x] order test in PR #6 (JS tests: B18) |
| B16 | `COMPONENTS.md` `CountdownCard` row: note that `scheduled_at` is rendered as a validated UTC ISO string in `data-scheduled-at` and read by `countdownCard` in `static/js/app.js`. List `static/js/app.js` in `ARCHITECTURE.md` layout. | PR #6 | Low | [x] |
| B17 | `scheduled_at_to_iso` raises `OverflowError` for a year-1 datetime with a positive offset (`"0001-01-01T00:00:00+01:00"` or an aware `datetime(1, 1, 1, tzinfo=+01:00)`): `astimezone(UTC)` goes below `datetime.min`, so the page 500s. Catch `OverflowError` with `ValueError` and return `""`. Test both inputs. Do with roadmap 3.4. | PR #6 | Low | [x] |
| B18 | No test runs `static/js/app.js` (removing the JS ISO check still passes). Add JS behaviour tests for `countdownCard` once a JS test runner is approved (new dependency, ask first). | PR #6 | Low | [ ] |

## Fix in PR C (pages and menus)

| # | Item | Source | Priority | Status |
|---|---|---|---|---|
| C1 | Menu items with a missing URL name render as disabled `#`, never `NoReverseMatch`; a test lists unbuilt items. | PR B/C plan | High | [x] |
| C2 | Menu and mixin filtering use plain attributes (`user.allowed_menus`, `institute.features`) until `SubAdminProfile` and `Plan` exist. | PR B/C plan | High | [x] |
| C3 | `MenuRequiredMixin` fail-closed: `sub_admin` on a view with no `menu_key` gets 403; admin portal pages without `menu_key` raise `ImproperlyConfigured` for institute admin paths. | PR #7 | High | [x] |
| C4 | Page and mixin access tests: each demo page allows only its roles; every other role plus anonymous gets 403; mutation-sensitive coverage for empty `allowed_roles` and missing tenant institute. | PR #7 / AGENTS.md §7 | High | [x] |
| C5 | Non-admin pages use `menu_key` for active-item highlighting (teacher `"dashboard"`, not a `core/menus.py` key). `COMPONENTS.md` says `menu_key` is admin only. Use a separate `active_item` attribute, or document it. | PR #7 | Low | [x] |
| C6 | Dead templates: `ui/layouts/pages/default.html` is never rendered (`build_page_body` falls back to `ListPageBody`), and `ui/layouts/portal_page.html` is a placeholder comment. Remove or use them. | PR #7 | Low | [x] |
| C7 | `FormPage` has no POST handling (POST returns 405) and builds `form_class()` without `institute`, so a `TenantModelForm` cannot save. Fix before the first real form page (roadmap 1.x). | PR #7 | High | [x] |
| C8 | Sign out menu items are plain links to `accounts:logout`. Django 5 `LogoutView` is POST-only, so the link will return 405 once the URL exists. Render Sign out as a POST form button with CSRF. Do with Phase 1 login. | PR #7 | Low | [x] |
| C9 | Anonymous users get 403 from page classes instead of a redirect to login. Redirect once the login URL exists (Phase 1). | PR #7 | Low | [x] |
| C10 | Access test gaps after the C3/C4 fix (PR #7, `04ed6fa`): no test covers a page that never sets `allowed_roles` (changing the default to all roles leaves all 132 tests passing; the empty-list test sets `[]` explicitly). `ImproperlyConfigured` for an admin page without `menu_key` only fires at request time; add a test that walks every `PortalPageView` subclass with `portal = "admin"` and asserts `menu_key` is a key in `core/menus.py`. The two `test_mutation_sensitive_*` tests duplicate the tests above them. | PR #7 | Low | [x] |
| C11 | Admin profile menu (Account settings, Toolbar settings, Default portal, Institute settings, Manage users, Manage permissions, Select currency, Appearance, Sign out) is not in the menu config. Admin-only items (Institute settings, Manage users, Manage permissions, Select currency) must render and route only for `institute_admin`, never for `sub_admin`. Do with roadmap 1.2 (campus profile and settings). | PR #7 | High | [x] |

## Fix in roadmap 0.5 (tooling, CI)

| # | Item | Source | Priority | Status |
|---|---|---|---|---|
| T1 | Tailwind build script: detect architecture (not only `linux-x64`) and verify the downloaded binary's checksum. | PR #3 | Low | [x] |
| T2 | Build Tailwind CSS in CI (the built `app.css` is gitignored). | PR #3 | High | [x] |
| T3 | Dev and CI on PostgreSQL (dev currently SQLite, prod Postgres). | PR #1 | High | [x] |
| T4 | `.env` is not loaded by anything. Use `uv run --env-file .env`, or add a loader (needs approval). Remove the unused `DEBUG` line from `.env.example`. | PR #1 | Low | [x] |

## Fix in Phase 1 (accounts and institutes), listed as roadmap 1.0

| # | Item | Source | Priority | Status |
|---|---|---|---|---|
| P1 | Base `TenantAdmin` that uses `unscoped` (default manager is fail-closed, so Django admin shows nothing for tenant models). | PR #2 | High | [x] |
| P2 | `createsuperuser` creates `role=super_admin`; otherwise the developer account gets a 403. Do in 1.1 with the User model. | PR #2 | High | [x] |
| P3 | Authenticated users with no institute can still reach logout. | PR #2 | Low | [x] |
| P4 | `Institute.is_active`; `TenantMiddleware` returns 403 for an inactive institute. | PR #2 | High | [x] |
| P5 | Rename `_is_super_admin` and `_user_institute_id` to public names. **PR #7:** `apps/core/mixins/access.py` now also imports `_is_super_admin` and `_user_role`; rename those too. | PR #2 | Low | [x] |
| P6 | PROTECT blocks deleting an institute with data (test). | PR #2 | High | [x] in PR #3 |
| P7 | Anonymous user with an institute id gets nothing from `for_user` (test). | PR #2 | High | [x] in PR #3 |

## Main audit 2026-10-06 (2)

| # | Item | Source | Priority | Status |
|---|---|---|---|---|
| N1 | Comment why `TenantModelForm` uses `model.unscoped` when limiting related choice querysets. | main audit | Low | [x] |
| N2 | `LogoutView.get` returns `HttpResponseNotAllowed(["POST"])`; test 405 and `Allow: POST`. | main audit | Low | [x] |
| N3 | Remove obsolete "Fix before roadmap 1.1c" backlog table (items already done). | main audit | Low | [x] |
| N4 | ROADMAP sub-item 1.1c; track N1–N4 and B17 in this table. | main audit | Low | [x] |
| N5 | No roadmap item built the seed data in `SPEC-DETAILS.md` section 10, so a demo had no data. Added `seed_demo` (Phase 1 part) and roadmap 2.8. | main audit | Low | [x] |
| N6 | Product admin portal uses URL namespace `admin` (`/admin/`); Django developer admin uses a separate `AdminSite` at `/django-admin/` so `reverse("admin:…")` resolves to portal routes. | main audit | Low | [x] |
| B17 | `scheduled_at_to_iso` catches `OverflowError` for year-1 datetimes with positive offset. | main audit / PR #6 | Low | [x] |

## Review 1.1c (PR #19 follow-ups)

| # | Item | Source | Priority | Status |
|---|---|---|---|---|
| F1 | Profile and change-password pages use `self_service=True` (no admin menu key); sub_admin without grantable menus still reaches them. | PR #19 | High | [x] |
| F2 | `admin_only=True` for institute-only admin pages; `ImproperlyConfigured` when misconfigured. | PR #19 | High | [x] |
| F3 | Change-password validation uses a non-dictionary password; failed validation leaves the old password unchanged. | PR #19 | Medium | [x] |
| F4 | Profile POST CSRF: GET exposes token; POST with checks succeeds, POST without → 403. | PR #19 | Medium | [x] |
| F5 | Profile save persists all four editable fields. | PR #19 | Medium | [x] |
| F6 | Invalid profile POST shows DB name, not tampered POST value. | PR #19 | Medium | [x] |
| F7 | Super admin profile uses the super portal shell (`data-portal="super"`). | PR #19 | Low | [x] |
| F8 | Test passwords are plain literals in `tests/conftest.py`; GitGuardian ignore narrowed to that file only. **PR #20 ticked this but did not change the code; done in the Phase 1 audit fix.** `.gitguardian.yaml` applies to the `ggshield` CLI only. The GitGuardian PR check ignores it and flagged `tests/conftest.py` on PR #21 (false positive, fake values). Stop PR alerts with an excluded path for `tests/` in the GitGuardian dashboard (manual, outside the repo). | PR #19 | Low | [x] |

## Review of Phase 1 (PR #20)

| # | Item | Source | Priority | Status |
|---|---|---|---|---|
| G1 | `seed_demo` had no `DEBUG` guard and created a super admin with a password readable in the repo. Now refuses when `DEBUG` is off, reads `SEED_DEMO_PASSWORD`, has `--reset`, uses the Premium plan. | PR #20 | High | [x] |
| G2 | `/super/institutes/<pk>/edit/` queried the database before the access check: unknown pk gave 500 for anonymous users and every role. Object now loads after the checks (404). | PR #20 | High | [x] |
| G3 | Superadmin role gates were untested and the URL walker was 7 fixed rows. `tests/core/test_url_access_walker.py` now walks every product URL: anonymous redirect, 403 for every other role, an allowed role gets through. | PR #20 | High | [x] |
| G4 | Basic plan held fees, homework, leave, lesson plans (Premium in `FEATURES.md`) and missed messaging. Basic is now messaging and time_zone_lectures (migration 0004). | PR #20 | High | [x] |
| G5 | Out-of-range institute settings gave 500 (check ran in the service after form validation). The form now shows the errors. | PR #20 | Medium | [x] |
| G6 | Create institute: existing admin email gave 500; invalid time zone was saved. Both rejected by the form. | PR #20 | Medium | [x] |
| G7 | Deactivate was a checkbox with no confirm. Now a POST confirm dialog (`ConfirmDialog` renders a real CSRF form) for activate and deactivate. | PR #20 | Medium | [x] |
| G8 | Set-password link went into the `messages` cookie as a path. Now shown once in the POST response as a full URL with a copy button (`CopyField`). | PR #20 | Medium | [x] |
| G9 | Roadmap 1.3 gaps: list search, 25 per page, status badge, user count, created date; create currency and admin name; edit time zone and currency. | PR #20 | Medium | [x] |
| G10 | PR #20 mutation table claimed coverage that did not exist. Added `scripts/mutation_check.py`; every entry must print CAUGHT. | PR #20 | Medium | [x] |
| G11 | Invalid campus POST changed `request.institute` in memory. Form binds a fresh copy. | PR #20 | Low | [x] |
| G12 | `InstituteSettings` created in two places; first admin got a random usable password. Signal only; unusable password. | PR #20 | Low | [x] |
| G13 | `FEATURES.md` ticked "Five logins" (sub-admin menus wait for 9.3c) and "symbol shown on all amounts" (no amounts yet). | PR #20 | Low | [x] |
| G14 | BACKLOG id N5 reused for another item; seed row and "Build order" rule missing. | PR #20 | Low | [x] |
| G15 | Wrong "unscoped" comment on the global `Institute` lookup in superadmin views. | PR #20 | Low | [x] |
| G16 | F3, F4 and F6 tests from PR #20 still passed with the fix undone (common-password check, CSRF token taken from the cookie, fresh instance). Tests now fail when each fix is undone. | Phase 1 audit | Medium | [x] |
| G17 | Super admin shell had no Sign out and no My profile. Added an Account group. | Phase 1 audit | Low | [x] |

## Main audit 2026-10-06 (fixed in PR #14, follow-ups from its review)

| # | Item | Source | Priority | Status |
|---|---|---|---|---|
| M1 | `TenantModelForm` let a form with `institute` in `Meta.fields` list every institute and move an existing row to another institute. Fixed: field stripped, `clean()` rejects another institute's instance, `save()` forces `self.institute`. | main audit | High | [x] in PR #14 |
| M2 | Users of an inactive or missing institute got 403 on logout. Fixed: logout is checked before the institute checks. | main audit | Low | [x] in PR #14 |
| M3 | `TenantAdmin` showed every institute's rows to any `is_staff` user. Fixed for module, view and change. | main audit | Medium | [x] in PR #14 |
| M4 | `TenantAdmin` still allows add and delete for a non-super-admin: `has_add_permission` and `has_delete_permission` fall back to Django perms, so an `is_superuser` user with `role=institute_admin` gets `True` for both (verified). Override both to require `user_is_super_admin`. Test both. Do with 1.1, since `createsuperuser` and real users arrive there. | PR #14 | High | [x] |
| M5 | `test_tenant_admin_changelist_forbidden_for_staff_non_super_admin` passes without the fix: the 403 comes from `TenantMiddleware` (a plain `auth.User` has no institute), not from `TenantAdmin`. Rewrite it with a user that passes the middleware once the 1.1 `User` model exists. | PR #14 | Low | [x] |
| M6 | Plan flags only hide menu items (`apps/ui/menus/registry.py`). Views do not enforce them, so a premium URL still opens when the flag is off. Add `requires_feature` / a `feature_key` mixin as in `ARCHITECTURE.md` (access layer 3); test the flag on and off. Do with 1.2 (Plan and feature flags) at the latest. | main audit | High | [x] |

## Review of 1.1a/1.1b (PR #15, PR #16)

| # | Item | Source | Priority | Status |
|---|---|---|---|---|
| R1 | Sign-in and set-password pages cannot be used in a browser. Rendered HTML: (a) every field is escaped text, because `Section.render` / `Row.render` in `apps/ui/forms/layout.py` join `SafeString`s with `"".join(...)`, which returns a plain `str` (a latent bug since PR #4); (b) the legend prints `None`; (c) there is no `<form>` tag (`helper.form_tag = False`, nothing wraps it); (d) no CSRF token, because `CrispyForm` is rendered inside `SectionCard` without `request`. Tests only POST directly, so all pass. Pass the parts as a list and loop in the template (no `mark_safe`); `{% if legend %}`; let public forms render their own `<form method="post">`; render nested components with `request`. Test: GET the page, parse the token, POST with `Client(enforce_csrf_checks=True)`, and assert `<input ... name="password">` is not escaped. | PR #16 | High | [x] fixed in PR #17 |
| R2 | Post-login redirect is broken. Teacher, student and guardian go to `/accounts/logout/` (the only resolvable menu item; GET returns 405). `institute_admin` and `sub_admin` go to `/accounts/login/`, which redirects an authenticated user to itself: an infinite loop (verified). `_first_menu_url` must skip `post_only` items, and the fallback must never be the login URL for an authenticated user. Add a minimal per-portal home page (or one signed-in page with Sign out) until dashboards exist. Test every role. | PR #16 | High | [x] fixed in PR #17 |
| R3 | `password_input.html` has no static `type="password"`, only Alpine `:type`. Until Alpine loads, or with JS off, the password shows as plain text. Add `type="password"` and keep `:type`. | PR #16 | Medium | [x] fixed in PR #17 |
| R4 | `/django-admin/` is open to any `is_staff` user whatever their role. A teacher with `is_staff` and `is_superuser` gets 200 on `/django-admin/accounts/user/` and sees every institute's users (verified). Gate `AdminSite.has_permission` (or `UserAdmin` permissions) to `user_is_super_admin`, and make `User.clean()` reject `is_staff` / `is_superuser` for every other role (`ARCHITECTURE.md`: these flags are for developers only). | PR #15 | High | [x] fixed in PR #17 |
| R5 | Docs: the `FEATURES.md` section 1 sign-in boxes are ticked, but sign-in does not work (R1, R2). Untick them until fixed. `CrispyForm`, `BlockStack`, `PublicFormShell` and `PasswordInput` are missing from `COMPONENTS.md` (AGENTS.md section 5 requires the table row). | PR #16 | Medium | [x] fixed in PR #17 |
| R6 | 4 new pytest warnings: `{% csrf_token %} was used in a template, but the context did not provide the value` (`tests/ui/test_dev_components.py`). Same root cause as R1(d). AGENTS.md section 9: no new warnings. | PR #16 | Low | [x] fixed in PR #17 |
| R7 | `SetPasswordToken.key` is stored in plain text, so anyone who reads the database can take over every account with an unused token. Store a SHA-256 hash and look up by hash. | PR #16 | Medium | [x] fixed in PR #18 |
| R8 | Users of an inactive institute can sign in, then get 403 on every page. Reject them at login with a clear message. | PR #16 | Low | [x] fixed in PR #18 |
| R9 | Test gaps (mutation): removing `validate_password` from `SetPasswordForm` passes all tests; reverting the top-nav POST Sign out (C8) passes all tests. The set-password field should use `autocomplete="new-password"`. | PR #16 | Low | [x] fixed in PR #17 |

## Build of 2.3 (academics)

| # | Item | Source | Priority | Status |
|---|---|---|---|---|
| S1 | Flash messages were never shown: no template rendered `messages`, so "Campus profile updated.", "Institute saved." and every other `messages.success` call was lost. Fixed: both shells render one `Toast` per message; toast tones use theme colors. | 2.3b build | Medium | [x] |
| S2 | `ListPageBody`, `DataTable` and `BlockStack` rendered nested components without `request`, so a `ConfirmDialog` in a table row had no CSRF token and its POST got 403. Fixed with `render_child`; test posts with `enforce_csrf_checks=True`. | 2.3b build | High | [x] |
| S3 | `badge-tone-*` classes (used by `Badge`) have no CSS, so status badges show no color. Map each tone to theme token classes in `badge.html`, as `toast.html` now does. | 2.3b build | Low | [ ] |
| S4 | `static/css/src/input.css` `@source` paths start with `../../../../`, which is outside the repo. Classes are still found by Tailwind's automatic detection. Fix the paths to `../../../`. | 2.3b build | Low | [ ] |
| S5 | `apps/institutes/urls/admin.py` is not included anywhere; admin URLs live in `apps/ui/urlconf/admin.py`. Delete it or include it. | 2.3b build | Low | [ ] |
| S6 | The URL walker only checked roles outside `allowed_roles`, so adding `Role.TEACHER` to an admin page passed every test (found by the 2.5a mutation check). Fixed: the walker now asserts admin portal views allow only `institute_admin` and `sub_admin`. | 2.5a build | Medium | [x] |

## Later (deployment hardening, Phase 12)

| # | Item | Priority | Status |
|---|---|---|---|
| L1 | If a Content-Security-Policy is added, switch Alpine to its CSP-compatible build (the standard build needs `unsafe-eval`). | Low | [ ] |
| L2 | Off-site backup copy of production data before real students are on it. | High | [ ] |
| L3 | Check that Pethost payment works from Pakistan before relying on it. Ask Pethost whether PostgreSQL and Redis are offered. | Low | [ ] |

## How this file is used

- After each PR review I add the new findings here, with the PR number.
- Each Cursor prompt names the backlog ids to fix in that PR (for example "also fix B1 to B6").
- A PR is not ready to merge if it touches an area with an open High item and does not fix it.
