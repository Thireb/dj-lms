from django.urls import path

from apps.notifications import views

app_name = "notifications"

urlpatterns = [
    path("", views.NotificationListPage.as_view(), name="list"),
    path("count/", views.NotificationCountView.as_view(), name="count"),
    path("panel/", views.NotificationPanelView.as_view(), name="panel"),
    path("read-all/", views.NotificationReadAllView.as_view(), name="read_all"),
    path("<int:pk>/open/", views.NotificationOpenView.as_view(), name="open"),
]
