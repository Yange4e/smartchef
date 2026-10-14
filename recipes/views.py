import uuid
from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST
from dotenv import dotenv_values

from .catalog import CATEGORIES, PRODUCTS, build_products
from .models import SavedRecipe
from .recipe_format import (
    RECIPE_PREFIX,
    parse_recipe_json,
    parse_stored_recipe,
    serialize_recipe,
)


def index(request):
    form_state = request.session.get("smartchef_form", {})
    language = request.POST.get(
        "language",
        request.GET.get("language", form_state.get("language", "kk")),
    )
    if language not in ["kk", "ru"]:
        language = "kk"

    products = form_state.get("products", "")
    selected_products = form_state.get("selected_products", [])
    minutes = form_state.get("minutes", "30")
    vegetarian = form_state.get("vegetarian", False)
    recipe = None
    error = ""
    can_save = False

    if request.method == "POST":
        action = request.POST.get("action", "")
        products = request.POST.get("products", "")
        selected_products = request.POST.getlist("selected_products")
        minutes = request.POST.get("minutes", "30")
        if minutes not in ["15", "30", "60"]:
            minutes = "30"

        vegetarian = request.POST.get("vegetarian") == "1"
        request.session["smartchef_form"] = {
            "language": language,
            "selected_products": selected_products,
            "products": products,
            "minutes": minutes,
            "vegetarian": vegetarian,
        }

        if action == "language":
            if "smartchef_draft" in request.session:
                del request.session["smartchef_draft"]
            recipe = None
            error = ""
        elif action == "generate":
            if "smartchef_draft" in request.session:
                del request.session["smartchef_draft"]

            try:
                selected_products, combined = build_products(
                    selected_products, products, language
                )
                request.session["smartchef_form"][
                    "selected_products"
                ] = selected_products
            except ValueError as ex:
                error = str(ex)
            else:
                config = dotenv_values(settings.BASE_DIR / ".env")
                api_key = (config.get("GEMINI_API_KEY") or "").strip()
                env_model = (
                    config.get("GEMINI_MODEL") or ""
                ).strip() or "gemini-3.8-flash"

                if not api_key or api_key == "PASTE_YOUR_KEY_HERE":
                    if language == "kk":
                        error = (
                            ".env файлына жарамды GEMINI_API_KEY кілтін енгізіңіз."
                        )
                    else:
                        error = "Пожалуйста, укажите действительный GEMINI_API_KEY в файле .env."
                else:
                    veg_str = (
                        "Вегетариандық тағам"
                        if vegetarian
                        else "Вегетариандық емес"
                    )
                    if language == "ru":
                        veg_str = (
                            "Вегетарианское блюдо"
                            if vegetarian
                            else "Обычное блюдо"
                        )

                    if language == "kk":
                        prompt = f"""Сен - кәсіби аспазсың.
Мына өнімдерді пайдаланып, дәл 1 рецепт дайында:
Өнімдер: {combined}
Дайындау уақыты: {minutes} минут
Санаты: {veg_str}
Тіл: Қазақша

Жауапты тек мына JSON құрылымында бер, Markdown қоспа:
{{"title":"Тағам атауы","ingredients":["Ингредиент"],"steps":["Дайындау қадамы"]}}
title 1–120 таңба, ingredients 1–24 жол (әрқайсысы 200 таңбаға дейін),
steps 1–12 жол (әрқайсысы 1200 таңбаға дейін) болсын."""
                    else:
                        prompt = f"""Ты - профессиональный шеф-повар.
Приготовь ровно 1 рецепт, используя следующие продукты:
Продукты: {combined}
Время приготовления: {minutes} минут
Категория: {veg_str}
Язык: Русский

Верни только JSON в этой структуре, без Markdown:
{{"title":"Название блюда","ingredients":["Ингредиент"],"steps":["Шаг приготовления"]}}
title: 1–120 символов, ingredients: 1–24 строки (до 200 символов каждая),
steps: 1–12 строк (до 1200 символов каждая)."""

                    try:
                        from google import genai

                        client = genai.Client(api_key=api_key)
                        response = client.models.generate_content(
                            model=env_model, contents=prompt
                        )
                        recipe_response = (
                            getattr(response, "text", "") or str(response)
                        ).strip()
                        try:
                            recipe = parse_recipe_json(recipe_response)
                        except ValueError as ex:
                            error = (
                                f"Gemini рецепті жарамсыз: {ex}"
                                if language == "kk"
                                else f"Некорректный JSON-рецепт Gemini: {ex}"
                            )
                        else:
                            can_save = True
                            request.session["smartchef_draft"] = {
                                "token": str(uuid.uuid4()),
                                "products": combined,
                                "recipe": serialize_recipe(recipe),
                                "language": language,
                                "minutes": int(minutes),
                                "vegetarian": vegetarian,
                            }
                            error = ""
                    except Exception as ex:
                        error = f"API қатесі: {ex}"

    context = {
        "language": language,
        "products": products,
        "selected_products": selected_products,
        "categories": CATEGORIES,
        "catalog_products": PRODUCTS,
        "catalog_data": {
            "categories": CATEGORIES,
            "products": PRODUCTS,
            "language": language,
        },
        "minutes": minutes,
        "vegetarian": vegetarian,
        "recipe": recipe,
        "error": error,
        "can_save": can_save,
    }
    return render(request, "recipes/index.html", context)


