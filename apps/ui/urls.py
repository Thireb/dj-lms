from django.urls import path

from apps.ui.views import dev_components

urlpatterns = [
    path("dev/components/", dev_components.dev_components, name="dev_components"),
]
