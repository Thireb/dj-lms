from django.test import Client, override_settings


@override_settings(DEBUG=True)
def test_dev_components_ok_when_debug() -> None:
    client = Client()
    response = client.get("/dev/components/")
    assert response.status_code == 200
    assert b"Component gallery" in response.content
    assert b"Alex Sample" in response.content


@override_settings(DEBUG=True)
def test_dev_components_body_includes_htmx_csrf_headers() -> None:
    client = Client()
    response = client.get("/dev/components/")
    html = response.content.decode()
    body_start = html.index("<body")
    body_tag = html[body_start : html.index(">", body_start) + 1]
    assert "hx-headers" in body_tag
    assert "X-CSRFToken" in body_tag


@override_settings(DEBUG=True)
def test_dev_components_loads_chart_js_in_extra_scripts() -> None:
    client = Client()
    response = client.get("/dev/components/")
    assert b"chart.umd.min.js" in response.content


@override_settings(DEBUG=False)
def test_dev_components_not_found_when_debug_off() -> None:
    client = Client()
    response = client.get("/dev/components/")
    assert response.status_code == 404
