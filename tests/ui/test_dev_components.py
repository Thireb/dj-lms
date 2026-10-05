from django.test import Client, override_settings


@override_settings(DEBUG=True)
def test_dev_components_ok_when_debug() -> None:
    client = Client()
    response = client.get("/dev/components/")
    assert response.status_code == 200
    assert b"Component gallery" in response.content
    assert b"Alex Sample" in response.content


@override_settings(DEBUG=False)
def test_dev_components_not_found_when_debug_off() -> None:
    client = Client()
    response = client.get("/dev/components/")
    assert response.status_code == 404
