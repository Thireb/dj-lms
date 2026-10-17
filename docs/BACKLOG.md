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
| S3 | `badge-tone-*` classes (used by `Badge`) have no CSS, so status badges show no color. Map each tone to theme token classes in `badge.html`, as `toast.html` now does. | 2.3b build | Low | [x] fixed in 2.4 |
| S4 | `static/css/src/input.css` `@source` paths start with `../../../../`, which is outside the repo. Classes are still found by Tailwind's automatic detection. Fix the paths to `../../../`. | 2.3b build | Low | [x] fixed in Phase 2 audit |
| S5 | `apps/institutes/urls/admin.py` is not included anywhere; admin URLs live in `apps/ui/urlconf/admin.py`. Delete it or include it. | 2.3b build | Low | [x] fixed in Phase 2 audit |
| S6 | The URL walker only checked roles outside `allowed_roles`, so adding `Role.TEACHER` to an admin page passed every test (found by the 2.5a mutation check). Fixed: the walker now asserts admin portal views allow only `institute_admin` and `sub_admin`. | 2.5a build | Medium | [x] |
| S7 | `DetailPageBody` rendered its cards without `request`, so a form inside a card had no CSRF token (same cause as S2). Fixed with `render_child`; test added. | 2.6 build | Medium | [x] |
| S8 | Bulk upload runs in the web request: about 0.55 s of password hashing per row, so files were capped at 50 rows; the Phase 2 audit (H6) lowered the cap to 15 and set the gunicorn timeout to 120 s in DEPLOYMENT.md. Move the import to a Celery task when Celery arrives (roadmap 3.2), then raise the cap. Celery is set up in 3.2; the move is its own branch (it needs a progress page). | 2.6 build | Low | [ ] |
| S9 | Automatic defaulter blocking (SPEC 6.2) is not part of 2.7: it needs challans and overdue data from Phase 7. Build it as roadmap 7.6 on top of the 2.7 block and exempt fields; manual block and unblock must still win until the next run. Done in 7.6 (Phase 7 PR). | 2.4 planning | High | [x] |
| S10 | Layout forms never showed non-field errors (`whole_uni_form.html`), so "Passwords do not match." and service errors mapped to the whole form were hidden. Fixed; test added. | Phase 2 audit | Medium | [x] |

## Phase 2 audit (external review, fixed in one PR)

| # | Item | Priority | Status |
|---|---|---|---|
| H1 | No sign-in throttling on login, developer admin login and set-password. Now 5 failures per 15 minutes per lower-cased email and IP (set-password per IP); a locked attempt never hashes a password; IP from `TRUSTED_PROXY_IP_HEADER` only when set. | High | [x] |
| H2 | Email case: `Sam@example.com` could not sign in as `sam@example.com`, and case duplicates were possible. Emails are lower-cased on save and sign-in, `Lower(email)` unique constraint, data migration. | High | [x] |
| H3 | Sidebar took 224 of 360px on phones. Hidden below md with a Menu button and a full-screen panel. | High | [x] |
| H4 | Admin top menu always open (508px desktop, 1,636px phone); sideways scroll on dashboard and upload. Groups are dropdowns, a collapsible list on phones; main and fieldsets are `min-w-0`; inputs are full width. 0px overflow at 360px on every page (headless Chromium). | High | [x] |
| H5 | A 5 KB .xlsx with a cell at row 1,048,576 took 7-11 s of CPU. The reader scans at most 1,000 rows, stops after 5 s, and refuses files over 20 MB unpacked. | High | [x] |
| H6 | A 50-row import outlived a 30 s worker. Cap 15 rows; gunicorn `--timeout 120` in DEPLOYMENT.md (S8 moves it to Celery). | High | [x] |
| M1 | A damaged .xlsx gave a 500 (ParseError). Every read error is now "not a valid .xlsx workbook". | Medium | [x] |
| M2 | A lost set-password link locked out the institute admin. `manage.py make_set_password_link` and a "New sign-in link" action on the super admin institute page; older unused links stop working. | Medium | [x] |
| M3 | `?batch=²`, `?q=%00` and a 5,000-digit id gave a 500 on the lists. `id_param` and `search_param` in `apps/core/query.py`. | Medium | [x] |
| M4 | The preview said Ready for rows the import rejected (field lengths). The check runs the model field checks and names the column. | Medium | [x] |
| M5 | Cell clean-up changed passwords and dropped a phone's leading 0. Passwords are kept as typed; template cells are Text; a phone typed as a number is an error. | Medium | [x] |
| M6 | Passwords were readable in the signed hidden field. Rows stay in the session; the page gets a random id. | Medium | [x] |
| M7 | Production gaps: `SECURE_PROXY_SSL_HEADER`, WhiteNoise, `/health/`. Logged as S11-S13; DEPLOYMENT.md marks them not built. | Medium | [x] logged |
| M8 | The page that shows a one-time link had no `Cache-Control: no-store`. Added (create institute, new sign-in link). | Medium | [x] |
| M9 | Sub-admins have no `allowed_menus` until 9.3c (logged as S15). The dashboard now shows recent students and teachers only with the People menu. | Medium | [x] |
| L1 | A user of an inactive institute got a bare 403. Now a page with the reason and Sign out. | Low | [x] |
| L2 | Without remember me the server session lasted 14 days. Now 12 hours (remember me: 14 days). | Low | [x] |
| L3 | Password fields stripped spaces. `strip=False` on every password field. | Low | [x] |
| L4 | `safe_url` repaired inner spaces and allowed `//host` and `/\host`. It now refuses them. | Low | [x] |
| L5 | Profile status was editable in the developer admin. Read-only. | Low | [x] |
| L6 | No `[x-cloak]` CSS rule. Added. | Low | [x] |
| L7 | `/` returned 404. It redirects to sign-in or the user's portal. | Low | [x] |
| L8 | `create_user(role="super_admin")` set `is_staff=False`. Now `True` by default. | Low | [x] |
| L9 | Set-password token use was not atomic. `select_for_update` in a transaction; a second use shows "already used". | Low | [x] |
| L10 | Set-password did not compare the password with the user's email. It does now. | Low | [x] |
| L11 | COMPONENTS.md was stale (render signature, shell_class, sorting, HTMX). Updated. | Low | [x] |
| L12 | Components built ahead and not used by a page yet are listed in COMPONENTS.md section 7. | Low | [x] |

