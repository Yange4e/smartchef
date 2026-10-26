import json


RECIPE_PREFIX = "SMARTCHEF_JSON_V1\n"


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Recipe JSON contains a duplicate key.")
        result[key] = value
    return result


def validate_recipe_structure(data):
    if not isinstance(data, dict):
        raise ValueError("Recipe must be a JSON object.")
    if set(data) - {"title", "ingredients", "steps", "metadata"}:
        raise ValueError("Recipe contains unsupported fields.")

    title = data.get("title")
    ingredients = data.get("ingredients")
    steps = data.get("steps")

    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
        raise ValueError("Recipe title must contain 1–120 characters.")
    if (
        not isinstance(ingredients, list)
        or not 1 <= len(ingredients) <= 24
        or any(
            not isinstance(item, str) or not 1 <= len(item.strip()) <= 200
            for item in ingredients
        )
    ):
        raise ValueError("Recipe ingredients must contain 1–24 strings of 1–200 characters.")
    if (
        not isinstance(steps, list)
        or not 1 <= len(steps) <= 12
        or any(
            not isinstance(item, str) or not 1 <= len(item.strip()) <= 1200
            for item in steps
        )
    ):
        raise ValueError("Recipe steps must contain 1–12 strings of 1–1200 characters.")

    return {
        "title": title.strip(),
        "ingredients": [item.strip() for item in ingredients],
        "steps": [item.strip() for item in steps],
    }


def parse_recipe_json(raw):
    if not isinstance(raw, str):
        raise ValueError("Recipe response must be text.")

    payload = raw.removeprefix(RECIPE_PREFIX)
    try:
        data = json.loads(payload, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise ValueError("Recipe response is not valid JSON.") from exc
    if not isinstance(data, dict) or set(data) != {"title", "ingredients", "steps"}:
        raise ValueError("Recipe response must contain only title, ingredients, and steps.")
    return validate_recipe_structure(data)


def serialize_recipe(recipe, metadata=None):
    payload = validate_recipe_structure(recipe)
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise ValueError("Recipe metadata must be a JSON object.")
        payload["metadata"] = metadata
    return f"{RECIPE_PREFIX}{json.dumps(payload, ensure_ascii=False)}"


def parse_stored_recipe(raw):
    if not isinstance(raw, str) or not raw.startswith(RECIPE_PREFIX):
        raise ValueError("Recipe does not use the supported JSON format.")

    try:
        payload = json.loads(
            raw[len(RECIPE_PREFIX):], object_pairs_hook=_reject_duplicate_keys
        )
    except json.JSONDecodeError as exc:
        raise ValueError("Stored recipe is not valid JSON.") from exc

    recipe = validate_recipe_structure(payload)
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("Recipe metadata must be a JSON object.")
    return recipe, metadata
