from django.urls import path
from .views import health_check, route_api

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("route/", route_api, name="route-api"),
]