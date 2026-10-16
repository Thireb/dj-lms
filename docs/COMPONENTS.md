# COMPONENTS

> **Lexicon redesign (roadmap Phase R).** Looks follow `UI-GUIDELINES.md`. R4a restyled the shells, public pages and base components below. R4b restyled tables, filters, pagination and the form layout. R4c built the dashboards and portal home pages.

How UI is built in Python. Components are classes. Pages and forms assemble them. New screens are made by subclassing, not by copying templates.

Same idea as our Pearl project: crispy-forms for forms, Python classes for components, inheritance for reuse.

## 1. Rules (short)

- Every UI piece is a Python class + one small HTML template.
- Props go in the constructor. Defaults live on the class.
- Reuse by subclassing: change a class attribute or override one method.
- Templates only display. No queries, no business logic, no `if role ==` checks.
- Pages build components in Python and pass them to the template as ready objects.
- If a screen needs a piece that doesn't exist, add a component class first (and a test), then use it.
- Do not paste raw HTML or Tailwind classes into page templates. Look for a component.

## 2. Where it lives

```
apps/ui/
  components/
    base.py        # Component base class
    layout.py      # TopNavShell, SidebarShell, Sidebar, TopNav, HeroBanner, PageHeader,
                   # SectionCard, Tabs, Modal, PublicFormShell
    forms.py       # CrispyForm, PublicPostForm, PortalPostForm
    quizzes.py     # AttemptTimer, ExamGuard
    block_stack.py # BlockStack, ButtonRow
    data.py        # StatCard, DataTable, Column, Badge, StatusBadge, Avatar,
                   # PersonCell, PersonList, KpiSummary, ProgressBar,
                   # ProgressRing, ChartCard, EmptyState, TextBlock
    actions.py     # Button, IconButton, QuickAction, ConfirmDialog, CopyField, Toast
    lectures.py    # CountdownCard, LectureRow, Calendar
    nav.py         # NotificationBell, NotificationCount, NotificationPanel,
                   # ChildSwitcher, FilterBar, Pagination
    pdf.py         # PdfHeader
  forms/
    base.py        # BaseForm, TenantModelForm, HtmxModalForm
    layout.py      # Section, Row, FormActions (crispy layout objects)
    widgets.py     # DatePicker, TimePicker, MoneyInput, PasswordInput
  views/
    pages.py       # PortalPageView, DashboardPage, ListPage, DetailPage, FormPage
  templates/ui/
    components/    # one html file per component
    forms/         # crispy template pack overrides
    layouts/       # app_shell.html, public.html
```

Rule: other apps import from `apps.ui`. `apps.ui` never imports from other apps.

## 3. Base component

```python
# apps/ui/components/base.py (shortened)
def render_child(child, request=None):
    """Render a nested component with the request; keep plain text as is."""
    return child.render(request=request) if isinstance(child, Component) else child


class Component:
    template_name: str = ""

    def __init__(self, **props):
        self.props = props

    def get_context(self) -> dict:
        return {"c": self, **self.props}

    def render(self, request=None) -> SafeString:
        return render_component_template(self, self.get_context(), request=request)

    def __html__(self) -> SafeString:   # lets templates write {{ component }}
        return self.render()

    __str__ = __html__
```

A component that holds other components overrides `render(request)` and passes the request down with `render_child` (`DataTable`, `BlockStack`, `ListPageBody`, `DetailPageBody`, `SectionCard`, the shells). Without the request, a nested `ConfirmDialog` or form has no CSRF token, and its POST fails (backlog S2, S7).

In a template: `{{ page.header }}` or `{{ stat }}`. No custom tag needed.

## 4. Subclassing examples

```python
class Badge(Component):
    template_name = "ui/components/badge.html"
    tone = "neutral"                      # success, warning, danger, info, neutral

    def __init__(self, text, tone=None):
        super().__init__(text=text, tone=tone or self.tone)


class ChallanStatusBadge(Badge):
    TONES = {"paid": "success", "partial": "warning", "pending": "warning", "overdue": "danger"}

    def __init__(self, challan):
        super().__init__(text=challan.get_status_display(), tone=self.TONES[challan.status])
```

