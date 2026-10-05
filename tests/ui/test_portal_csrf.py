from __future__ import annotations

import re
from typing import Any

import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.test import Client, RequestFactory
from tests.conftest import FakeUser
from tests.ui.support.page_views import DemoAdminPeopleList, DemoTeacherDashboard

_META_CSRF_RE = re.compile(
    r'<meta name="csrf-token" content="([^"]+)"',
)
_BODY_HX_CSRF_RE = re.compile(
    r"""hx-headers='\{"X-CSRFToken": "([^"]+)"\}'""",
)


def _attach_session_and_csrf(request: Any) -> None:
    session_middleware = SessionMiddleware(lambda req: HttpResponse())
    session_middleware.process_request(request)
    request.session.save()
    csrf_middleware = CsrfViewMiddleware(lambda req: HttpResponse())
    csrf_middleware.process_request(request)


def _dispatch_with_csrf(
    view_cls: type,
    user: FakeUser,
    institute: Any,
    path: str,
) -> tuple[HttpResponse, Any]:
    rf = RequestFactory()
    request = rf.get(path)
    _attach_session_and_csrf(request)
    request.user = user
    request.institute = institute
    response = view_cls.as_view()(request)
    return response, request


def _csrf_tokens_from_html(html: str) -> tuple[str, str]:
    meta_match = _META_CSRF_RE.search(html)
    body_match = _BODY_HX_CSRF_RE.search(html)
    assert meta_match is not None, "meta csrf-token missing"
    assert body_match is not None, "body hx-headers missing"
    meta_token = meta_match.group(1)
    body_token = body_match.group(1)
    return meta_token, body_token


def _htmx_echo_client(token: str) -> Client:
    client = Client(enforce_csrf_checks=True)
    client.cookies.load({"csrftoken": token})
    return client


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("view_cls", "path", "user_fixture"),
    [
        (DemoTeacherDashboard, "/test/pages/teacher-dashboard/", "teacher_a"),
        (DemoAdminPeopleList, "/test/pages/admin-people/", "admin_a"),
    ],
    ids=["teacher_dashboard", "admin_people"],
)
def test_portal_page_renders_csrf_meta_and_hx_headers(
    view_cls: type,
    path: str,
    user_fixture: str,
    institute_a: Any,
    request: pytest.FixtureRequest,
) -> None:
    user: FakeUser = request.getfixturevalue(user_fixture)
    response, _get_request = _dispatch_with_csrf(view_cls, user, institute_a, path)
    assert response.status_code == 200
    html = response.content.decode()
    meta_token, body_token = _csrf_tokens_from_html(html)
    assert meta_token
    assert body_token
    assert meta_token == body_token


@pytest.mark.django_db
def test_portal_csrf_token_allows_htmx_post(
    teacher_a: FakeUser, institute_a: Any
) -> None:
    response, _get_request = _dispatch_with_csrf(
        DemoTeacherDashboard,
        teacher_a,
        institute_a,
        "/test/pages/teacher-dashboard/",
    )
    assert response.status_code == 200
    token, _ = _csrf_tokens_from_html(response.content.decode())
    client = _htmx_echo_client(token)
    post_response = client.post(
        "/test/htmx-echo/",
        {},
        HTTP_HX_REQUEST="true",
        HTTP_X_CSRFTOKEN=token,
    )
    assert post_response.status_code == 200
    assert post_response.content == b"htmx-ok"


@pytest.mark.django_db
def test_portal_csrf_post_without_token_is_rejected(
    teacher_a: FakeUser, institute_a: Any
) -> None:
    response, _get_request = _dispatch_with_csrf(
        DemoTeacherDashboard,
        teacher_a,
        institute_a,
        "/test/pages/teacher-dashboard/",
    )
    assert response.status_code == 200
    token, _ = _csrf_tokens_from_html(response.content.decode())
    client = _htmx_echo_client(token)
    post_response = client.post(
        "/test/htmx-echo/",
        {},
        HTTP_HX_REQUEST="true",
    )
    assert post_response.status_code == 403
