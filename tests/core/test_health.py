"""Uptime check (backlog S13) and the TLS proxy setting (backlog S11)."""

from __future__ import annotations

from unittest import mock

import pytest
from config.settings.proxy import proxy_ssl_header
from django.db import DatabaseError
from django.test import Client


@pytest.mark.django_db
def test_health_is_open_and_shows_no_data() -> None:
    response = Client().get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "no-cache" in response["Cache-Control"]
    assert Client().head("/health/").status_code == 200


@pytest.mark.django_db
def test_health_refuses_a_post() -> None:
    assert Client().post("/health/").status_code == 405


@pytest.mark.django_db
def test_health_is_503_when_the_database_fails() -> None:
    with mock.patch(
        "apps.core.health.connection.cursor", side_effect=DatabaseError("down")
    ):
        response = Client().get("/health/")
    assert response.status_code == 503
    assert response.json() == {"status": "error"}
    assert b"down" not in response.content


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", None),
        ("  ", None),
        ("HTTP_X_FORWARDED_PROTO", ("HTTP_X_FORWARDED_PROTO", "https")),
        (" HTTP_X_FORWARDED_PROTO ", ("HTTP_X_FORWARDED_PROTO", "https")),
    ],
)
def test_proxy_ssl_header(value, expected) -> None:
    assert proxy_ssl_header(value) == expected


@pytest.mark.parametrize("value", ["X-Forwarded-Proto", "http_x_forwarded_proto"])
def test_proxy_ssl_header_refuses_a_wrong_name(value) -> None:
    with pytest.raises(ValueError, match="HTTP_X_FORWARDED_PROTO"):
        proxy_ssl_header(value)
