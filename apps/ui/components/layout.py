from __future__ import annotations

from apps.ui.components.base import Component
from apps.ui.components.nav import NotificationBell


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


class TopNavShell(Component):
    template_name = "ui/components/top_nav_shell.html"

    def __init__(self, portal, user, active=None, groups=None, **props):
        super().__init__(
            portal=portal,
            user=user,
            active=active,
            groups=groups or [],
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
        return ctx


class SidebarShell(Component):
    template_name = "ui/components/sidebar_shell.html"

    def __init__(self, portal, user, active=None, groups=None, **props):
        super().__init__(
            portal=portal,
            user=user,
            active=active,
            groups=groups or [],
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
        return ctx


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

    def __init__(self, title, breadcrumb=None, actions=None, **props):
        super().__init__(
            title=title,
            breadcrumb=breadcrumb or [],
            actions=actions or [],
            **props,
        )


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
            link_url=link_url,
            link_label=link_label,
            **props,
        )


class Tabs(Component):
    template_name = "ui/components/tabs.html"

    def __init__(self, tabs, active=None, **props):
        super().__init__(tabs=tabs, active=active, **props)


class Modal(Component):
    template_name = "ui/components/modal.html"

    def __init__(self, id, title, body, **props):
        super().__init__(id=id, title=title, body=body, **props)
