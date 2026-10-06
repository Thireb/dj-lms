from __future__ import annotations

from types import SimpleNamespace

import pytest
from apps.ui import safe_url as safe_url_module
from apps.ui.components.actions import Button, QuickAction
from apps.ui.components.layout import SectionCard, Tabs
from apps.ui.components.lectures import CountdownCard
from apps.ui.safe_url import safe_url

UNSAFE_URLS = [
    "javascript:alert(1)",
    " JavaScript:alert(1)",
    "JaVaScRiPt:alert(1)",
    "java\tscript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "file:///etc/passwd",
    "unknown:foo",
]

SAFE_URLS = [
    "https://example.com/path",
    "http://example.com",
    "mailto:user@example.com",
    "tel:+15551212",
    "/admin/students/",
    "./relative",
    "../up",
    "?page=2",
    "#section",
]


@pytest.mark.parametrize("url", UNSAFE_URLS)
def test_safe_url_helper_rejects_unsafe(url: str) -> None:
    assert safe_url(url) == ""


@pytest.mark.parametrize("url", SAFE_URLS)
def test_safe_url_helper_allows_safe(url: str) -> None:
    assert safe_url(url) == url.replace(" ", "").replace("\t", "")


@pytest.mark.parametrize(
    "factory",
    [
        lambda u: Button("Go", url=u),
        lambda u: QuickAction("Tile", "plus", u),
        lambda u: SectionCard("Title", body="Body", link_url=u),
        lambda u: Tabs([{"id": "a", "label": "A", "url": u}], active="a"),
        lambda u: CountdownCard(
            SimpleNamespace(
                title="Lecture",
                scheduled_at="2026-08-16T15:00:00+00:00",
                meeting_link=u,
            ),
            SimpleNamespace(timezone_label="UTC"),
        ),
    ],
    ids=["button", "quick_action", "section_card", "tabs", "countdown_card"],
)
@pytest.mark.parametrize("unsafe", UNSAFE_URLS)
def test_components_reject_unsafe_urls_in_rendered_html(factory, unsafe: str) -> None:
    html = str(factory(unsafe))
    assert "javascript:" not in html.lower()
    assert "data:" not in html.lower()
    assert "vbscript:" not in html.lower()
    assert unsafe.replace("\t", "") not in html
    if unsafe.startswith("javascript") or "script:" in unsafe.replace("\t", "").lower():
        assert 'href="javascript' not in html.lower()


@pytest.mark.parametrize("safe", SAFE_URLS)
def test_button_renders_safe_href(safe: str) -> None:
    html = str(Button("Go", url=safe))
    normalized = safe.replace("\t", "")
    assert f'href="{normalized}"' in html


def test_button_calls_safe_url(monkeypatch) -> None:
    from apps.ui.components import actions

    calls: list[object] = []

    def _record(url: object) -> str:
        calls.append(url)
        return safe_url_module.safe_url(url)

    monkeypatch.setattr(actions, "safe_url", _record)
    Button("Go", url="https://example.com")
    assert calls == ["https://example.com"]
