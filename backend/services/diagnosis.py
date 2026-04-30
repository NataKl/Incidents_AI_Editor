from __future__ import annotations

import json
import re
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from core.config import settings


class OpenAIDiagnosisFailed(Exception):
    """OpenAI вызван по ключу из настроек; эвристика отключена."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


Confidence = Literal["high", "medium", "low"]


class DiagnosisPayload(BaseModel):
    root_cause_hypothesis: str
    confidence: Confidence
    next_steps: list[str] = Field(min_length=1)
    needs_review: bool


def _openai_http_proxy() -> str | None:
    """URL прокси для исходящих HTTPS-запросов к OpenAI (из .env)."""
    for raw in (settings.https_proxy, settings.http_proxy):
        u = (raw or "").strip()
        if u:
            return u
    return None


def _openai_temperature_unsupported_explicit(model_name: str) -> bool:
    """Некоторые модели принимают только температуру по умолчанию — поле нельзя задавать (иначе 400)."""
    m = model_name.strip().lower()
    if m.startswith("gpt-5"):
        return True
    if len(m) >= 2 and m[0] == "o" and m[1].isdigit():
        return True
    return False


_VAGUE_PAT = re.compile(
    r"^(запуск|старт|проверка|ok|ок|health|ping|тест)\b",
    re.IGNORECASE,
)


def _heuristic_diagnosis(title: str, messages: list[str]) -> tuple[DiagnosisPayload, str]:
    joined = " ".join(messages).strip()
    short = len(joined) < 80
    vague = all(len(m.strip()) < 40 for m in messages) or any(_VAGUE_PAT.search(m or "") for m in messages)

    if short or vague or len(messages) < 2:
        payload = DiagnosisPayload(
            root_cause_hypothesis=(
                "По коротким или слишком общим сообщениям нельзя выделить конкретную причину сбоя."
            ),
            confidence="low",
            needs_review=True,
            next_steps=[
                "Собрать уточнения: точное время, затронутые сервисы, корреляционные ID, трассировки.",
                "Добавить логи уровня error со стеком и идентификатором запроса.",
                "Проверить метрики latency и error rate по сервису за интервал инцидента.",
            ],
        )
        return payload, json.dumps(payload.model_dump(), ensure_ascii=False)

    # Достаточно «технических» сигналов — условно средняя уверенность
    lowered = joined.lower()
    if "timeout" in lowered or "db locked" in lowered or "valueerror" in lowered:
        payload = DiagnosisPayload(
            root_cause_hypothesis=(
                "Вероятна инфраструктурная или прикладная ошибка (таймаут, БД, парсинг) по текстам событий."
            ),
            confidence="medium",
            needs_review=False,
            next_steps=[
                "Сопоставить время событий с деплоями и нагрузкой.",
                "Проверить пулы соединений к БД и лимиты внешних API.",
                "Воспроизвести на стенде с тем же входом данных.",
            ],
        )
    else:
        payload = DiagnosisPayload(
            root_cause_hypothesis="По имеющимся сообщениям возможны несколько сценариев; нужна дополнительная телеметрия.",
            confidence="medium",
            needs_review=True,
            next_steps=[
                "Собрать уточнения: полные логи вокруг времени инцидента.",
                "Добавить метрики golden signals (latency, traffic, errors, saturation).",
            ],
        )
    return payload, json.dumps(payload.model_dump(), ensure_ascii=False)


async def _openai_diagnose(title: str, messages: list[str]) -> tuple[DiagnosisPayload | None, str, str | None]:
    """Returns (parsed or None, raw_text, error_code)."""
    schema_hint = json.dumps(
        {
            "root_cause_hypothesis": "string",
            "confidence": "high|medium|low",
            "next_steps": ["string"],
            "needs_review": True,
        },
        ensure_ascii=False,
    )
    user_content = (
        f"Заголовок инцидента: {title}\n"
        f"Сообщения событий:\n"
        + "\n".join(f"- {m}" for m in messages)
        + "\n\nВерни ТОЛЬКО один JSON-объект без markdown по схеме:\n"
        + schema_hint
        + "\nЕсли данных мало (мало сообщений, противоречивый контекст) или есть явные ошибки/деградация — "
        "confidence=low, needs_review=true, "
        "а первый пункт next_steps должен начинаться с «Собрать уточнения».\n"
        "Если все события только про успешные проверки/штатную работу (info без ошибок и предупреждений о сбоях) и "
        "в текстах нет признаков инцидента — допустимо confidence=high и needs_review=false: кратко опиши вывод, "
        "что по логам сбоев не видно, режим штатный."
    )
    key = settings.openai_api_key.strip()
    headers = {"Authorization": f"Bearer {key}"}
    body: dict[str, Any] = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": "Ты инженер SRE. Отвечай только валидным JSON. "
             "Не считай случаем «мало данных», если единственное событие явно подтверждает успешный health-check без сбоев."},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
    }
    if not _openai_temperature_unsupported_explicit(settings.openai_model):
        body["temperature"] = settings.openai_temperature
    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    proxy = _openai_http_proxy()
    client_kw: dict[str, Any] = {"timeout": 60.0}
    if proxy:
        client_kw["proxy"] = proxy
    async with httpx.AsyncClient(**client_kw) as client:
        r = await client.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    raw_text = data["choices"][0]["message"]["content"]
    try:
        obj = json.loads(raw_text)
        parsed = DiagnosisPayload.model_validate(obj)
        return parsed, raw_text, None
    except (json.JSONDecodeError, ValidationError, KeyError):
        return None, raw_text, "INVALID_JSON"


async def run_diagnosis(title: str, messages: list[str]) -> tuple[DiagnosisPayload, str, str | None]:
    """
    Возвращает (payload для API, текст для колонки diagnosis_json в БД, error).
    При INVALID_JSON в БД пишется сырой ответ модели (как текст), API всё равно получает валидный JSON.

    Если задан OPENAI_API_KEY — диагностика только через модель (эвристика не используется).
    Без ключа используется эвристика.
    """
    if settings.openai_api_key.strip():
        try:
            parsed, raw_text, err = await _openai_diagnose(title, messages)
            if parsed is not None:
                data = parsed.model_dump()
                if data["confidence"] == "low":
                    data["needs_review"] = True
                fixed = DiagnosisPayload.model_validate(data)
                return fixed, json.dumps(fixed.model_dump(), ensure_ascii=False), None
            review_payload = DiagnosisPayload(
                root_cause_hypothesis="Ответ модели не удалось разобрать как строгий JSON.",
                confidence="low",
                needs_review=True,
                next_steps=[
                    "Собрать уточнения: повторить диагностику после исправления формата ответа ИИ.",
                    "Проверить логи backend и ключ API.",
                ],
            )
            return review_payload, raw_text, err
        except httpx.HTTPStatusError as e:
            snippet = (e.response.text or "")[:500]
            raise OpenAIDiagnosisFailed(
                f"OpenAI HTTP {e.response.status_code}: {snippet}"
            ) from e
        except Exception as e:
            raise OpenAIDiagnosisFailed(str(e)) from e

    payload, text = _heuristic_diagnosis(title, messages)
    return payload, text, None
