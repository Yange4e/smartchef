import logging
import os
import time

import httpx
from django.conf import settings
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
TRANSIENT_API_STATUSES = {500, 502, 503, 504}
API_RETRY_DELAY_SECONDS = 1


class AIAdapterError(Exception):
    def __init__(self, message, user_message=None, user_message_ru=None):
        super().__init__(message)
        self.user_message = user_message or (
            "AI провайдері сұрауды өңдей алмады."
        )
        self.user_message_ru = user_message_ru or (
            "Провайдер AI не смог обработать запрос."
        )


class AITimeoutError(AIAdapterError):
    pass


class AIConfigurationError(AIAdapterError):
    pass


def generate_text(prompt):
    load_dotenv(settings.BASE_DIR / ".env", override=False)
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key or api_key == "PASTE_YOUR_KEY_HERE":
        raise AIConfigurationError("A valid GEMINI_API_KEY is required.")

    model = (os.getenv("GEMINI_MODEL") or "gemini-2.5-flash").strip()

    try:
        from google import genai
        from google.genai import errors
    except ImportError as exc:
        logger.exception("Gemini SDK import failed")
        raise AIAdapterError(
            "The Gemini SDK is unavailable.",
            "Gemini кітапханасы орнатылмаған немесе импортталмады.",
            "Библиотека Gemini не установлена или не импортируется.",
        ) from exc

    try:
        client = genai.Client(
            api_key=api_key,
            http_options=genai.types.HttpOptions(timeout=30_000),
        )
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model, contents=prompt
                )
                break
            except errors.APIError as exc:
                status = getattr(exc, "code", None)
                if status not in TRANSIENT_API_STATUSES or attempt == 1:
                    raise
                logger.warning(
                    "Gemini API returned transient HTTP %s; retrying once",
                    status,
                )
                time.sleep(API_RETRY_DELAY_SECONDS)
    except httpx.TimeoutException as exc:
        logger.exception("Gemini API request timed out")
        raise AITimeoutError("The AI request timed out.") from exc
    except errors.APIError as exc:
        logger.exception("Gemini API returned an error")
        status = getattr(exc, "code", None)
        if status in (401, 403):
            user_message = (
                "Gemini API кілті жарамсыз немесе оның API-ға рұқсаты жоқ."
            )
            user_message_ru = (
                "Ключ Gemini API недействителен или у него нет доступа к API."
            )
        elif status == 404:
            user_message = (
                f"Gemini-де «{model}» моделі табылмады немесе қолжетімсіз."
            )
            user_message_ru = (
                f"Модель «{model}» не найдена или недоступна в Gemini."
            )
        elif status == 429:
            user_message = (
                "Gemini API сұрау лимитіне жетті немесе квота таусылды."
            )
            user_message_ru = (
                "Достигнут лимит запросов Gemini API или исчерпана квота."
            )
        elif status is not None and status >= 500:
            user_message = (
                "Gemini қызметінде уақытша сервер қатесі бар. Кейінірек қайталап көріңіз."
            )
            user_message_ru = (
                "В Gemini произошла временная ошибка сервера. Попробуйте позже."
            )
        elif status is not None:
            user_message = (
                f"Gemini сұрауды қабылдамады (HTTP {status}). Сұрау параметрлері мен API баптауын тексеріңіз."
            )
            user_message_ru = (
                f"Gemini отклонил запрос (HTTP {status}). Проверьте параметры запроса и настройки API."
            )
        else:
            user_message = (
                "Gemini API қатесі. Сервер журналындағы толық мәліметті тексеріңіз."
            )
            user_message_ru = (
                "Ошибка Gemini API. Подробности доступны в серверном журнале."
            )
        raise AIAdapterError(
            f"Gemini API error (HTTP {status}): {exc}",
            user_message,
            user_message_ru,
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("Gemini network request failed")
        raise AIAdapterError(
            f"Gemini network error ({type(exc).__name__}): {exc}",
            "Gemini API-ға желі арқылы қосыла алмады. Интернет пен желі параметрлерін тексеріңіз.",
            "Не удалось подключиться к Gemini API. Проверьте интернет и сетевые настройки.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected Gemini API request error")
        raise AIAdapterError(
            f"Unexpected Gemini error ({type(exc).__name__}): {exc}",
            "Gemini API күтпеген қате қайтарды. Толық мәлімет сервер журналында жазылды.",
            "Gemini API вернул непредвиденную ошибку. Подробности записаны в серверный журнал.",
        ) from exc

    try:
        text = getattr(response, "text", None)
    except ValueError as exc:
        logger.exception("Gemini returned an invalid response")
        raise AIAdapterError(
            "The AI provider returned an invalid response.",
            "Gemini жауабын оқу мүмкін болмады.",
            "Не удалось прочитать ответ Gemini.",
        ) from exc
    return text.strip() if isinstance(text, str) else ""