"""URL configuration for landing app."""
from django.urls import path

from . import views

app_name = "landing"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("contact/", views.contact_form, name="contact_form"),
    path("post/<int:pk>/", views.post_detail, name="post_detail"),
    path("biography/<int:pk>/", views.biography_detail, name="biography_detail"),
    path("biographies/", views.biographies_alphabetical, name="biographies_alphabetical"),
    path("biographies/by-city/", views.biographies_by_city, name="biographies_by_city"),
    path("search/", views.search_results, name="search_results"),
]
