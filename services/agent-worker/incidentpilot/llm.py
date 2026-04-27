from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import logging
from typing import Any
from urllib import error, request

from .config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RootCauseDraft:
    root_cause: str
    confidence: float
    evidence_ids: list[str]
    limitations: list[str]
    provider: str


class LLMClient:
    provider = "disabled"

    @property
    def enabled(self) -> bool:
        return False

    async def generate_root_cause(self, messages: list[dict[str, str]], allowed_evidence_ids: set[str]) -> RootCauseDraft:
        raise NotImplementedError


class OpenAICompatibleClient(LLMClient):
    provider = "openai-compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_tokens: int,
        temperature: float,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.temperature = temperature

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def generate_root_cause(self, messages: list[dict[str, str]], allowed_evidence_ids: set[str]) -> RootCauseDraft:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }
        raw_content = await asyncio.to_thread(self._chat_completion, payload)
        parsed = parse_json_object(raw_content)
        return normalize_root_cause_draft(parsed, allowed_evidence_ids, self.provider)

    def _chat_completion(self, payload: dict[str, Any]) -> str:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"llm provider returned {exc.code}: {detail[:300]}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"llm provider unreachable: {exc.reason}") from exc

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("llm provider returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("llm provider returned empty content")
        return content


def build_llm_client(settings: Settings) -> LLMClient | None:
    if settings.llm_provider in {"", "disabled", "none"}:
        return None
    if settings.llm_provider in {"openai", "openai-compatible", "deepseek", "ollama", "hunyuan"}:
        if not settings.llm_api_key:
            logger.info("LLM provider %s configured without LLM_API_KEY; deterministic RCA fallback is active", settings.llm_provider)
            return None
        return OpenAICompatibleClient(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
        )
    logger.warning("unknown LLM_PROVIDER=%s; deterministic RCA fallback is active", settings.llm_provider)
    return None


def parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("llm response did not contain a JSON object")
    return json.loads(text[start : end + 1])


def normalize_root_cause_draft(payload: dict[str, Any], allowed_evidence_ids: set[str], provider: str) -> RootCauseDraft:
    root_cause = str(payload.get("root_cause", "")).strip()
    if len(root_cause) < 20:
        raise ValueError("llm root_cause is too short")

    confidence = float(payload.get("confidence", 0))
    confidence = min(0.95, max(0.05, confidence))

    raw_evidence_ids = payload.get("evidence_ids", [])
    if not isinstance(raw_evidence_ids, list):
        raw_evidence_ids = []
    evidence_ids = [str(value) for value in raw_evidence_ids if str(value) in allowed_evidence_ids]
    if len(evidence_ids) < 2:
        raise ValueError("llm response did not cite at least two supplied evidence IDs")

    raw_limitations = payload.get("limitations", [])
    if not isinstance(raw_limitations, list):
        raw_limitations = [str(raw_limitations)]
    limitations = [str(item).strip() for item in raw_limitations if str(item).strip()]
    if not limitations:
        limitations = ["LLM analysis is bounded to supplied synthetic evidence."]

    return RootCauseDraft(
        root_cause=root_cause,
        confidence=confidence,
        evidence_ids=evidence_ids,
        limitations=limitations[:5],
        provider=provider,
    )