Claims the audit tested that did not hold: overlong cells do not give a 500 on import (they fail per row, now caught in the check by M4); formula injection does not apply (nothing is exported); the XML parser has no `defusedxml`, but no attack worked against Python 3.13's expat limits (logged as S16, defense in depth).

## Open after the Phase 2 audit

| # | Item | Source | Priority | Status |
|---|---|---|---|---|
| S11 | `SECURE_PROXY_SSL_HEADER` is not set; behind a TLS proxy `SECURE_SSL_REDIRECT` would loop. Set it with the proxy setup. Fixed: `TRUSTED_PROXY_SSL_HEADER` names the proxy's scheme header (for example `HTTP_X_FORWARDED_PROTO`); a wrong name stops the start. | Phase 2 audit M7 | High before deploy | [x] |
| S12 | WhiteNoise is not installed, so static files do not load with `DEBUG=False`. New dependency (ask first). | Phase 2 audit M7 | High before deploy | [ ] |
| S13 | No `/health/` route for the uptime check. Fixed: `/health/` checks the database (200 or 503, no details), open to everyone, not cached, not redirected to https. | Phase 2 audit M7 | High before deploy | [x] |
| S14 | The sign-in limits need one shared cache; `prod.py` uses Redis when `REDIS_URL` is set, but the `redis` package is not installed (new dependency, ask first). Fixed in 3.2: `redis` and `celery` added with the owner's approval. | Phase 2 audit H1 | High before deploy | [x] |
| S15 | Sub-admins have no `allowed_menus` until 9.3c, so `demo-sub` gets 403 on every admin page. 9.3c must add the field, the seed grants (Finance and People per SPEC 10) and tests; the dashboard already hides people names without People. Also closes P7-4: test that a sub-admin with Finance gets the fee notices. | Phase 2 audit M9 | Medium | [ ] |
| S16 | openpyxl parses XML without `defusedxml`. No attack worked against Python 3.13's expat limits; add `defusedxml` as defense in depth when dependencies are next reviewed. | Phase 2 audit | Low | [ ] |
| S17 | No automated browser test: the 360px layout was checked once with headless Chromium. Add one with the JS test runner (B18). Partly done 2026-10-16: `./scripts/browser-walk.sh` opens every portal page at 360px and 1440px (status, sideways scroll, console errors, axe) and runs at each handover. It is not in CI yet (it needs Chromium and loads axe from a CDN). | Phase 2 audit | Low | [ ] |
| S18 | The notification bell in the admin top bar was a near-black icon on the dark bar (rgb(12,27,31) on rgb(0,48,61)), so it looked cut off in the Phase 2 walkthrough video. The bell now inherits the bar's light text colour, and its hover uses `bg-primary/20` instead of the light `bg-page`. Checked in Chromium at 1280px and 390px. | Phase 2 walkthrough | Low | [x] |

