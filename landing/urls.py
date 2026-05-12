"""URL configuration for landing app."""
from django.urls import path

from . import views

app_name = "landing"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("contact-us/", views.contact_us, name="contact_us"),
    path("post/<int:pk>/", views.post_detail, name="post_detail"),
    path("biography/<int:pk>/", views.biography_detail, name="biography_detail"),
]