@require_POST
def save_recipe(request):
    draft = request.session.get("smartchef_draft")
    if not draft:
        return redirect("recipes:index")

    recipe, _ = parse_stored_recipe(draft["recipe"])
    metadata = {
        "token": draft["token"],
        "minutes": draft["minutes"],
        "language": draft["language"],
        "vegetarian": draft["vegetarian"],
    }
    stored_recipe = serialize_recipe(recipe, metadata)
    SavedRecipe.objects.get_or_create(
        title=recipe["title"],
        products=draft["products"],
        recipe_text=stored_recipe,
    )
    lang = draft.get("language", "kk")
    return redirect(f"{reverse('recipes:saved_recipes')}?language={lang}")


def saved_recipes(request):
    language = request.GET.get("language", "kk")
    if language not in ["kk", "ru"]:
        language = "kk"

    recipes_list = []
    for saved_recipe in SavedRecipe.objects.all():
        stored_text = saved_recipe.recipe_text
        minutes = None
        recipe_language = None
        recipe_data = None
        if stored_text.startswith(RECIPE_PREFIX):
            recipe_data, metadata = parse_stored_recipe(stored_text)
            minutes = metadata.get("minutes")
            recipe_language = metadata.get("language")
            recipe_text = ""
        else:
            recipe_text = stored_text

        recipes_list.append(
            {
                "id": saved_recipe.id,
                "products": saved_recipe.products,
                "minutes": minutes,
                "language": recipe_language,
                "created_at": saved_recipe.created_at,
                "recipe": recipe_text,
                "recipe_data": recipe_data,
            }
        )

    context = {
        "saved_recipes": recipes_list,
        "language": language,
    }
    return render(request, "recipes/saved.html", context)


@require_http_methods(["GET", "POST"])
def cooking(request, recipe_id=None):
    if recipe_id is None:
        draft = request.session.get("smartchef_draft")
        if not draft:
            return redirect("recipes:index")
        recipe, _ = parse_stored_recipe(draft["recipe"])
        recipe_key = f"draft-{draft['token']}"
        language = draft.get("language", "kk")
        return_url = reverse("recipes:index")
    else:
        try:
            saved_recipe = SavedRecipe.objects.get(pk=recipe_id)
        except SavedRecipe.DoesNotExist:
            return redirect("recipes:saved_recipes")
        try:
            recipe, metadata = parse_stored_recipe(saved_recipe.recipe_text)
        except ValueError:
            return redirect("recipes:saved_recipes")
        recipe_key = f"saved-{saved_recipe.pk}"
        language = metadata.get("language", "kk")
        return_url = reverse("recipes:saved_recipes")

    if language not in ("kk", "ru"):
        language = "kk"

    cooking_states = request.session.get("smartchef_cooking", {})
    state = cooking_states.get(recipe_key, {})
    index = state.get("index", 0)
    if not isinstance(index, int) or not 0 <= index < len(recipe["steps"]):
        index = 0

    if request.method == "POST":
        action = request.POST.get("action")
        action_token = request.POST.get("action_token")
        if (
            action_token
            and action_token == state.get("action_token")
            and action_token != state.get("processed_token")
        ):
            if action == "finish":
                cooking_states.pop(recipe_key, None)
                if cooking_states:
                    request.session["smartchef_cooking"] = cooking_states
                else:
                    request.session.pop("smartchef_cooking", None)
                return redirect(return_url)
            if action == "next":
                index = min(index + 1, len(recipe["steps"]) - 1)
            elif action == "back":
                index = max(index - 1, 0)
            else:
                return redirect(request.path)

            state["index"] = index
            state["processed_token"] = action_token
            state["action_token"] = str(uuid.uuid4())
            cooking_states[recipe_key] = state
            request.session["smartchef_cooking"] = cooking_states
        return redirect(request.path)

    if not state.get("action_token"):
        state["action_token"] = str(uuid.uuid4())
    state["index"] = index
    cooking_states[recipe_key] = state
    request.session["smartchef_cooking"] = cooking_states

    context = {
        "language": language,
        "recipe": recipe,
        "step": recipe["steps"][index],
        "step_number": index + 1,
        "total_steps": len(recipe["steps"]),
        "progress_percent": round((index + 1) / len(recipe["steps"]) * 100),
        "action_token": state["action_token"],
        "return_url": return_url,
    }
    return render(request, "recipes/cooking.html", context)