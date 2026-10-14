from django.urls import path
from . import views

app_name = "recipes"
urlpatterns = [
    path("", views.index, name="index"),
    path("save/", views.save_recipe, name="save_recipe"),
    path("saved/", views.saved_recipes, name="saved_recipes"),
    path("cooking/", views.cooking, name="cooking"),
    path("cooking/<int:recipe_id>/", views.cooking, name="saved_cooking"),
]