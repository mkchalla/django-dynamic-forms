from django.urls import path

from . import views

app_name = "formbuilder"

urlpatterns = [
    path("", views.form_list, name="form_list"),
    path("<slug:slug>/", views.form_detail, name="form_detail"),
    path("<slug:slug>/thanks/", views.form_thanks, name="form_thanks"),
]
