# UI-GUIDELINES

Rules for building screens. AI agents must follow this file exactly. Do not invent new components, colors, or spacing.

Status: values marked **(proposed)** are our picks. Replace them after we see the demo.

## 1. UI stack

- Django templates + Python component classes (see `COMPONENTS.md`). No React/Vue unless approved.
- Forms: django-crispy-forms with form classes that inherit our base forms.
- Tailwind CSS for all styling. No custom CSS files except `static/css/app.css` for tokens.
- HTMX for partial updates (forms, tables, modals, tabs).
- Alpine.js for small client state (dropdowns, modals, countdown).
- Chart.js for charts.
- Font Awesome Free icons (solid + regular), as inline SVG or the free webfont. The reference uses Font Awesome. One icon set only.
- Every reusable piece is a class in `apps/ui/components/` with a template in `apps/ui/templates/ui/components/`.

## 2. Colors

Taken from the reference product's captured CSS (public). Each portal has its own accent, with one shared system.

| Portal | Primary | Secondary / accent | Sidebar or nav dark | Page bg |
|---|---|---|---|---|
| Admin | `#005E78` | `#0B7F9C` | `#00303D` (nav), `#002530` (sidebar) | `#F0F3F5` |
| Teacher | `#005E78` family, accent `#00A2CF` | `#00475B` (dark) | `#00303D` | `#F3F7F9` |
| Student | `#0D9488` | `#0F766E`, accent `#34D399` | `#115E59` | `#F0FDFA` |
| Guardian | `#0EA5E9` | `#0284C7`, accent `#6366F1` | `#0F172A` | `#F0F4F8` |

Shared tokens (all portals):

| Token | Hex | Use |
|---|---|---|
| `success` | `#059669` / `#10B981` | paid, active, present |
| `warning` | `#D97706` | pending, due soon |
| `danger` | `#E11D48` / `#EF4444` | overdue, inactive, absent |
| `info` | `#2563EB` | notices |
| `violet` | `#7C3AED` | occasional highlight (admin) |
| `text` | `#0C1B1F` (admin) / `#0F172A` | main text |
| `muted` | `#5D6E73` | secondary text |
| `border` | `#E2E8EA` | lines and card borders |
| `surface` | `#FFFFFF` | cards |

- Implement as CSS variables set per portal (`<body data-portal="admin">`), mapped to Tailwind theme colors. Never raw hex in templates.
- Status colors always come with a text label.
- These values are PREVIEW from public CSS. Compare with the logged-in demo before locking.

## 3. Type, spacing, shape

- Fonts seen in the reference: Sora (admin headings), Plus Jakarta Sans, Poppins, Inter, JetBrains Mono (codes and numbers). Our pick: Plus Jakarta Sans for headings and Inter for body, JetBrains Mono for IDs and amounts. System fallback on all.
- Sizes: page title `text-2xl font-semibold`, section title `text-lg font-semibold`, body `text-sm`, caption `text-xs text-muted`.
- Spacing: use the 4px scale (`p-2`, `p-4`, `p-6`). Card padding is `p-5`. Gap between cards is `gap-4`.
- Radius: `rounded-lg` for cards and inputs, `rounded-full` for badges and avatars.
- Shadow: cards use `border` only. Only modals and dropdowns get `shadow-lg`.
- Line length for text blocks: max 70 characters (`max-w-prose`).

## 4. Layout

- **Admin portal:** top horizontal menu bar with grouped dropdowns (Dashboards, Institute, People, Online Lectures, Finance, Teacher Salary, Academic, Messages), brand on the left, bell and user menu on the right, breadcrumb and live clock below, then a campus hero banner on the dashboard.
- **Teacher, Student, Guardian portals:** dark left sidebar with labelled groups, top bar with clock, bell, theme toggle and avatar, then a hero banner on the dashboard.
- Guardian top bar has the institute name and a **child switcher**.
- Sidebar collapses to a drawer on mobile. Admin top menu becomes a hamburger drawer on mobile. Built in the Phase 2 audit: below md, a "Menu" button opens either one. Desktop admin groups are closed dropdowns.
- Wide tables scroll sideways inside their own box, never the page. The main column and form fieldsets use `min-w-0`, and form fields are full width, so nothing pushes a 360px page wider.
- Content: `max-w-7xl`, `p-6` on desktop, `p-4` on mobile.
- Dashboard grid: hero, then stat cards, then quick actions, then 2-column sections.
- Mobile first. Every page must work at 360px width.
- Menu items per portal are in `FEATURES.md` section 13. Do not add or rename items without asking.
- Public site uses `layouts/public.html`.

## 5. Components (exact list)

The full list, class names, files, and props are in `COMPONENTS.md` section 7. Summary:

- **Layout:** `TopNavShell` (admin), `SidebarShell` (teacher, student, guardian), `Sidebar`, `TopNav`, `HeroBanner`, `PageHeader`, `SectionCard`, `Tabs`, `Modal`
- **Data:** `StatCard`, `DataTable`, `Badge`, `Avatar`, `ProgressBar`, `ChartCard`, `EmptyState`
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
- **`FormPage`:** `PageHeader` -> one `SectionCard` holding a crispy form (`{% crispy form %}`). Max width `max-w-2xl`.
- **`DashboardPage`:** `PageHeader` -> row of `StatCard` -> row of `QuickAction` -> `SectionCard`s.
- **Modal forms:** use `HtmxModalForm` for short forms (under 6 fields). Longer forms get their own page.

## 7. Tables

- Header row `bg-page`, text `text-xs text-muted`, rows `text-sm`, row hover `bg-page`.
- Status columns always use `badge`.
- Actions column on the right: icon buttons with tooltips, max 3.
- On mobile, tables scroll horizontally inside `overflow-x-auto`. Never let the page scroll sideways.

## 8. Forms

- Forms are crispy-forms classes (`BaseForm`, `TenantModelForm`). Layout is set in `get_layout()`, never in the template.
- Labels above inputs, never placeholder-only.
- Required fields marked with `*`.
- Errors appear under the field in `danger` text and say how to fix it.
- Primary action on the right, "Cancel" on the left of it.
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
- Visible keyboard focus on every control (`focus-visible:ring-2`).
- Contrast at least 4.5:1 for text.
- Every icon-only button has an `aria-label`.
- Money: `Rs 4,000` format using the institute currency. Right-aligned in tables.
- Dates: `16 Aug 2026`. Times: 12-hour with AM/PM.

## 11. PWA

- `manifest.json` with name, icons (192 and 512), `theme_color: #005E78`, `display: standalone`.
- Service worker caches the app shell and static files only. Never cache API or personal data pages.
- "Install app" button appears when the browser allows it.

## 12. Do not

- Do not copy the reference product's logo, name, images, or text.
- Do not add a second icon set, font, or CSS framework.
- Do not use inline styles.
- Do not build one-off components inside page templates. Make a component class.
- Do not put layout or form HTML in templates when a crispy layout object or component exists.
