# COMPONENTS

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
    forms.py       # CrispyForm, PublicPostForm
    block_stack.py # BlockStack
    data.py        # StatCard, DataTable, Column, Badge, StatusBadge, Avatar,
                   # ProgressBar, ChartCard, EmptyState
    actions.py     # Button, QuickAction, ConfirmDialog, Toast
    lectures.py    # CountdownCard, LectureRow, ScheduleList
    nav.py         # NotificationBell, FilterBar, Pagination
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
# apps/ui/components/base.py
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

class Component:
    template_name: str = ""

    def __init__(self, **props):
        self.props = props

    def get_context(self) -> dict:
        return {"c": self, **self.props}

    def render(self) -> str:
        return mark_safe(render_to_string(self.template_name, self.get_context()))

    def __html__(self) -> str:   # lets templates write {{ component }}
        return self.render()

    __str__ = __html__
```

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
        ctx["shell"] = self.shell_class(portal=self.portal, user=self.request.user, active=self.get_active_item())   # TopNavShell for admin, SidebarShell for others
        ctx["header"] = self.get_header()
        ctx.update(self.get_components())
        return ctx


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

Base page types: `DashboardPage`, `ListPage`, `DetailPage`, `FormPage`. They match the page patterns in `UI-GUIDELINES.md`.

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

- Modal forms: subclass `HtmxModalForm` (same as `BaseForm`, renders inside `Modal`, submits with HTMX).
- Template: `{% crispy form %}` inside the `FormPage` layout. That is the only form tag allowed in templates.

## 7. Component list

Every item here is a class. Names are fixed.

| Class | File | Purpose | Main props |
|---|---|---|---|
| `TopNavShell` | layout | admin shell: top menu bar with dropdown groups | `portal`, `user`, `active` |
| `SidebarShell` | layout | teacher/student/guardian shell: sidebar + top bar | `portal`, `user`, `active` |
| `TopNav` | layout | grouped dropdown menu from a menu config | `portal`, `active` |
| `Sidebar` | layout | grouped sidebar menu from a menu config | `portal`, `active` |
| `HeroBanner` | layout | dashboard welcome banner with chips and actions | `title`, `subtitle`, `chips`, `actions` |
| `PageHeader` | layout | title, breadcrumb, actions | `title`, `breadcrumb`, `actions` |
| `SectionCard` | layout | titled card with "View all" | `title`, `body`, `link_url`, `link_label` |
| `Tabs` | layout | tabs with HTMX swap | `tabs`, `active` |
| `Modal` | layout | dialog (Alpine + HTMX) | `id`, `title`, `body` |
| `PublicFormShell` | layout | centered public page (sign-in, set password) | `page_title`, `header`, `content` |
| `CrispyForm` | forms | crispy form body (`form_tag=False` inside a parent form) | `form` |
| `PublicPostForm` | forms | `<form method="post">` + CSRF wrapper for public pages | `action`, `body` |
| `BlockStack` | block_stack | vertical stack of text or nested components | `blocks` |
| `SignOutForm` | actions | POST sign out with CSRF | `logout_url` |
| `StatCard` | data | number + label + note | `value`, `label`, `note`, `icon`, `tone` |
| `DataTable` + `Column` | data | table with sort, empty state | `columns`, `rows` |
| `Badge` | data | status pill | `text`, `tone` |
| `Avatar` | data | initials circle | `name`, `size` |
| `ProgressBar` | data | percent bar | `value`, `label`, `tone` |
| `ChartCard` | data | Chart.js card | `title`, `chart_id`, `data_url` |
| `EmptyState` | data | message + one action | `title`, `text`, `action` |
| `Button` | actions | primary, secondary, danger, ghost | `label`, `variant`, `url`, `icon` |
| `QuickAction` | actions | dashboard tile | `label`, `icon`, `url` |
| `ConfirmDialog` | actions | confirm destructive actions | `message`, `confirm_label`, `url` |
| `Toast` | actions | success/error message | `message`, `tone` |
| `CountdownCard` | lectures | "Up next" with live timer + Join | `lecture`, `viewer`; `scheduled_at` is validated to a UTC ISO string in `data-scheduled-at`, read by `countdownCard` in `static/js/app.js` |
| `LectureRow` | lectures | one lecture in a list | `lecture`, `viewer` |
| `ScheduleList` | lectures | lectures grouped by day | `lectures`, `viewer` |
| `NotificationBell` | nav | bell + unread count | `user` |
| `FilterBar` | nav | search + selects | `filters` |
| `Pagination` | nav | page links | `page_obj` |
| `PdfHeader` | pdf | institute header for PDFs | `institute` |

Form layout objects: `Section`, `Row`, `FormActions`.

Form widgets (not components): `PasswordInput` (show/hide toggle; static `type="password"` for no-JS and tests).

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
