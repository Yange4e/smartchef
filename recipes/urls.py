from django.urls import path
from . import views
from .editor import editor

app_name = "recipes"
urlpatterns = [
    path("", views.index, name="index"),
    path("save/", views.save_recipe, name="save_recipe"),
    path("saved/", views.saved_recipes, name="saved_recipes"),
    path("editor/<int:recipe_id>/", editor, name="editor"),
    path("editor/<int:recipe_id>/undo/", editor, name="editor_undo"),
    path("cooking/", views.cooking, name="cooking"),
    path("cooking/<int:recipe_id>/", views.cooking, name="saved_cooking"),
]