from django.test import Client, override_settings


@override_settings(DEBUG=True)
def test_htmx_post_succeeds_with_csrf_header() -> None:
    client = Client(enforce_csrf_checks=True)
    client.get("/dev/components/")
    token = client.cookies["csrftoken"].value
    response = client.post(
        "/test/htmx-echo/",
        {},
        HTTP_HX_REQUEST="true",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 200
    assert response.content == b"htmx-ok"


@override_settings(DEBUG=True)
def test_htmx_post_without_csrf_is_rejected() -> None:
    client = Client(enforce_csrf_checks=True)
    response = client.post(
        "/test/htmx-echo/",
        {},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 403