```python
class DataTable(Component):
    template_name = "ui/components/data_table.html"
    columns: list = []                    # list of Column(...)
    empty_title = "Nothing here yet."
    row_actions: list = []

    def __init__(self, rows, **props):
        super().__init__(rows=rows, **props)

    def get_context(self):
        ctx = super().get_context()
        ctx["cells"] = [[col.cell(row) for col in self.columns] for row in self.props["rows"]]
        return ctx


class StudentTable(DataTable):
    columns = [
        Column("student_id", "ID"),
        Column("full_name", "Name"),
        Column("status", "Status", render=lambda s: Badge(s.get_status_display(), "success" if s.is_active else "danger")),
    ]
    empty_title = "No students yet."
```

Rule of thumb: generic component in `apps/ui`, domain subclass (`StudentTable`, `ChallanStatusBadge`) in the domain app's own `ui.py`.

## 5. Page classes

Pages are class-based views that assemble components.

```python
class PortalPageView(RoleRequiredMixin, TenantRequiredMixin, TemplateView):
    template_name = "ui/layouts/app_shell.html"
    portal = None            # "admin", "teacher", "student", "guardian"
    menu_key = None          # admin views only: one of the keys in core/menus.py
    active_item = None       # sidebar/top-nav highlight; defaults to menu_key when unset
    allowed_roles = []       # required, e.g. [Role.TEACHER] (from apps.core.roles); empty list = 403 for everyone
    title = ""
    breadcrumb = []

    def get_header(self):
        return PageHeader(title=self.title, breadcrumb=self.breadcrumb, actions=self.get_actions())

    def get_actions(self):
        return []

    def get_components(self) -> dict:
        return {}

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["header"] = self.get_header()
        ctx.update(self.get_components())
        return ctx

    def render_to_response(self, context, **kw):
        # get_shell_class(): TopNavShell for admin, SidebarShell for the others.
        # The page body and the shell are rendered with the request (CSRF).
        shell = self.get_shell_class()(portal=self.portal, user=self.request.user, active=self.get_active_item(), content=self.build_page_body(context), ...)
        return HttpResponse(shell.render(request=self.request), **kw)


class ListPage(PortalPageView):
    table_class = None
    filter_class = None
    def get_queryset(self): ...
    def get_components(self):
        return {"filters": self.filter_class(self.request), "table": self.table_class(self.get_queryset())}


class StudentListPage(ListPage):
    portal = "admin"
    title = "Students"
    menu_key = "students"
    table_class = StudentTable
    filter_class = StudentFilterBar
    allowed_roles = [Role.INSTITUTE_ADMIN]
    def get_queryset(self):
        return StudentProfile.objects.for_user(self.request.user)   # scoped by role and institute
    def get_actions(self):
        return [Button("Enrol student", url=reverse("admin:student_create"), icon="plus")]
```

Base page types: `DashboardPage`, `ListPage`, `DetailPage`, `FormPage`. They match the page patterns in `UI-GUIDELINES.md`. `DashboardPage` slots, in page order: `get_hero()` (a `HeroBanner`), `get_feature()` (one card, for example "Up next"), `get_stat_cards()`, `get_quick_actions()`, `get_sections()`. `section_columns = 2` puts the section cards side by side from lg.

## 6. Forms with crispy-forms

- Package: `django-crispy-forms` with a Tailwind template pack. Check the maintained Tailwind pack for your crispy-forms version, or keep our own pack in `apps/ui/templates/ui/forms/`.
- Every form inherits `BaseForm` (or `TenantModelForm` for model forms that need the institute).
- Layout is defined in the form class through `get_layout()`. No layout logic in templates.
- Custom crispy layout objects live in `apps/ui/forms/layout.py`: `Section`, `Row`, `FormActions`.

