from __future__ import annotations

from django.contrib.messages import get_messages

from apps.ui.brand import BRAND_MARK, BRAND_NAME, user_badge
from apps.ui.components.actions import Toast
from apps.ui.components.base import Component, render_component_template
from apps.ui.components.nav import NotificationBell
from apps.ui.safe_url import safe_url


def render_toasts(request) -> list:
    """One Toast per Django message; reading them marks them as shown."""
    if request is None:
        return []
    return [
        Toast(str(message), tone=message.level_tag or "info").render(request=request)
        for message in get_messages(request)
    ]


class TopNav(Component):
    template_name = "ui/components/top_nav.html"

    def __init__(self, portal, active=None, groups=None, **props):
        super().__init__(
            portal=portal,
            active=active,
            groups=groups or [],
            **props,
        )


class Sidebar(Component):
    template_name = "ui/components/sidebar.html"

    def __init__(self, portal, active=None, groups=None, **props):
        super().__init__(
            portal=portal,
            active=active,
            groups=groups or [],
            **props,
        )

    def get_context(self):
        ctx = super().get_context()
        ctx.update(brand_mark=BRAND_MARK, brand_name=BRAND_NAME)
        return ctx


class TopNavShell(Component):
    template_name = "ui/components/top_nav_shell.html"

    def __init__(
        self,
        portal,
        user,
        active=None,
        groups=None,
        institute=None,
        **props,
    ):
        if groups is None:
            from apps.ui.menus.registry import build_menu_groups

            inst = institute or getattr(user, "institute", None)
            groups = build_menu_groups(portal, user, inst)
        super().__init__(
            portal=portal,
            user=user,
            active=active,
            groups=groups,
            institute=institute,
            **props,
        )

    def get_context(self):
        ctx = super().get_context()
        ctx["portal"] = self.props["portal"]
        ctx["page_title"] = self.props.get("page_title", "")
        ctx["content"] = self.props.get("content", "")
        ctx["top_nav"] = TopNav(
            portal=self.props["portal"],
            active=self.props.get("active"),
            groups=self.props.get("groups") or [],
        )
        ctx["notification_bell"] = NotificationBell(
            user=self.props["user"],
            unread_count=self.props.get("unread_count", 0),
        )
        from apps.ui.components.profile_menu import ProfileMenu
        from apps.ui.menus.registry import build_profile_menu_items

        inst = self.props.get("institute") or getattr(
            self.props["user"], "institute", None
        )
        profile_items = build_profile_menu_items(self.props["user"], inst)
        ctx["profile_menu"] = ProfileMenu(
            items=profile_items, badge=user_badge(self.props["user"])
        )
        ctx.update(brand_mark=BRAND_MARK, brand_name=BRAND_NAME)
        return ctx

    def render(self, request=None):
        ctx = self.get_context()
        if request is not None:
            ctx["top_nav"] = ctx["top_nav"].render(request=request)
            ctx["notification_bell"] = ctx["notification_bell"].render(request=request)
            ctx["profile_menu"] = ctx["profile_menu"].render(request=request)
            content = ctx.get("content")
            if content is not None and hasattr(content, "render"):
                ctx["content"] = content.render(request=request)
        ctx["toasts"] = render_toasts(request)
        return render_component_template(self, ctx, request=request)


class SidebarShell(Component):
    template_name = "ui/components/sidebar_shell.html"

    def __init__(
        self,
        portal,
        user,
        active=None,
        groups=None,
        institute=None,
        **props,
    ):
        if groups is None:
            from apps.ui.menus.registry import build_menu_groups

            inst = institute or getattr(user, "institute", None)
            groups = build_menu_groups(portal, user, inst)
        super().__init__(
            portal=portal,
            user=user,
            active=active,
            groups=groups,
            institute=institute,
            **props,
        )

    def get_context(self):
        ctx = super().get_context()
        ctx["portal"] = self.props["portal"]
        ctx["page_title"] = self.props.get("page_title", "")
        ctx["content"] = self.props.get("content", "")
        ctx["sidebar"] = Sidebar(
            portal=self.props["portal"],
            active=self.props.get("active"),
            groups=self.props.get("groups") or [],
        )
        ctx["notification_bell"] = NotificationBell(
            user=self.props["user"],
            unread_count=self.props.get("unread_count", 0),
        )
        ctx["badge"] = user_badge(self.props["user"])
        ctx.update(brand_mark=BRAND_MARK, brand_name=BRAND_NAME)
        return ctx

    def render(self, request=None):
        ctx = self.get_context()
        if request is not None:
            ctx["sidebar"] = ctx["sidebar"].render(request=request)
            ctx["notification_bell"] = ctx["notification_bell"].render(request=request)
            content = ctx.get("content")
            if content is not None and hasattr(content, "render"):
                ctx["content"] = content.render(request=request)
        ctx["toasts"] = render_toasts(request)
        return render_component_template(self, ctx, request=request)