## Redesign audit (after R4c, fixed before Phase 3)

The audit called these L1-L8; renamed RA1-RA8 because L1-L12 are already used above.

| # | Item | Priority | Status |
|---|---|---|---|
| RA1 | No styled error pages: a 403 was the bare text "Forbidden." and a 404 the plain Django page. `handler403/404/500` and the access mixins now return a Lexicon notice page (icon, what happened, "Go to my home page"). | Low | [x] |
| RA2 | Esc and a click outside did not close the admin Menu list (below 1280px). Both close it now. | Low | [x] |
| RA3 | "View all" on the dashboard cards was 49x20px. It is now at least 32px tall with padding. | Low | [x] |
| RA4 | Checkboxes were a 20px target. The whole row is one label, 40px tall. | Low | [x] |
| RA5 | The logo link's `aria-label="LEXICON home"` did not match its visible text (axe label-content-name-mismatch). The label is gone; the name is the visible "LEXICON" plus a screen-reader-only "home". | Low | [x] |
| RA6 | The sign-in panel promised live classes, homework and challans, which do not exist yet. It now lists what exists and says the rest is coming. | Low | [x] |
| RA7 | No `/health/` route. Already S13 (Phase 12). Fixed with S13. | High before deploy | [x] |
| RA8 | No query-count tests. `tests/people/test_dashboard_queries.py` sets a budget per dashboard (admin 13, teacher 7, student 7, guardian 8) with more people than the pages list, so an N+1 query fails it. | Low | [x] |

## Build of 3.1 (lectures)

Left out of 3.1 on purpose; each has a home in a later item.