```python
class BaseForm(forms.Form):
    form_method = "post"
    save_label = "Save changes"
    cancel_url = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_tag = False
        self.helper.layout = self.get_layout()

    def get_layout(self):
        return Layout(*self.fields.keys(), FormActions(self.save_label, self.cancel_url))


class TenantModelForm(BaseForm, forms.ModelForm):
    def __init__(self, *args, institute, **kwargs):
        self.institute = institute
        super().__init__(*args, **kwargs)


class StudentForm(TenantModelForm):
    save_label = "Enrol student"

    class Meta:
        model = StudentProfile
        fields = ["first_name", "last_name", "date_of_birth", "phone", "batch"]

    def get_layout(self):
        return Layout(
            Section("Student details", Row("first_name", "last_name"), Row("date_of_birth", "phone")),
            Section("Class", "batch"),
            FormActions(self.save_label, self.cancel_url),
        )
```

- Modal forms: subclass `HtmxModalForm` (same as `BaseForm`, renders inside `Modal`, submits with HTMX). Not used by a page yet.
- `BaseForm` gives text inputs, selects and textareas the shared full-width classes (`INPUT_CLASSES`), so fields fit a 360px screen. A widget with its own `class` keeps it.
- Template: `{% crispy form %}` inside the `FormPage` layout. That is the only form tag allowed in templates.

## 7. Component list

Every item here is a class. Names are fixed.

