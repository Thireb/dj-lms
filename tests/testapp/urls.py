from django.urls import path

from tests.testapp import views

urlpatterns = [
    path("test/htmx-echo/", views.htmx_echo, name="test_htmx_echo"),
]
