"""LLM client protocol and multi-provider implementations for the pipeline.

Inspired by:
- ats-web apps/pipeline/llm.py (OpenAI with strict json_schema)
- matrix-pdf-summarizer-bot llm_factory.py (multi-provider pattern)
"""

from __future__ import annotations

import copy
from typing import Any, Protocol, runtime_checkable

from django.conf import settings


@runtime_checkable
class LlmClient(Protocol):
    """Protocol for LLM chat completion."""

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return completion text for the supplied prompts."""
        ...


# ── Test-friendly clients ──────────────────────────────────────────────────


class StaticLlmClient:
    """Test-friendly client returning a fixed response."""

    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        return self._response_text


class RecordingLlmClient:
    """Test client that records calls and returns configured responses."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = iter(responses or [])
        self.calls: list[dict[str, str]] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return next(self._responses, "")


# ── Factory functions ──────────────────────────────────────────────────────


def create_openai_client(
    *,
    response_schema_name: str | None = None,
    response_schema: dict[str, object] | None = None,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> LlmClient:
    """Create OpenAI chat completions client with optional strict json_schema.

    When response_schema_name and response_schema are provided,
    uses strict json_schema mode. Otherwise falls back to json_object mode.
    """
    if (response_schema_name is None) != (response_schema is None):
        raise ValueError("response_schema_name and response_schema must be provided together")

    from openai import OpenAI

    _api_key = api_key or settings.OPENAI_API_KEY
    _model = model or settings.OPENAI_MODEL
    _base_url = base_url or getattr(settings, "OPENAI_BASE_URL", "https://api.openai.com/v1")

    client = OpenAI(api_key=_api_key, base_url=_base_url)

    # Pre-normalize schema for strict mode
    normalized_schema: dict[str, object] | None = None
    if response_schema_name is not None and response_schema is not None:
        normalized_schema = _normalize_openai_strict_schema(response_schema)

    class OpenAiLlmClient:
        def __init__(
            self,
            openai_client: OpenAI,
            model_name: str,
            schema_name: str | None,
            schema: dict[str, object] | None,
        ) -> None:
            self._client = openai_client
            self._model = model_name
            self._schema_name = schema_name
            self._schema = schema

        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            if self._schema_name is None or self._schema is None:
                response_format: Any = {"type": "json_object"}
            else:
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": self._schema_name,
                        "schema": self._schema,
                        "strict": True,
                    },
                }
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=response_format,
            )
            content: str | None = response.choices[0].message.content
            if content is None:
                raise RuntimeError("OpenAI returned empty content")
            return content

    return OpenAiLlmClient(client, _model, response_schema_name, normalized_schema)


def create_anthropic_client(
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> LlmClient:
    """Create Anthropic (Claude) chat completions client.

    Note: Anthropic API uses a different call format (system parameter,
    not system message). This adapter translates the common interface.
    """
    from anthropic import Anthropic

    _api_key = api_key or getattr(settings, "ANTHROPIC_API_KEY", "")
    _model: str = str(model or getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-20250514"))
    _base_url = base_url or getattr(settings, "ANTHROPIC_BASE_URL", "https://api.anthropic.com")

    client = Anthropic(api_key=_api_key, base_url=_base_url)

    class AnthropicLlmClient:
        def __init__(self, client: Anthropic, model_name: str) -> None:
            self._client = client
            self._model = model_name

        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            content = response.content[0].text
            if content is None:
                raise RuntimeError("Anthropic returned empty content")
            return str(content).strip()

    return AnthropicLlmClient(client, _model)


def create_generic_openai_compatible_client(
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> LlmClient:
    """Create generic OpenAI-compatible client (Ollama, Groq, etc.).

    Uses the OpenAI SDK against a custom base_url.
    """
    from openai import OpenAI

    _api_key = api_key or getattr(settings, "OPENAI_API_KEY", "not-required")
    _model = model or settings.OPENAI_MODEL
    _base_url = base_url or getattr(settings, "OPENAI_BASE_URL", "http://localhost:11434/v1")

    client = OpenAI(api_key=_api_key, base_url=_base_url)

    class GenericOpenAiCompatibleClient:
        def __init__(self, client: OpenAI, model_name: str) -> None:
            self._client = client
            self._model = model_name

        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            content: str | None = response.choices[0].message.content
            if content is None:
                raise RuntimeError("Generic client returned empty content")
            return content

    return GenericOpenAiCompatibleClient(client, _model)


def create_openai_llm1_client() -> LlmClient:
    """Create OpenAI client for LLM1 with strict Llm1VascularResponse schema."""
    from apps.pipeline.schemas.llm1 import Llm1VascularResponse

    return create_openai_client(
        response_schema_name="llm1_vascular_response",
        response_schema=Llm1VascularResponse.model_json_schema(),
    )


def create_openai_llm2_client() -> LlmClient:
    """Create OpenAI client for LLM2 with strict Llm2VascularResponse schema."""
    from apps.pipeline.schemas.llm2 import Llm2VascularResponse

    return create_openai_client(
        response_schema_name="llm2_vascular_response",
        response_schema=Llm2VascularResponse.model_json_schema(),
    )


def create_llm_client_from_settings(*, prefix: str) -> LlmClient:
    """Factory: create LLM client from Django settings with a given prefix.

    Reads:
        <PREFIX>_PROVIDER (openai, anthropic, generic)
        <PREFIX>_MODEL
        <PREFIX>_API_KEY
        <PREFIX>_BASE_URL

    Example:
        create_llm_client_from_settings(prefix="LLM1_PRIMARY")
        → reads LLM1_PRIMARY_PROVIDER, LLM1_PRIMARY_MODEL, ...
    """
    provider = getattr(settings, f"{prefix}_PROVIDER", "openai")
    model = getattr(settings, f"{prefix}_MODEL", None)
    api_key = getattr(settings, f"{prefix}_API_KEY", None)
    base_url = getattr(settings, f"{prefix}_BASE_URL", None)

    if provider == "openai":
        return create_openai_client(api_key=api_key, model=model, base_url=base_url)
    elif provider == "anthropic":
        return create_anthropic_client(api_key=api_key, model=model, base_url=base_url)
    elif provider == "generic":
        return create_generic_openai_compatible_client(api_key=api_key, model=model, base_url=base_url)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


# ── Schema normalization for OpenAI strict mode ─────────────────────────────


def _normalize_openai_strict_schema(schema: dict[str, object]) -> dict[str, object]:
    """Normalize JSON Schema so OpenAI strict mode accepts all object nodes.

    OpenAI strict mode requires every object node to have:
    - ``additionalProperties: false``
    - ``required`` listing all property names
    """
    normalized = copy.deepcopy(schema)
    _normalize_schema_node(normalized)
    return normalized


def _normalize_schema_node(node: object) -> None:
    if isinstance(node, dict):
        node_type = node.get("type")
        properties = node.get("properties")
        if node_type == "object" and isinstance(properties, dict):
            property_names = [str(name) for name in properties.keys()]
            node["required"] = property_names
            node.setdefault("additionalProperties", False)

        for value in node.values():
            _normalize_schema_node(value)
        return

    if isinstance(node, list):
        for value in node:
            _normalize_schema_node(value)
