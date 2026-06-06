from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Protocol

import requests

from backend.core.config import get_settings

logger = logging.getLogger("nexa.ai")


class AIProviderError(RuntimeError):
    pass


class AIProvider(Protocol):
    name: str

    def interpret(self, prompt: str) -> dict:
        ...


@dataclass
class GroqProvider:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int = 20
    name: str = "groq"

    def interpret(self, prompt: str) -> dict:
        response = requests.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are Nexa's task approval interpreter. Return only compact JSON with keys: "
                            "corrected_text, intent, task_type, date, time, trigger, action, priority, "
                            "conditions, confidence, execution_impact, high_risk, needs_clarification."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise AIProviderError(f"Groq request failed: {response.status_code} {response.text[:300]}")
        try:
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise AIProviderError("Groq returned an invalid interpretation payload") from exc


class ProviderFactory:
    @staticmethod
    def create() -> AIProvider | None:
        settings = get_settings()
        provider = settings.ai_provider.lower().strip()
        if provider == "groq" and settings.groq_api_key:
            return GroqProvider(settings.groq_api_key, settings.groq_base_url, settings.groq_model)
        logger.info("AI provider %s unavailable; using local task approval interpreter", provider)
        return None
