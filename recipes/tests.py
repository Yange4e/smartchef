import json
from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from . import ai_adapter
from .ai_adapter import AIAdapterError, AITimeoutError
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
		with self.assertRaises(ValueError):
			parse_recipe_json(
				'{"title":"Бірінші","title":"Екінші","ingredients":["Сүт"],'
				'"steps":["Араластыру"]}'
			)
		with self.assertRaises(ValueError):
			parse_recipe_json(
				'{"title":"Тағам","ingredients":["Сүт"],"steps":["Араластыру"],'
				'"metadata":{}}'
			)
		with self.assertRaises(ValueError):
			parse_recipe_json('{"title":"Тағам","ingredients":["Сүт"]}')

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
	def test_saved_page_uses_recipe_json_fields_for_display(self):
		recipe = {
			"title": "Құймақ",
			"ingredients": ["Жұмыртқа", "Сүт"],
			"steps": ["Қамырды араластырыңыз."],
		}
		SavedRecipe.objects.create(
			title="Ескі атау",
			products="жұмыртқа, сүт",
			recipe_text=serialize_recipe(recipe),
		)

		response = self.client.get(reverse("recipes:saved_recipes"))

		self.assertContains(response, "<h2>Құймақ</h2>")
		self.assertContains(response, "<li>Жұмыртқа</li>")
		self.assertContains(response, "<li>Қамырды араластырыңыз.</li>")
		self.assertNotContains(response, "Ескі атау")

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