| Class | File | Purpose | Main props |
|---|---|---|---|
| `TopNavShell` | layout | admin shell: top menu bar with dropdown groups; below md a Menu button shows the groups as a collapsible list | `portal`, `user`, `active` |
| `SidebarShell` | layout | teacher/student/guardian shell: sidebar + top bar; below md the sidebar is hidden and a Menu button opens it as a full-screen panel (Escape or a tap outside closes it); `child_switcher` goes in the top bar (the brand hides below md to make room) | `portal`, `user`, `active` |
| `TopNav` | layout | grouped dropdown menu from a menu config | `portal`, `active` |
| `Sidebar` | layout | grouped sidebar menu from a menu config | `portal`, `active` |
| `HeroBanner` | layout | dashboard banner on the Lexicon band (gradient + waves): title, subtitle, chips, actions (`Button` `light` first, then `glass`); `stats` adds glass number tiles on the right (admin campus hero); `initials` adds a large avatar (portal welcome) | `title`, `subtitle`, `chips`, `actions`, `stats` (list of value, label, note), `initials` |
| `PageHeader` | layout | breadcrumb (chevrons), optional live clock chip in the viewer's time zone, title, subtitle, actions; portal pages turn the clock on | `title`, `breadcrumb`, `actions`, `subtitle`, `clock` |
| `SectionCard` | layout | titled card with "View all"; optional icon tile before the title | `title`, `body`, `link_url`, `link_label`, `icon` |
| `Tabs` | layout | tabs with HTMX swap (not used by a page yet) | `tabs`, `active` |
| `LinkTabs` | layout | tabs that are plain links (each tab is its own list, for example Today, Upcoming, Past, All); the current tab has `aria-current="page"`; 40px tall; scrolls sideways on phones | `tabs`, `active`, `label` (the nav name) |
| `Grid` | layout | components in a grid: `stats` (2 columns, 4 from lg), `sections` (2 columns from lg), `stack`, or `list` (no gap, for rows with their own dividers) | `items`, `variant` |
| `LiveRegion` | layout | a block that reloads itself every `seconds` with HTMX: it fetches `url` (usually the page itself) and swaps in the element with the same `region_id` (`hx-select`), so no extra endpoint is needed; `region_id` must be a lowercase slug | `region_id`, `body`, `url`, `seconds` |
| `Modal` | layout | dialog (Alpine + HTMX; not used by a page yet) | `id`, `title`, `body` |
| `PublicFormShell` | layout | public page: `split` (form left, band right; short band on phones) or `notice` (whole page is the band, centred message with an icon) | `page_title`, `header`, `content`, `variant`, `icon` |
| `CrispyForm` | forms | crispy form body (`form_tag=False` inside a parent form) | `form` |
| `PublicPostForm` | forms | `<form method="post">` + CSRF wrapper for public pages | `action`, `body` |
| `PortalPostForm` | forms | Portal `FormPage` POST wrapper (CSRF, multipart, crispy body). `framed` puts the sections in one card with dividers and a footer bar for the buttons; the bulk upload sets `framed=False` because its form sits in a `SectionCard`; `form_id` gives the form an id (the quiz timer submits it) | `action`, `body`, `framed`, `form_id` |
| `ProfileMenu` | layout | Admin top-bar profile dropdown (C11 items, admin_only hiding) | `items` |
| `BlockStack` | block_stack | vertical stack of text or nested components | `blocks` |
| `ButtonRow` | block_stack | actions side by side; wraps on phones, right-aligned from md (table action cells) | `items` |
| `SignOutForm` | actions | POST sign out with CSRF; `variant="light"` on the band | `logout_url`, `variant` |
| `StatCard` | data | stat tile with an icon tile; `tone="lead"` is the solid royal tile | `value`, `label`, `note`, `icon`, `tone` |
| `DataTable` + `Column` | data | table in a card with a light header row; each cell has `data-label` (its column label) and `cell-<key>`. Below md each row becomes a card of label and value pairs; a `PersonCell` becomes the card title. From md the table scrolls sideways inside its box. No sorting yet | `columns`, `rows`, `empty_title` |
| `PersonCell` | data | `Avatar`, name and a small second line (code) for people columns | `name`, `detail` |
| `BadgeNote` | data | a badge with a short reason under it ("Needs attention" on the schedule list) | `badge`, `note` |
| `Badge` | data | status chip with a dot (`success`, `danger`, `warning`), or plain (`info`, `neutral`) | `text`, `tone` |
| `Avatar` | data | initials (first letters of the first two words, or of the email's local part) in a soft circle; the tint is stable per name; full name in `title` | `name`, `size` (`sm`, `md`, `lg`) |
| `ProgressBar` | data | percent bar | `value`, `label`, `tone` |
| `ProgressRing` | data | percent as an SVG ring with the number inside (no chart library); `role="img"` with the label and percent | `value`, `label`, `tone` (`primary`, `indigo`) |
| `KpiSummary` | data | one big number, its label, status chips and an optional `ProgressRing` | `value`, `label`, `chips`, `ring` |
| `PersonList` | data | short list of `PersonCell` rows with a chip on the right (dashboard "Recently enrolled") | `rows` (person, trailing), `title`, `empty_text` |
| `ChartCard` | data | Chart.js card | `title`, `chart_id`, `data_url` |
| `DetailList` | data | label and value pairs for a detail page (`<dl>`); a value may be a component; an empty value shows a dash | `rows` (label, value) |
| `TextBlock` | data | long text a person wrote (assignment instructions, an answer, feedback): line breaks stay, long words wrap, the text is escaped; `empty_text` shows when there is no text | `text`, `empty_text` |
| `EmptyState` | data | icon tile, message and one action; `framed=False` drops the dashed box inside a card | `title`, `text`, `action`, `icon`, `framed` |
| `IconButton` | actions | icon-only link (with `url`) or button; `label` is the `aria-label` and tooltip; `new_tab=True` adds `target="_blank" rel="noopener noreferrer"` (links to other sites, such as meeting links) | `icon`, `label`, `url`, `new_tab` |
| `Button` | actions | `primary`, `secondary`, `danger`, `ghost`, `light`, `glass` (the last two on the band); Lucide icon before the label; `disabled=True` is a state that cannot be clicked (never a link), `title` explains it; `new_tab=True` adds `target="_blank" rel="noopener noreferrer"` (meeting links); `submit=True` (no `url`) submits the form it is in | `label`, `variant`, `url`, `icon`, `disabled`, `title`, `new_tab`, `submit` |
| `PostButton` | actions | one-button POST form with CSRF (when rendered with `request`); `new_tab=True` adds `target="_blank" rel="noopener noreferrer"` (Join) | `label`, `url`, `variant`, `icon`, `new_tab` |
| `QuickAction` | actions | dashboard tile | `label`, `icon`, `url` |
| `ConfirmDialog` | actions | confirm actions in a centred modal (`role="alertdialog"`, backdrop, Escape and click outside close it); renders a POST form with CSRF (when rendered with `request`) and a close button (`dismiss_label`, default Cancel; "Keep lecture" when the action is itself a cancel) | `message`, `confirm_label`, `url`, `trigger_label`, `variant` (`danger`/`primary`), `fields` (hidden name/value pairs), `dismiss_label` |
| `CopyField` | actions | read-only value with a copy button (one-time links) | `label`, `value` |
| `Toast` | actions | success, warning or error message (`tone` is the Django message level tag) | `message`, `tone` |
| `CountdownCard` | lectures | "Up next": title, when and detail lines, "Starts in 1:02:03" (then "Started") and one action; `starts_at` is validated to a UTC ISO string in `data-scheduled-at`, read by `countdownCard` in `static/js/app.js`; with `refresh_url` the card reloads itself every 30 seconds (HTMX) | `title`, `starts_at`, `when`, `detail`, `action`, `refresh_url` |
| `LectureRow` | lectures | one lecture in a short list (guardian "Upcoming classes", the schedule preview); `when` and `detail` show only when set | `title`, `when`, `detail`, `trailing` |
| `Calendar` | lectures | week (seven day cards, side by side from lg) or month (a grid of weeks from md; on phones a list of the month's days that have entries), with previous, Today and next links; each day is a `CalendarDay` (`day`, `items`, `is_today`, `in_month`) and each entry a `CalendarItem` (`time`, `title`, `detail`, `status`, `tone`: `info`, `success`, `warning`, `neutral` or `danger`, `url`); an unsafe item `url` renders as plain text | `days`, `view` (`week`, `month`), `label`, `previous_url`, `today_url`, `next_url`, `empty_text`, `empty_day_text` |
| `AttemptTimer` | quizzes | the time left in a quiz attempt, kept at the top of the screen (sticky); the last minute turns red and is announced once to screen readers; at zero `attemptTimer` in `static/js/app.js` submits the form `form_id` once with `auto_submit=1`; `deadline` is validated to a UTC ISO string in `data-deadline` | `deadline`, `form_id`, `label` (text without JavaScript) |
| `ExamGuard` | quizzes | exam mode on the attempt page: says what is recorded ("It does not change your score"); with `full_screen` an "Enter full screen" button shows while not in full screen; `examGuard` in `static/js/app.js` posts `kind=left_page` when the page is hidden (with `flag_leaving`) and `kind=left_full_screen` when full screen ends (with `full_screen`) to `event_url`, with the CSRF token of the form `form_id`; nothing is sent while the page navigates (Submit, the timer); an unsafe `event_url` renders empty | `event_url`, `form_id`, `full_screen`, `flag_leaving` |
| `NotificationBell` | nav | top bar bell (6.1): a link to the Notifications page; with JavaScript a click opens the panel (loaded from `notifications:panel` when opened) and the count loads on each page and every 60 seconds (`notifications:count`, HTMX); empty for the super admin | `user`, `unread_count` |
| `NotificationCount` | nav | the bell's unread badge ("99+" above 99) and "Notifications, N unread" for screen readers | `unread_count` |
| `NotificationPanel` | nav | the bell's list: each row a POST button that marks it read and opens its link (unread rows bold, with "Unread:" for screen readers), "Mark all as read" (back to `next_url`), "See all notifications"; unsafe URLs render empty; render with `request` for the CSRF tokens | `rows` (`text`, `when`, `open_url`, `is_read`), `list_url`, `read_all_url`, `next_url` |
| `ChildSwitcher` | nav | guardian top bar: a POST form with a "Child" select that sends on change ("Show" button without JavaScript); `options` (value, label), `chosen`, `url`, `next_url`. Pages get it from `GuardianChildMixin.get_child_switcher()` | `options`, `chosen`, `url`, `next_url` |
| `FilterBar` | nav | search field with an icon + selects and "Apply filters"; "Clear" shows when a filter has a value. Each filter (dict or object) has `name`, `label`, optional `value`, `placeholder`; a filter with `options` (list of value, label) renders a select; a filter with `hidden=True` is a hidden input that keeps a value (such as the chosen tab) and does not count for "Clear"; a select with `kept=True` (a guardian's chosen child) does not count for "Clear", and "Clear" keeps its value; `input_type="date"` renders a date field | `filters` |
| `Pagination` | nav | "Showing X to Y of N", then previous, page numbers (elided when long) and next; `query` keeps the current filters | `page_obj`, `query` |
| `PdfHeader` | pdf | institute header for PDFs | `institute` |

| `Icon` | icon | one Lucide icon from the self-hosted sprite (`{% icon "name" %}` in templates); unknown names render nothing; always `aria-hidden` | `name`, `css_class` |

Form layout objects: `Section(legend, *fields, description="", columns=1)` (title and a one-line explanation on the left, fields on the right from md; `columns=2` puts the fields in two columns; with no legend the fields take the full width), `Row`, `FormActions` (`stacked=True`: cancel becomes a text link and the submit button is full width, for public pages; `save_name` names the main button and `second=(label, name)` adds one more submit button, so a page can tell "Save" from "Submit", sent as `name=1`).

Form widgets (not components): `PasswordInput` (show/hide toggle; static `type="password"` for no-JS and tests). `GroupedCheckboxes` (one fieldset per choice group, for example subjects under each batch; `empty_text` when there are no choices). `OptionRadios` (one choice as full-width rows that wrap long text, in a `radiogroup` with `group_label`; MCQ options in a quiz attempt). `ChipRadios` (one choice as a row of chips in a `radiogroup`; `group_label` names it for screen readers; below sm the chips are 4 equal columns without the check icon, so four marks fit at 360px; used for attendance marks).

Built ahead of the pages that need them, and shown only on `/dev/components/` so far: `Modal`, `Tabs`, `ChartCard`, `PdfHeader`, `HtmxModalForm`. Keep them tested; the lecture, chart and PDF phases use them (audit L12).

## 8. Menus

- A menu item is `MenuItem(label, url_name, icon, menu_key=None, feature=None)`.
- URL names that do not exist yet (pages not built) render as a disabled item with `#`, never `NoReverseMatch`. A test lists the unbuilt ones.
- Feature and sub-admin filtering reads plain attributes (`institute.features`, `user.allowed_menus`), so it works before the Plan and SubAdminProfile models exist.


- Menus are Python config, one class per portal: `AdminMenu`, `TeacherMenu`, `StudentMenu`, `GuardianMenu`.
- Menu choice comes from `user.role`. One user, one role, one menu.
- For `sub_admin`, `TopNav` hides every group whose key is not in `SubAdminProfile.allowed_menus`.
- Menu keys live in one place: `core/menus.py`.
- Each menu is a list of groups and items (label, url name, icon, required feature flag).
- `Sidebar` reads the menu, hides items for features the institute's plan doesn't include.
- Menu items match `FEATURES.md` section 13.
- Admin menus render in `TopNav` (dropdown groups). Teacher, student and guardian menus render in `Sidebar`.

## 9. Testing components

- Each component: one test that renders it with sample props and checks key text and CSS class.
- Each page class: test allowed role passes, other roles get 403.
- A `/dev/components/` page (dev only) shows every component with sample data.

## 10. Adding a new component (checklist)

1. Add the class in the right file under `apps/ui/components/`.
2. Add its template in `apps/ui/templates/ui/components/`.
3. Add a row in the table above.
4. Add a sample to the `/dev/components/` page.
5. Add a render test.
6. Then use it in a page.
