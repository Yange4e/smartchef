from django.test import TestCase
from django.urls import reverse
from .models import SavedRecipe
from .recipe_format import (
	RECIPE_PREFIX,
	parse_recipe_json,
	parse_stored_recipe,
	serialize_recipe,
)


class RecipeFormatTests(TestCase):
	def test_parses_and_serializes_valid_recipe_json(self):
		recipe = {
			"title": "Құймақ",
			"ingredients": ["Жұмыртқа", "Сүт"],
			"steps": ["Ингредиенттерді араластырыңыз."],
		}

		self.assertEqual(parse_recipe_json(serialize_recipe(recipe)), recipe)
		self.assertTrue(serialize_recipe(recipe).startswith(RECIPE_PREFIX))

	def test_rejects_recipe_values_outside_limits(self):
		with self.assertRaises(ValueError):
			parse_recipe_json('{"title":"","ingredients":["Сүт"],"steps":["Араластыру"]}')
		with self.assertRaises(ValueError):
			parse_recipe_json(
				'{"title":"Тағам","ingredients":[],"steps":["Араластыру"]}'
			)
		with self.assertRaises(ValueError):
			parse_recipe_json(
				'{"title":"Тағам","ingredients":["Сүт"],"steps":["Араластыру"],'
				'"extra":"unsupported"}'
			)

	def test_accepts_limits_and_rejects_values_over_them(self):
		recipe = {
			"title": "T" * 120,
			"ingredients": ["I" * 200] * 24,
			"steps": ["S" * 1200] * 12,
		}
		self.assertEqual(parse_recipe_json(serialize_recipe(recipe)), recipe)

		invalid_recipes = [
			{**recipe, "title": "T" * 121},
			{**recipe, "ingredients": recipe["ingredients"] + ["I"]},
			{**recipe, "ingredients": ["I" * 201]},
			{**recipe, "steps": recipe["steps"] + ["S"]},
			{**recipe, "steps": ["S" * 1201]},
		]
		for invalid_recipe in invalid_recipes:
			with self.subTest(recipe=invalid_recipe):
				with self.assertRaises(ValueError):
					parse_recipe_json(serialize_recipe(invalid_recipe))

	def test_stored_recipe_metadata_is_separate_from_cooking_fields(self):
		recipe = {
			"title": "Құймақ",
			"ingredients": ["Жұмыртқа", "Сүт"],
			"steps": ["Араластыру"],
		}

		parsed, metadata = parse_stored_recipe(
			serialize_recipe(recipe, {"language": "kk", "minutes": 15})
		)

		self.assertEqual(parsed, recipe)
		self.assertEqual(metadata, {"language": "kk", "minutes": 15})


class CookingViewTests(TestCase):
	def setUp(self):
		self.recipe = {
			"title": "Құймақ",
			"ingredients": ["Жұмыртқа", "Сүт"],
			"steps": ["Қамырды араластырыңыз.", "Құймақты қуырыңыз."],
		}
		self.saved_recipe = SavedRecipe.objects.create(
			title=self.recipe["title"],
			products="жұмыртқа, сүт",
			recipe_text=serialize_recipe(self.recipe, {"language": "kk"}),
		)
		self.url = reverse("recipes:saved_cooking", args=[self.saved_recipe.pk])

	def test_shows_one_step_and_progress(self):
		response = self.client.get(self.url)

		self.assertContains(response, "Қамырды араластырыңыз.")
		self.assertNotContains(response, "Құймақты қуырыңыз.")
		self.assertContains(response, 'value="1" max="2"')

	def test_draft_can_start_cooking_from_the_session(self):
		session = self.client.session
		session["smartchef_draft"] = {
			"token": "draft-token",
			"products": "жұмыртқа, сүт",
			"recipe": serialize_recipe(self.recipe),
			"language": "kk",
		}
		session.save()

		response = self.client.get(reverse("recipes:cooking"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Қамырды араластырыңыз.")

	def test_repeated_navigation_submission_does_not_skip_a_step(self):
		response = self.client.get(self.url)
		action_token = response.context["action_token"]
		payload = {"action": "next", "action_token": action_token}

		self.client.post(self.url, payload)
		response = self.client.post(self.url, payload)
		response = self.client.get(self.url)

		self.assertContains(response, "Құймақты қуырыңыз.")
		self.assertContains(response, 'value="2" max="2"')

	def test_back_and_finish_actions(self):
		response = self.client.get(self.url)
		self.client.post(
			self.url,
			{"action": "next", "action_token": response.context["action_token"]},
		)
		response = self.client.get(self.url)
		self.client.post(
			self.url,
			{"action": "back", "action_token": response.context["action_token"]},
		)
		response = self.client.get(self.url)
		self.assertContains(response, "Қамырды араластырыңыз.")

		self.client.post(
			self.url,
			{"action": "finish", "action_token": response.context["action_token"]},
		)
		self.assertNotIn("smartchef_cooking", self.client.session)


class SavedRecipeViewTests(TestCase):
	def test_save_post_creates_recipe_and_redirects(self):
		recipe = {
			"title": "Құймақ",
			"ingredients": ["Жұмыртқа", "Сүт"],
			"steps": ["Ингредиенттерді араластырыңыз."],
		}
		session = self.client.session
		session["smartchef_draft"] = {
			"token": "draft-token",
			"products": "жұмыртқа, сүт",
			"recipe": serialize_recipe(recipe),
			"language": "kk",
			"minutes": 15,
			"vegetarian": False,
		}
		session.save()

		response = self.client.post(reverse("recipes:save_recipe"))

		self.assertRedirects(
			response,
			f"{reverse('recipes:saved_recipes')}?language=kk",
		)
		saved_recipe = SavedRecipe.objects.get()
		self.assertEqual(saved_recipe.title, "Құймақ")
		self.assertEqual(saved_recipe.products, "жұмыртқа, сүт")
		self.assertTrue(saved_recipe.recipe_text.startswith(RECIPE_PREFIX))
		self.assertEqual(parse_stored_recipe(saved_recipe.recipe_text)[0], recipe)

	def test_saved_recipes_displays_recipe_and_cooking_link(self):
		recipe = {
			"title": "Құймақ",
			"ingredients": ["Жұмыртқа", "Сүт"],
			"steps": ["Ингредиенттерді араластырыңыз."],
		}
		SavedRecipe.objects.create(
			title="Құймақ",
			products="жұмыртқа, сүт",
			recipe_text=serialize_recipe(recipe),
		)

		response = self.client.get(reverse("recipes:saved_recipes"))

		self.assertContains(response, "Құймақ")
		self.assertContains(response, "жұмыртқа, сүт")
		self.assertContains(response, "Ингредиенттерді араластырыңыз.")
		self.assertContains(
			response,
			reverse("recipes:saved_cooking", args=[SavedRecipe.objects.get().pk]),
		)