class EditorSuggestionTests(TestCase):
	def setUp(self):
		self.original = {
			"title": "Құймақ",
			"ingredients": ["Жұмыртқа", "Сүт"],
			"steps": ["Қамырды араластырыңыз."],
		}
		self.candidate = {
			"title": "Жаңа құймақ",
			"ingredients": ["Жұмыртқа", "Сүт", "Қант"],
			"steps": ["Қамырды араластырыңыз.", "Құймақты пісіріңіз."],
		}
		self.saved_recipe = SavedRecipe.objects.create(
			title=self.original["title"],
			products="жұмыртқа, сүт",
			recipe_text=serialize_recipe(self.original, {"language": "kk"}),
		)
		self.url = reverse("recipes:editor", args=[self.saved_recipe.pk])

	@patch(
		"recipes.views.generate_text",
		return_value=json.dumps(
			{
				"title": "Жаңа құймақ",
				"ingredients": ["Жұмыртқа", "Сүт", "Қант"],
				"steps": ["Қамырды араластырыңыз.", "Құймақты пісіріңіз."],
			},
			ensure_ascii=False,
		),
	)
	def test_candidate_is_pending_and_saved_recipe_is_unchanged(self, generate_text):
		response = self.client.post(
			self.url, {"edit_request": "Қант қосып, тәттілеу ет"}
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Жаңа құймақ")
		self.assertContains(response, 'class="recipe-comparison"')
		self.assertContains(response, 'class="recipe-version recipe-original"')
		self.assertContains(response, 'class="recipe-version recipe-proposal"')
		generate_text.assert_called_once()
		pending = self.client.session["smartchef_editor_pending"]
		self.assertEqual(pending["recipe_id"], self.saved_recipe.pk)
		self.assertEqual(pending["original_text"], self.saved_recipe.recipe_text)
		self.assertEqual(parse_stored_recipe(pending["candidate"])[0], self.candidate)
		self.assertGreater(pending["expires_at"], timezone.now().timestamp())
		self.assertEqual(
			SavedRecipe.objects.get(pk=self.saved_recipe.pk).recipe_text,
			self.saved_recipe.recipe_text,
		)

	def test_editor_reads_recipe_fields_from_recipe_text_not_model_title(self):
		self.saved_recipe.title = "Ескі атау"
		self.saved_recipe.save(update_fields=["title"])

		response = self.client.get(self.url)

		self.assertContains(response, "<title>Рецептті өзгерту — Құймақ</title>")
		self.assertContains(response, "<h3>Құймақ</h3>")
		self.assertContains(response, "<li>Жұмыртқа</li>")
		self.assertContains(response, "<li>Қамырды араластырыңыз.</li>")
		self.assertNotContains(response, "Ескі атау")

	@patch(
		"recipes.views.generate_text",
		return_value='{"title":"Тағам","title":"Қайталанған",'
		'"ingredients":["Өнім"],"steps":["Қадам"]}',
	)
	def test_invalid_ai_json_is_rejected_without_pending(self, generate_text):
		response = self.client.post(
			self.url, {"edit_request": "Рецептті жақсарт"}
		)

		self.assertContains(response, "JSON")
		self.assertNotIn("smartchef_editor_pending", self.client.session)
		generate_text.assert_called_once()
		self.assertEqual(
			SavedRecipe.objects.get(pk=self.saved_recipe.pk).recipe_text,
			self.saved_recipe.recipe_text,
		)

	@patch("recipes.views.generate_text")
	def test_invalid_request_length_does_not_call_ai(self, generate_text):
		for edit_request in ("ab", "x" * 301):
			with self.subTest(length=len(edit_request)):
				response = self.client.post(
					self.url, {"edit_request": edit_request}
				)
				self.assertContains(response, "3–300")
		generate_text.assert_not_called()

	@patch("recipes.views.generate_text", return_value="")
	def test_blank_ai_response_shows_clear_message(self, generate_text):
		response = self.client.post(
			self.url, {"edit_request": "Рецептті жақсарт"}
		)

		self.assertContains(response, "AI бос жауап қайтарды")
		self.assertNotIn("smartchef_editor_pending", self.client.session)

	@patch("recipes.views.generate_text", side_effect=AITimeoutError("timeout"))
	def test_ai_timeout_shows_clear_message(self, generate_text):
		response = self.client.post(
			self.url, {"edit_request": "Рецептті жақсарт"}
		)

		self.assertContains(response, "уақыты аяқталды")
		self.assertNotIn("smartchef_editor_pending", self.client.session)

	def test_undo_requires_matching_pending_token(self):
		session = self.client.session
		session["smartchef_editor_pending"] = {
			"recipe_id": self.saved_recipe.pk,
			"original_text": self.saved_recipe.recipe_text,
			"candidate": serialize_recipe(self.candidate),
			"token": "expected-token",
			"expires_at": (timezone.now() + timedelta(minutes=5)).timestamp(),
		}
		session.save()
		undo_url = reverse("recipes:editor_undo", args=[self.saved_recipe.pk])

		response = self.client.post(undo_url, {"token": "wrong-token"})
		self.assertContains(response, "Ұсыныс табылмады")
		self.assertIn("smartchef_editor_pending", self.client.session)

		response = self.client.post(undo_url, {"token": "expected-token"})
		self.assertContains(response, "Сақталған рецепт өзгерген жоқ")
		self.assertNotIn("smartchef_editor_pending", self.client.session)
		self.assertEqual(
			SavedRecipe.objects.get(pk=self.saved_recipe.pk).recipe_text,
			self.saved_recipe.recipe_text,
		)

	def test_expired_pending_is_removed(self):
		session = self.client.session
		session["smartchef_editor_pending"] = {
			"recipe_id": self.saved_recipe.pk,
			"original_text": self.saved_recipe.recipe_text,
			"candidate": serialize_recipe(self.candidate),
			"token": "expired-token",
			"expires_at": (timezone.now() - timedelta(seconds=1)).timestamp(),
		}
		session.save()

		self.client.get(reverse("recipes:saved_recipes"))

		self.assertNotIn("smartchef_editor_pending", self.client.session)

	def test_pending_candidate_is_isolated_to_its_session(self):
		session = self.client.session
		session["smartchef_editor_pending"] = {
			"recipe_id": self.saved_recipe.pk,
			"original_text": self.saved_recipe.recipe_text,
			"candidate": serialize_recipe(self.candidate),
			"token": "session-token",
			"expires_at": (timezone.now() + timedelta(minutes=5)).timestamp(),
		}
		session.save()

		other_client = Client()
		response = other_client.get(reverse("recipes:saved_recipes"))

		self.assertNotContains(response, "Жаңа құймақ")
		self.assertNotIn("smartchef_editor_pending", other_client.session)

	@patch("google.genai.Client")
	@patch(
		"recipes.ai_adapter.os.getenv",
		side_effect=lambda name: {
			"GEMINI_API_KEY": "test-key",
			"GEMINI_MODEL": "existing-model",
		}.get(name),
	)
	@patch("recipes.ai_adapter.load_dotenv")
	def test_ai_adapter_reads_existing_model_from_environment(
		self, load_dotenv, getenv, client_class
	):
		client_class.return_value.models.generate_content.return_value.text = (
			"ответ"
		)

		result = ai_adapter.generate_text("prompt")

		self.assertEqual(result, "ответ")
		load_dotenv.assert_called_once()
		getenv.assert_any_call("GEMINI_API_KEY")
		client_class.assert_called_once()
		client_class.return_value.models.generate_content.assert_called_once_with(
			model="existing-model", contents="prompt"
		)

	@patch("google.genai.Client")
	@patch("recipes.ai_adapter.os.getenv", return_value="test-key")
	@patch("recipes.ai_adapter.load_dotenv")
	def test_ai_adapter_logs_and_classifies_provider_errors(
		self, load_dotenv, getenv, client_class
	):
		from google.genai.errors import APIError

		client_class.return_value.models.generate_content.side_effect = APIError(
			code=401, response_json={"error": {"message": "invalid key"}}
		)

		with self.assertLogs("recipes.ai_adapter", level="ERROR"):
			with self.assertRaises(AIAdapterError) as raised:
				ai_adapter.generate_text("prompt")

		self.assertIn("Gemini API", raised.exception.user_message)
		self.assertNotIn("test-key", raised.exception.user_message)

	@patch("recipes.ai_adapter.time.sleep")
	@patch("google.genai.Client")
	@patch("recipes.ai_adapter.os.getenv", return_value="test-key")
	@patch("recipes.ai_adapter.load_dotenv")
	def test_ai_adapter_retries_transient_server_errors_once(
		self, load_dotenv, getenv, client_class, sleep
	):
		from google.genai.errors import APIError

		generate_content = client_class.return_value.models.generate_content
		generate_content.side_effect = [
			APIError(code=503, response_json={"error": {"message": "busy"}}),
			type("Response", (), {"text": "  ұсыныс  "})(),
		]

		result = ai_adapter.generate_text("prompt")

		self.assertEqual(result, "ұсыныс")
		self.assertEqual(generate_content.call_count, 2)
		sleep.assert_called_once_with(1)

	@patch("recipes.ai_adapter.time.sleep")
	@patch("google.genai.Client")
	@patch("recipes.ai_adapter.os.getenv", return_value="test-key")
	@patch("recipes.ai_adapter.load_dotenv")
	def test_ai_adapter_reports_server_error_after_retry(
		self, load_dotenv, getenv, client_class, sleep
	):
		from google.genai.errors import APIError

		generate_content = client_class.return_value.models.generate_content
		generate_content.side_effect = [
			APIError(code=503, response_json={"error": {"message": "busy"}}),
			APIError(code=503, response_json={"error": {"message": "busy"}}),
		]

		with self.assertLogs("recipes.ai_adapter", level="ERROR"):
			with self.assertRaises(AIAdapterError) as raised:
				ai_adapter.generate_text("prompt")

		self.assertIn("уақытша", raised.exception.user_message)
		self.assertIn("временная", raised.exception.user_message_ru)
		self.assertEqual(generate_content.call_count, 2)
		sleep.assert_called_once_with(1)

	@patch(
		"recipes.views.generate_text",
		side_effect=AIAdapterError(
			"provider details",
			"Gemini-де модель табылмады.",
			"Модель не найдена.",
		),
	)
	def test_provider_cause_is_shown_in_browser(self, generate_text):
		response = self.client.post(
			self.url, {"edit_request": "Рецептті жақсарт", "language": "ru"}
		)

		self.assertContains(response, "Модель не найдена.")
		self.assertNotContains(response, "provider details")
