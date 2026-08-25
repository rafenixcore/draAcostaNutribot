from django.urls import path

from core.views import echo, health

urlpatterns = [
    path("health", health),
    path("echo/<str:value>", echo),
]