class HeroBanner(Component):
    template_name = "ui/components/hero_banner.html"

    def __init__(
        self,
        title,
        subtitle="",
        chips=None,
        actions=None,
        **props,
    ):
        super().__init__(
            title=title,
            subtitle=subtitle,
            chips=chips or [],
            actions=actions or [],
            **props,
        )


class PageHeader(Component):
    template_name = "ui/components/page_header.html"

    def __init__(
        self, title, breadcrumb=None, actions=None, subtitle="", clock=False, **props
    ):
        super().__init__(
            title=title,
            breadcrumb=breadcrumb or [],
            actions=actions or [],
            subtitle=subtitle,
            clock=clock,
            **props,
        )

    def render(self, request=None):
        ctx = self.get_context()
        if request is not None:
            actions = []
            for action in ctx.get("actions") or []:
                if hasattr(action, "render"):
                    actions.append(action.render(request=request))
                else:
                    actions.append(action)
            ctx["actions"] = actions
        return render_component_template(self, ctx, request=request)


class SectionCard(Component):
    template_name = "ui/components/section_card.html"

    def __init__(
        self,
        title,
        body,
        link_url=None,
        link_label="View all",
        **props,
    ):
        super().__init__(
            title=title,
            body=body,
            link_url=safe_url(link_url) if link_url is not None else None,
            link_label=link_label,
            **props,
        )

    def render(self, request=None):
        ctx = self.get_context()
        body = ctx.get("body")
        if request is not None and body is not None and hasattr(body, "render"):
            ctx["body"] = body.render(request=request)
        return render_component_template(self, ctx, request=request)


class Tabs(Component):
    template_name = "ui/components/tabs.html"

    def __init__(self, tabs, active=None, **props):
        safe_tabs = []
        for tab in tabs:
            if isinstance(tab, dict):
                item = dict(tab)
            else:
                item = dict(vars(tab))
            if "url" in item:
                item["url"] = safe_url(item["url"])
            safe_tabs.append(item)
        super().__init__(tabs=safe_tabs, active=active, **props)


class Modal(Component):
    template_name = "ui/components/modal.html"

    def __init__(self, id, title, body, **props):
        super().__init__(id=id, title=title, body=body, **props)


class PublicFormShell(Component):
    """Public pages (sign-in, set password, notices) in the Lexicon look.

    ``variant="split"``: form on the left, the Lexicon band on the right
    (a short band above the form on phones). ``variant="notice"``: the whole
    page is the band with a centred message, for Access paused and refusals.
    """

    template_name = "ui/layouts/public.html"

    def __init__(
        self,
        page_title="",
        header=None,
        content=None,
        variant="split",
        icon="",
        **props,
    ):
        super().__init__(
            page_title=page_title,
            header=header,
            content=content,
            variant=variant,
            icon=icon,
            **props,
        )

    def get_context(self):
        from apps.ui.brand import BRAND_LONG_NAME

        ctx = super().get_context()
        ctx.update(
            brand_mark=BRAND_MARK, brand_name=BRAND_NAME, brand_long=BRAND_LONG_NAME
        )
        return ctx

    def render(self, request=None):
        ctx = self.get_context()
        if request is not None:
            for key in ("header", "content"):
                val = ctx.get(key)
                if val is not None and hasattr(val, "render"):
                    ctx[key] = val.render(request=request)
        return render_component_template(self, ctx, request=request)
