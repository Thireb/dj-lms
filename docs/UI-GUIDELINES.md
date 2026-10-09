# UI-GUIDELINES

Rules for building screens. AI agents must follow this file exactly. Do not invent new components, colors, or spacing.

Design system: **Lexicon**, approved by the owner on 2026-10-09 (roadmap Phase R, proposal linked in `ROADMAP.md` R1). Built: R4a (tokens, font, icons, shells, public pages, base components), R4b (tables, filters, pagination, forms layout) and R4c (dashboards and portal home pages).

## 1. UI stack

- Django templates + Python component classes (see `COMPONENTS.md`). No React/Vue unless approved.
- Forms: django-crispy-forms with form classes that inherit our base forms.
- Tailwind CSS for all styling. Tokens and a few component classes (`btn`, `chip`, `field-control`, `band`) live in `static/css/src/input.css`, compiled to `static/css/app.css`.
- HTMX for partial updates (forms, tables, modals, tabs).
- Alpine.js for small client state (dropdowns, dialogs, menus, clock, countdown).
- Chart.js for charts.
- Icons: **Lucide** only (ISC), self-hosted as one SVG sprite (`static/vendor/lucide/icons.svg`). Use the `Icon` component or `{% icon "name" %}`. To add an icon, list it in `apps/ui/icons.py` and run `scripts/build_icon_sprite.py`. Unknown names render nothing.
- Font: **Familjen Grotesk** (Lexicon's typeface, OFL), self-hosted woff2 in `static/vendor/familjen-grotesk/`. No CDN.
- Every reusable piece is a class in `apps/ui/components/` with a template in `apps/ui/templates/ui/components/`.

## 2. Colors

From Lexicon's own site (lexicon.edu.pk), measured in a browser. **One look for every portal**; the role shows in the user chip, not in the colours.

| Token | Hex | Use |
|---|---|---|
| `primary` (royal) | `#002DA8` | buttons, links, active states, focus |
| `primary-dark` | `#00238A` | primary hover |
| `primary-50` / `primary-100` | `#EEF2FC` / `#DCE4F8` | soft fills, icon tiles, active menu item |
| `accent` (sky) | `#1273EB` | gradient end, focus ring |
| `indigo` | `#130C8E` | sidebar, band start, brand mark |
| `indigo-deep` | `#0B0766` | sidebar gradient end |
| `page` | `#F7F8FB` | page background |
| `surface` | `#FFFFFF` | cards, top bar |
| `field` | `#F2F4F9` | input fill |
| `text` | `#16182B` | main text |
| `ink-2` | `#4A5068` | secondary text in controls |
| `muted` | `#636A85` | captions, labels (5.1:1 on white) |
| `border` / `border-strong` | `#E6E8F0` / `#C9CEDD` | hairlines, hover borders |
| `success` on `success-50` | `#0E7A55` on `#E3F5EE` | active, paid, present |
| `warning` on `warning-50` | `#9A5B00` on `#FDF1DC` | pending, blocked, due soon |
| `danger` on `danger-50` | `#B4233F` on `#FBE7EB` | inactive, overdue, errors, destructive |
| `tone-indigo-50`, `tone-teal` on `tone-teal-50`, `tone-clay` on `tone-clay-50` | `#EAE6FB`; `#0B5E86` on `#E2F2F8`; `#8A3B12` on `#FCEBE3` | avatar tints only |

- Never raw hex in templates; use the Tailwind token classes (`bg-primary`, `text-muted`, ...). A test fails if a template has one.
- Status colours always come with a text label (chips have a dot and a word).
- **The band** (`.band` + `_waves.html`): royal-to-indigo gradient with fine wave lines, from Lexicon's homepage. It is the one bold element: sign-in panel, dashboard heroes, Access paused and other full-page notices only. Everything else stays white and quiet.
- Light only. No dark mode (owner decision, R2).

## 3. Type, spacing, shape

- One family: Familjen Grotesk 400 to 700, tabular digits everywhere (`font-variant-numeric: tabular-nums` on `body`).
- Sizes: display 32-40 bold (sign-in, heroes), page title 26 bold, section title 16-18 semibold, body 15, label 14 semibold, caption 13. No all-caps labels.
- Spacing: 4px scale. Cards `p-5`, gaps `gap-4` to `gap-5`, content padding `px-4 py-5` (phone) and `px-7 py-6` (desktop), content max width 1240px.
- Radius: controls 10px, fields 12px, cards 18px, heroes 24px, chips and avatars full.
- Shadow: cards use a hairline border only. Floating things get the tinted shadows: `--shadow-float` (primary buttons), `--shadow-pop` (menus, dropdowns, dialogs, toasts).
- Controls: buttons 40px (`btn-lg` 48px), fields 48px, icon buttons 40px square. Touch targets at least 40px.
- Line length for text blocks: under 70 characters.

## 4. Layout

- **Admin portal:** white top bar (sticky): brand on the left, menu groups as closed dropdowns (each item has an icon tile; items of later phases are shown dimmed), bell and the user chip (initials, name, role) on the right. Page header below: breadcrumb and live clock chip, then title, subtitle and actions.
- **Teacher, Student, Guardian portals:** deep indigo sidebar (gradient to `indigo-deep`) with the brand, sentence-case group labels and a white-on-glass active item (`aria-current`); a white top bar with the bell and the user chip.
- Guardian top bar has the institute name and a **child switcher**.
- Sidebar collapses to a drawer on mobile. Admin top menu becomes a hamburger drawer on mobile. Built in the Phase 2 audit: below md, a "Menu" button opens either one. Desktop admin groups are closed dropdowns.
- Wide tables scroll sideways inside their own box, never the page. The main column and form fieldsets use `min-w-0`, and form fields are full width, so nothing pushes a 360px page wider.
- Content: max width 1240px, `px-7 py-6` on desktop, `px-4 py-5` on mobile.
- Dashboard grid: hero, then one feature card ("Up next"), then stat cards, then quick actions, then sections (2 columns on the admin dashboard and the guardian home).
- Admin dashboard: the campus hero holds the main actions (first one white, the rest glass) and the key numbers; then a Students and a Teachers card (total, active and inactive chips, a ring, the five newest people). A sub-admin without the People menu sees the numbers but no names and no links.
- Teacher, student and guardian homes: a welcome band (initials, "Good morning, name", code, batch and subject chips), then "Up next". Until lectures exist, "Up next" is an empty state that says when lectures appear.
- Mobile first. Every page must work at 360px width.
- Menu items per portal are in `FEATURES.md` section 13. Do not add or rename items without asking.
- Public pages use `PublicFormShell` (`layouts/public.html`): `split` (form left, band right; a short band on top on phones) for sign-in, set password and forgot password; `notice` (whole page is the band) for Access paused and refusals.

## 5. Components (exact list)

The full list, class names, files, and props are in `COMPONENTS.md` section 7. Summary:

- **Layout:** `TopNavShell` (admin), `SidebarShell` (teacher, student, guardian), `Sidebar`, `TopNav`, `HeroBanner`, `PageHeader`, `SectionCard`, `Tabs`, `Modal`
- **Data:** `StatCard`, `DataTable`, `Badge`, `Avatar`, `PersonCell`, `PersonList`, `KpiSummary`, `ProgressBar`, `ProgressRing`, `ChartCard`, `EmptyState`
- **Actions:** `Button`, `QuickAction`, `ConfirmDialog`, `Toast`
- **Lectures:** `CountdownCard`, `LectureRow`, `ScheduleList`
- **Navigation:** `NotificationBell`, `FilterBar`, `Pagination`
- **PDF:** `PdfHeader`
- **Form layout (crispy):** `Section`, `Row`, `FormActions`

Rules:
- Use components by creating the class in Python and printing it in the template (`{{ table }}`).
- Need a variant? Subclass the component and change an attribute or override one method.
- Need something new? Add the class and a row in `COMPONENTS.md` first, then use it.
- Never write component HTML or Tailwind classes directly in a page template.

## 6. Page patterns

Each pattern is a base page class in `apps/ui/views/pages.py`. Subclass it.

- **`ListPage`:** `PageHeader` -> `FilterBar` -> `DataTable` -> `Pagination`. Empty list shows `EmptyState`.
- **`DetailPage`:** `PageHeader` -> two-column cards (info left, related lists right).
- **`FormPage`:** `PageHeader` -> one card (max width 1024px) with the crispy sections split by hairlines: section title and explanation on the left, fields on the right (stacked on phones). Short fields go in two columns (`Section(columns=2)`). Buttons sit in a footer bar.
- **`DashboardPage`:** `PageHeader` -> `HeroBanner` -> feature card -> row of `StatCard` -> row of `QuickAction` -> `SectionCard`s.
- **Modal forms:** use `HtmxModalForm` for short forms (under 6 fields). Longer forms get their own page.

## 7. Tables

- Table in a card with a light header row (13px semibold muted), 14px rows. People are one column: avatar, name and code (`PersonCell`); no separate ID column.
- Status columns always use `badge`.
- Actions column on the right: small icon buttons with an `aria-label`, max 3; destructive ones open a `ConfirmDialog` (a real modal).
- On phones each row becomes a card with label and value pairs; the person is the card title. Never let the page scroll sideways.
- Filters above the table: search with an icon, selects, "Apply filters", and "Clear" when a filter is set. Pagination below: "Showing 1 to 25 of 52" and page numbers.

## 8. Forms

- Forms are crispy-forms classes (`BaseForm`, `TenantModelForm`). Layout is set in `get_layout()`, never in the template.
- Labels above inputs, never placeholder-only.
- Every titled section has a one-line explanation of what it is for.
- Many-to-many choices (for example subjects per batch) are chip toggles that show a check when selected.
- File fields are a dashed drop area with a "Choose file" button (base style in `input.css`).
- Required fields marked with `*`.
- Errors appear under the field in `danger` text and say how to fix it.
- Primary action on the right, "Cancel" on the left of it. On public pages the submit button is full width (`FormActions(stacked=True)`).
- Disable the submit button while the request runs.

## 9. Words on screen

- Sentence case everywhere ("Generate challan", not "Generate Challan").
- Buttons say what happens: "Save changes", "Enrol student", "Generate challans".
- The same action keeps the same name in button, toast, and history ("Published" toast after "Publish").
- Errors say what went wrong and what to do. No apologies, no vague text.
- Empty screens invite one action ("No lectures yet. Create your first lecture.").

## 10. Behavior and quality

- Show lecture and deadline times in the viewer's time zone, with the zone label (example: `3:00 PM PKT`).
- Countdown timers update every second without page reload.
- Join button is disabled until 10 minutes before start (configurable).
- Loading states use a spinner on the button or a skeleton row. No full-page spinners.
- Motion only in response to a click (open modal, expand, toast). No decorative animation.
- Respect `prefers-reduced-motion`.
- Visible keyboard focus on every control (3px sky outline from `:focus-visible` in `input.css`).
- Contrast at least 4.5:1 for text.
- Every icon-only button has an `aria-label`.
- Money: `Rs 4,000` format using the institute currency. Right-aligned in tables.
- Dates: `16 Aug 2026`. Times: 12-hour with AM/PM.

## 11. PWA

- `manifest.json` with name, icons (192 and 512), `theme_color: #002DA8`, `display: standalone`.
- Service worker caches the app shell and static files only. Never cache API or personal data pages.
- "Install app" button appears when the browser allows it.

## 12. Do not

- Do not copy the reference product's logo, name, images, or text.
- Do not add a second icon set, font, or CSS framework.
- Do not use inline styles.
- Do not build one-off components inside page templates. Make a component class.
- Do not put layout or form HTML in templates when a crispy layout object or component exists.