| # | Item | Priority | Status |
|---|---|---|---|
| LC1 | All lectures has no date-range filter yet (SPEC 3 lists one). The Today, Upcoming, Past and All tabs and the teacher, batch, subject and status filters are built. Add the range with the schedule views (3.3). Fixed in 3.3: From and To date fields (days in the viewer's zone, both included). | Low | [x] |
| LC2 | Row actions View and Cancel, and the teacher's Start, Whiteboard and Attendance, come with lecture states (3.5), the whiteboard and attendance (4.1). 3.1 has Edit and "Open meeting link". 3.5 adds View, Cancel (admin) and Start class (teacher). 4.1 adds Attendance (finished lectures). Only Whiteboard stays open; it comes with the ROADMAP "Live whiteboard" item (feature key `whiteboard`). | Low | [ ] |
| LC3 | `seed_demo` has no lectures yet. Fixed in 3.2: a Mon/Wed/Fri schedule and two single lectures for `demo-teacher@`. Past and live demo lectures need lecture states (LC5). | Low | [x] |
| LC5 | Past, live and finished demo lectures (SPEC 13) come with lecture states (3.5); the services refuse a start in the past. Fixed in 3.5: three finished lectures from last week and one live lecture for `demo-teacher@`. | Low | [x] |
| LC4 | The admin dashboard "lectures today" number and the teacher home lecture count and up-next countdown come with 3.4. Fixed in 3.4. | Low | [x] |
| LC6 | Student and guardian lists have no Join column and no meeting link yet. Join and its states (SPEC 6.4) come with 3.4 and 3.5. Fixed in 3.4: the Join column and the join view; Join becomes possible when 3.5 lets the teacher start. | Low | [x] |
| LC7 | The guardian picks a child with a filter on "Lectures schedule". The header child switcher that every guardian page follows (UI-GUIDELINES) is not built yet; build it before the next guardian list (Phase 4 attendance) and move this filter to it. Fixed in 4.2: `ChildSwitcher` in the guardian top bar (`GuardianChildMixin`, session key `guardian_child_id`); "Lectures schedule", "Class attendance" and the home follow it; the Child filter is gone. | Medium | [x] |
| LC8 | `ScheduleList` and `LectureRow` are still the stub components from PR B; 3.3 used `Calendar` and `DataTable`. Use them in 3.4 (up-next and dashboards) or remove them. Fixed in 3.4: `LectureRow` is rebuilt for the guardian's upcoming classes; `ScheduleList` is removed (`Calendar` does its job). | Low | [x] |
| LC10 | Join does not record anything yet. Attendance from joins (SPEC 6.3, provider-based) comes with Phase 4; the join view is the place to log it. Phase 4 decision (owner approved 2026-10-14): not built. With manual meeting links a join is only a click and does not prove attendance; provider attendance stays with the meeting provider work (`MeetingProvider.get_participants`). | Low | [ ] |
| LC9 | A calendar entry opens only a scheduled lecture (its edit page). Finished and cancelled entries do not link until a lecture detail page exists (3.5). Fixed in 3.5: every entry opens the lecture page. | Low | [x] |
| LC11 | No notifications exist yet: there is no model or service, and the header bell (`NotificationBell`) always shows 0. The lecture events in SPEC 7 (created or changed, starts in 15 minutes, started, cancelled) are hooked in by roadmap 6.1 and 6.2. The lecture services (`create_lecture`, `update_lecture`, `start_lecture`, `cancel_lecture`) are the places to hook them. Fixed in 6.2: the lecture services send created or changed (a new time, length, teacher or link), started, cancelled and the schedule notices, and a 5-minute job sends "starts soon" 15 minutes before. | Low | [x] |
| LC12 | Admin Lectures dashboard / Live lecture monitor (FEATURES 5, SPEC 8) is not built yet. It is roadmap 3.6. Fixed in 3.6, with a "Late start" list. | Low | [x] |
| LC13 | The Lectures dashboard has no "Teachers on leave today" (SPEC 8); it needs leave requests (roadmap 9.3). Its lists have no paging; a very large institute may need a limit. Limit fixed: each list shows its first 20 lectures, the title says "(20 of 57)" and "View all 57" opens All lectures with the matching filters; the cards keep the full counts. "Teachers on leave today" stays open for 9.3. | Low | [ ] |

## Phase 3 audit (2026-10-14, fixed in one PR)

Full review of roadmap 3.1 to 3.6 on `main` f1e5ff3: pytest 1620 passed, ruff clean, mutation check 380 caught; 28 pages opened as `demo-admin`, `demo-teacher`, `demo-student` and `demo-guardian` at 1440px and 360px (all 200, no sideways scroll, no console errors).

| # | Item | Priority | Status |
|---|---|---|---|
| P3-1 | A schedule edit remade the old date of a lecture moved on its own ("this one"), and the date it moved to lost its own lecture: the generator found taken dates from each lecture's current start. Lectures now keep `occurrence_date` (the schedule date they stand for); a data migration fills it for existing rows (a lecture already moved keeps its new date). Reproduced first, then fixed; test added. | Medium | [x] |
| P3-2 | `update_lecture` saved every field of the copy read at page load, so an edit saved just after Start, Cancel or the finish job set the status back to scheduled. Stop, edit, extend and the generator also used the schedule copy without a lock (a stop during the nightly run could still get lectures). Each now locks the row and reads it again before it checks and saves; tests added. | Medium | [x] |
| P3-3 | Demo: `demo-student` and `demo-guardian` saw no lectures, because the seed used the teacher's first batch and subject (Afternoon: Biology) and the demo student takes Afternoon: Physics. The seed now uses a pair the demo student takes; the seed test checks the student sees the live lecture. | Medium | [x] |
| P3-4 | The edit page of a finished or cancelled lecture, and the edit and extend pages of a stopped schedule, showed a form that could never be saved. They now go back (lecture page or schedule list) with the reason. | Low | [x] |
| P3-5 | No query budget for the lecture pages. Measured with 3 and 12 lectures (same counts, so no N+1); `tests/lectures/test_page_queries.py` now holds a budget for 10 pages. | Low | [x] |
| P3-6 | In dev, no beat runs while `CELERY_ALWAYS_EAGER=true`, so lectures past their end stay "Scheduled" and schedules are not extended nightly. README says so; DEPLOYMENT has a beat check. | Low | [x] |
| P3-7 | The finish job marked a lecture finished even when the teacher never pressed Start, so payroll (Phase 8) would pay a class that never took place. Owner decision 2026-10-14: a new state `not_held` (amber "Not held"). The job now makes a live lecture finished and a never-started one not held; payroll and attendance count only finished lectures, Lecture History lists only finished ones. A data migration moves existing finished lectures with no Start to not held. Demo seed has one. | Medium | [x] |
| P3-8 | Polling: "Up next" (teacher, student) and the Lectures dashboard reload every 30 seconds. About 8 queries each; at 1,000 open student homes that is about 33 requests a second. Fine for now; revisit with caching or a longer interval before large institutes. | Low | [ ] |
| P3-9 | Time zones with clock changes: a lecture or schedule time that does not exist on a spring-forward day (for example 01:30 in Europe/London) is saved as Django's `make_aware` reads it, without a warning. Pakistan has no clock changes; add a check when an institute in such a zone signs up. Fixed: the lecture form and the schedule check refuse such a time with the day and zone ("1:30 AM does not exist on Sun 28 Mar 2027 in Europe/London: the clocks go forward"); a time that happens twice uses the first one. | Low | [x] |

## External audit of Phase 3 (2026-10-14, after PR #49)

| # | Item | Priority | Status |
|---|---|---|---|
| X1 | Broker (Redis) down: `_enqueue` called `.delay()` in `on_commit` with no error handling, so a saved schedule showed an error page (a resubmit made a duplicate), and "Save and update lectures" left the upcoming lectures deleted until the nightly run. Reproduced with a broker on a closed port (`kombu.exceptions.OperationalError`). Fixed: the error is logged and the lectures are made in the request; if that fails too, it is logged and the nightly job makes them. Tests run against the closed port. The audit suggested "log and wait for the nightly job"; making them at once avoids a day without lectures. | High | [x] |
| X2 (L1) | One failing schedule or institute ended the nightly extend and the 5-minute finish run for everyone after it. Each schedule and each institute is now logged and skipped on error (ids only, no personal data); tests added. | Medium | [x] |
| X3 (L2) | Sidebar group headings were `text-white/55`; axe flagged them on 5 teacher pages. Now `text-white/70` (7.3:1 on the lighter end of the gradient). Correction (Phase 4 re-audit): opacity was not the cause. The flagged "Leave" heading sat below the screen height, outside the sidebar gradient, so it was white text on the light page. That is P4-4. | Low | [x] |
| X4 (L3) | Schedule preview at 360px: 21 dates became 21 table cards with an empty Note row; Save was at the very bottom. Now one line per date ("Thu 15 Oct, 10:00 AM PKT" and New or Skipped, the reason only when skipped) and a Save button above the dates. 21 dates: page 6355px to 3691px (the rest is the form), Save at y 394. | Low | [x] |
| X5 (L4) | "Open meeting link" (teacher and admin) opened in the same tab. `Button` has `new_tab`; the link now opens a new tab without an opener, like the student Join. | Low | [x] |
| X6 (L5) | A schedule whose teacher became inactive or stopped teaching a subject made no lectures, silently. The schedule list now shows "Needs attention" with the reason; the generator and the list share `schedule_problem`. The schedule list budget is 10 queries (+1, the teacher links once per page). | Medium | [x] |
| X7 | Cleanup found while fixing X6: `ScheduleListPage` had unused copies of the date filter methods (a 3.3 edit replaced every match). Removed. | Low | [x] |

## Build of Phase 4 (attendance)

Left out of 4.1 to 4.3 on purpose, or found while building.

| # | Item | Priority | Status |
|---|---|---|---|
| AT1 | Teacher "My students" (SPEC 3: ID, Name, Batch, Attendance %, Guardian phone) has no page and no roadmap item; the menu link is disabled. `attendance.services.student_summaries` gives the % for a page of students in 4 queries. Add a roadmap item or build it with the teacher dashboard numbers (FEATURES 14). | Low | [ ] |
| AT2 | A teacher sees no count of finished lectures without marks ("attendance to take"). The lecture page and Lecture history show "Take attendance" and "Not taken" one lecture at a time. A dashboard card fits with the teacher analytics (FEATURES 14). Fixed: the teacher dashboard card "Attendance to take" counts finished lectures with at least one expected student and no marks (4 queries for any number). | Low | [x] |
| AT3 | The admin cannot correct a mark; only the lecture's teacher can (owner approved 4.1 defaults). If the teacher leaves, nobody can fix old marks. Decide with payroll or leave (Phase 8 and 9). | Low | [ ] |

## Phase 4 audit (2026-10-14, after PR #51)

Full review of roadmap 4.1 to 4.3 on `main` ceecf9c: pytest 1771 passed, ruff clean, mutation check 427 caught; 19 attendance, lecture and dashboard pages opened as `demo-teacher`, `demo-student`, `demo-guardian` and `demo-admin` at 360px and 1440px (all 200, no sideways scroll, no console errors). Security pass clean: `unscoped` only in the demo reset, every view declares `allowed_roles`, no `|safe`, the switcher form has CSRF and goes back only to `/guardian/` pages.

| # | Item | Priority | Status |
|---|---|---|---|
| P4-1 | A deactivated student (one who left) kept their enrolments, so they stayed on every new roster. The form starts every unmarked student at Present, so each save marked them Present, and they counted in Present / Total. Enrolments of inactive students are now left out; a student with a saved mark stays on that lecture (SPEC 6.3). Tests and a mutation entry added. | Medium | [x] |
| P4-2 | "Student attendance history" loads every student of the institute into the Student select. Fine for a few hundred; at about 2,000 students the page has a very long list. Use a search field (like All students) when an institute grows. Fixed: a search (name, code, email or phone) lists the matches, 25 a page, each with a link to their history; a chosen student has "Choose another student". | Low | [x] |
| P4-3 | The attendance pages and dashboard % read every finished lecture of the student's batches and page them in Python (no N+1; the query count is fixed). A batch with 5 lectures a day has about 1,500 a year. Revisit with P3-8 (caching) before large institutes. | Low | [ ] |
| P4-4 | The dark sidebar background stopped at the screen height. The `<aside>` had `h-full` and the gradient, and its parent scrolls, so items below the first screen (Account, My profile, Sign out) were white text on the light page. Seen for teacher at 900px height, student and guardian at about 640px. Fixed in PR #54: the aside has `min-h-full` and grows with its items. | High | [x] |
| P4-5 | A class the teacher has not marked lowered the %. Owner decision 2026-10-14: % = (Present + Late + 0.5 x Partial) / marked classes; a not-marked class is left out and shows "Waiting for teacher" to students and guardians; with no marks the page says "No marks yet". The Absent card counts only Absent. Fixed in PR #54. | Medium | [x] |
| P4-6 | The schedule preview was 3799px tall at 360px for 21 dates. Fixed in PR #54: the list shows the first 10 dates and "and N more dates"; the card title keeps the full count. | Low | [x] |

## Build of Phase 5 (assessments)

Left out of 5.1 on purpose, or found while building.

| # | Item | Priority | Status |
|---|---|---|---|
| AS1 | SPEC 4.16 has an optional assignment file, and students may want to attach work. There is no file storage yet (no `MEDIA` settings, no private download view; ARCHITECTURE plans S3, which is a new dependency). 5.1 takes text answers only. Decide the storage with course documents (FEATURES 7, Phase 9) and add the file then. | Medium | [ ] |
| AS2 | The guardian sees no assignments yet. The guardian menu (FEATURES 13) has no "Assignments" item; scores come with roadmap 5.4. `Assignment.objects.for_user` and `Submission.objects.for_user` already cover guardians (tested). Fixed in 5.4 part 1: guardian "Assignments" and "Quizzes and exams" for the chosen child. | Low | [x] |
| AS3 | A teacher cannot delete an assignment made by mistake; they can edit it until the first answer. Add Delete (confirm dialog) when the admin overview comes (FEATURES 7, approval queues). | Low | [ ] |
| AS5 | axe (best-practice rules) on the 5.1 pages, and the same on the existing lecture pages: `empty-table-header` (the `DataTable` actions column has an empty header; give it a screen-reader label such as "Actions") and `heading-order` (form `Section` titles skip a heading level after the page title). Shared components, so one fix covers every page. | Low | [ ] |
| AS6 | 5.2 lets a teacher delete any question in their bank. When quizzes use questions (5.3), a question in a quiz must stay (protect it, or copy the question into the quiz), so old attempts keep their questions and marks. Fixed in 5.3 part 1: `QuizQuestion.question` is `PROTECT`; Delete says to remove it from the quiz first; a question of a quiz that has opened cannot change. | Medium | [x] |
| AS7 | The teacher quiz list shows Questions (count and marks) where SPEC 3 has Attempts; the admin "Quizzes and exams" overview (SPEC 3) has no page yet. Both need attempts: build them in 5.3 part 2. The Attempts column is built in 5.3 part 2b; the admin overview (list and read-only quiz page) in part 2d. | Low | [x] |
| AS8 | After a quiz closes, a student sees only the score, not each question with the right answer (showing it while the quiz is live would help other students). Decide with 5.4 (scores on the portals). Fixed in 5.4 part 1: "Your answers" after the quiz closes and the attempt ends. | Low | [x] |
| AS9 | An attempt left open (the student closed the page) is submitted when a page next shows it; the student's pages and the teacher results (5.3 part 2b) do that. If reports read attempts directly later, add a job that submits expired attempts (like `finish_all_ended_lectures`). Until then the teacher list's "N to mark" leaves out an expired attempt that no page has submitted yet. | Low | [ ] |
| AS10 | The teacher dashboard card "Answers to grade" (5.1) counts assignment answers only, not quiz attempts with written answers to mark. Add them when the dashboard is next changed (5.4). Fixed in 5.4 part 2: the card adds the submitted attempts. | Low | [x] |
| AS11 | Exam flags come from the student's browser (5.3 part 2c). A student who turns off JavaScript, or blocks the request, sends no flags; the server cannot see a page leave. The paper still works without JavaScript (the server ends the attempt at the deadline). If an institute needs proof, show "no flag data" when the paper's guard never reported in (for example a start ping). | Low | [ ] |
| AS4 | Notifications for "assignment published", "submission received" and "graded" (SPEC 7) wait for the notification service (roadmap 6.1 and 6.2). Fixed in 6.2: "published" to the class and guardians, "answer received" to the teacher (first answer only), "graded" to the student and guardians with the marks. | Low | [x] |

## Phase 5 audit (2026-10-16, after PR #64)

Full review of roadmap 5.1 to 5.4 on `main` 7631c0f: pytest 2130 passed, ruff clean, makemigrations clean, mutation check 557 caught; 17 assessment pages opened as `demo-teacher`, `demo-student`, `demo-guardian` and `demo-admin` at 360px and 1440px (all 200, no sideways scroll, no console errors, no axe WCAG A/AA violations). Security pass clean: `unscoped` only in the demo reset, every view declares `allowed_roles`, the admin quiz pages use the Academic menu key, no `|safe`, the exam flag POST needs the CSRF token.

| # | Item | Priority | Status |
|---|---|---|---|
| AS12 | A student who left a batch or subject still saw their old quizzes and assignments in the lists, but the open link gave 404: the lists keep rows with an attempt or answer, the detail scope needed a current enrolment. Fixed: the student and guardian scopes of `Quiz` and `Assignment` also include the rows with the student's own attempt or answer (a draft quiz stays hidden). | Low | [x] |
| AS13 | The paper's `auto_submit` field marked a normal Submit as "Sent when the time ended" when a student added it by hand. The score did not change. Fixed: the flag counts only within 1 minute of the deadline. | Low | [x] |
| AS14 | Owner decision: "Your answers" shows the right answers after a quiz closes, even when the teacher uses the same bank question in a later quiz. Real exams have the same risk. Decided 2026-10-16: keep it. | Low | [x] |
| AS15 | Seen while recording the progress video: the teacher and admin quiz pages of a closed quiz said "Closed. It closes Tue 13 Oct 2026, 3:42 PM PKT." (a past time with "closes"). Fixed: "Closed Tue 13 Oct 2026, 3:42 PM PKT.", like the student page. | Low | [x] |

## Phase 6 audit (2026-10-16, on `phase/6`)

Full review of roadmap 6.1 to 6.3 on the local `phase/6` branch (one PR for the phase): after the audit fixes pytest 2393 passed, ruff clean, makemigrations clean, mutation check 611 caught (0 missed, 0 stale); 204 pages opened by `./scripts/browser-walk.sh` as `demo-super`, `demo-admin`, `demo-teacher`, `demo-student` and `demo-guardian` at 360px and 1440px (all 200, no sideways scroll, no console errors, no axe WCAG A/AA findings); the bell, Messages, a thread, New message, Message monitor and Broadcast looked at in screenshots at both widths. Security pass: `unscoped` only in the demo reset; every view declares `allowed_roles`; the admin Broadcast and Monitor use the Messages menu key; no `|safe`; Open, Mark all as read, the thread actions and Draft delete are POST with CSRF; the bell and menu badge parts answer 204 to a signed-out user; "Mark all as read" goes back only to a path on this site; notification and message text is escaped. The inbox makes 7 queries for 3 or 12 threads (no N+1).

| # | Item | Priority | Status |
|---|---|---|---|
| P6-1 | The shared form field template showed the label of a hidden field, so New message had an empty "To" above Subject. Hidden fields now render only the input (every form). | Low | [x] |
| P6-2 | The lecture reminder job locked the joined teacher and user rows too (`select_for_update` with `select_related`), so a profile save could wait for it. It now locks the lecture rows only (`of=("self",)`). | Low | [x] |
| P6-3 | The "New" badge in the Messages list sat above the subject and made the rows tall. `BlockStack(inline=True)` puts it on the same line. | Low | [x] |
| P6-4 | New message listed up to 20 people for a search, each with a full-size "Choose" button (very long at 360px). Now 10, each with an icon button. | Low | [x] |
| P6-5 | The demo admin and sub-admin had no names, so messages and the monitor showed their emails. `seed_demo` names them "Office Admin" and "Office Helper". | Low | [x] |
| P6-6 | A signed-out user on a feature-gated page (the first ones are Messages) got 403, not the sign-in page: the feature check ran before the role check. Fixed in 6.3 part 2. | Low | [x] |
| P6-7 | Polling: each portal page now loads 2 small HTMX parts (the bell count and the Messages badge) and refreshes both every 60 seconds, on top of "Up next" every 30 seconds (P3-8). Join them into one request, or use a longer interval, before large institutes. | Low | [ ] |
| P6-8 | A blocked student (portal access paused) cannot open Messages, because every `/student/` page shows "Access paused". The page shows the institute phone (SPEC 6.2). Decide if a blocked student may still message the office. Owner decision 2026-10-16: yes. Messages stay open while blocked (the reach rule does not change), and "Access paused" has a "Message the office" button. | Low | [x] |
| P6-9 | A notification text keeps the time in the zone the recipient had when it was made; a later time zone change does not rewrite old notifications. Accepted: the zone name is in the text. | Low | [x] |

## Phase 7 audit (2026-10-17, on `phase/7`)

This was a full review of roadmap 7.1 to 7.6 and the demo fees, on the local `phase/7` branch (one PR for the phase).
- **Checks:** pytest 2719 passed. Ruff and makemigrations are clean. The mutation check gave 690 caught, 0 missed, 0 stale.
- **Browser walk:** `./scripts/browser-walk.sh` opened 242 pages for the 5 demo roles at 360px and 1440px. All answered 200, with no sideways scroll, no console errors and no axe WCAG A/AA findings.
- **Screenshots** at both widths: Fee defaulters, the Challan dashboard, the student and guardian fee pages, and the 3 dashboards.
- **Security pass:**
  - `unscoped` appears only in the demo resets.
  - Every finance view gets `allowed_roles` from its mixin.
  - There is no `|safe`.
  - The actions are POST forms with CSRF.
  - The receipt files are private, with `nosniff` and `no-store`.
  - The Block / Unblock "next" accepts only an `/admin/` path.
- **By hand:** the challan page, the PDF and the reports show and count the late fee.

| # | Item | Priority | Status |
|---|---|---|---|
| P7-1 | The Challan dashboard uses the Dashboards menu key (FEATURES 11 menu), so a sub-admin with Dashboards but without Finance sees this month's fee totals. The Main dashboard fee strip needs Finance. Decide if the Challan dashboard should need Finance too. Owner decision 2026-10-17: yes. A sub-admin needs Dashboards and Finance for the page and its menu item (`extra_menu_keys`). | Low | [x] |
| P7-2 | The dashboards and fee pages take "today" in the viewer's own zone; the reminder and defaulter jobs use the institute's zone. Near midnight a viewer in another zone can see a different "this month" or "overdue". | Low | [ ] |
| P7-3 | Turning "Auto-block defaulters" off leaves the students the rule blocked still blocked (assumed; SPEC 6.2 says nothing). Decide if switching it off should open them. Owner decision 2026-10-17: yes. Saving the settings with the rule switched off opens every student the rule blocked; manual blocks stay. | Low | [x] |
| P7-4 | Fee notices for sub-admins (receipt submitted, challans overdue) wait for stored sub-admin menus (backlog S15): the jobs load users from the database, where a sub-admin has no menus yet. Owner decision 2026-10-17: close it with S15; S15 adds a test that a sub-admin with Finance gets "receipt submitted". | Low | [ ] |
| P7-5 | The bulk print test counted PDF pages with a regular expression that cut a compressed stream ending in a carriage return, so it failed on some dates. Fixed: the counter keeps the end bytes. | Low | [x] |

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
