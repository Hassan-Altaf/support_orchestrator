"""Google Gemini structured-output provider.

Why Gemini: the free tier on `gemini-2.0-flash` (1,500 requests/day on the AI
Studio API at the time of writing) makes this the cheapest way to run the
orchestrator end-to-end against a real LLM — useful for assessments and
local development without burning OpenAI/Anthropic credits.

Implementation: uses the official `google-genai` SDK with Gemini's native
structured-output path. The Pydantic JSON schema is cleaned before being
sent because Gemini's `response_schema` API accepts only a subset of OpenAPI:
it does NOT support `$ref` / `$defs` (so we inline them) and rejects
`additionalProperties` (which Pydantic emits whenever a model declares
`extra="forbid"`). Pydantic still validates on our side, so a shape
deviation raises `ValidationError` and feeds the retry-with-feedback loop
the same way OpenAI/Anthropic do.
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from app.config import Settings

T = TypeVar("T", bound=BaseModel)

# JSON-Schema keys Gemini's response_schema parser rejects or doesn't understand.
# camelCase entries cover what Pydantic emits; snake_case covers what the
# google-genai SDK converts to before sending.
_UNSUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "additionalProperties",
        "additional_properties",
        "$schema",
        "$id",
        "$comment",
        "definitions",
        "discriminator",
        "patternProperties",
        "pattern_properties",
        # `title` is accepted but redundant noise — strip to keep the schema lean.
        "title",
    }
)


def _resolve_refs(schema: Any, defs: dict[str, Any] | None = None) -> Any:
    """Recursively inline `$ref` pointers and drop the `$defs` block.

    Gemini's response_schema does not support JSON-Schema reference resolution,
    so the schema must be fully self-contained.
    """
    if isinstance(schema, dict):
        if defs is None:
            defs = schema.get("$defs", {})

        if "$ref" in schema:
            ref = schema["$ref"]
            # Expected shape: "#/$defs/<name>"
            name = ref.rsplit("/", 1)[-1]
            target = defs.get(name) if defs else None
            if target is None:
                return {}
            return _resolve_refs(target, defs)

        return {k: _resolve_refs(v, defs) for k, v in schema.items() if k != "$defs"}

    if isinstance(schema, list):
        return [_resolve_refs(item, defs) for item in schema]

    return schema


def _strip_unsupported(schema: Any) -> Any:
    """Remove JSON-Schema keys Gemini's response_schema parser rejects."""
    if isinstance(schema, dict):
        return {
            k: _strip_unsupported(v) for k, v in schema.items() if k not in _UNSUPPORTED_SCHEMA_KEYS
        }
    if isinstance(schema, list):
        return [_strip_unsupported(x) for x in schema]
    return schema


def _pydantic_to_gemini_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic model into a Gemini-compatible response_schema dict."""
    raw = model.model_json_schema()
    inlined = _resolve_refs(raw)
    cleaned = _strip_unsupported(inlined)
    assert isinstance(cleaned, dict)
    return cleaned


class GeminiProviderError(RuntimeError):
    """Raised for transport/auth/empty-response failures (NOT for ValidationError)."""


class GeminiProvider:
    """`google-genai`-backed implementation of LLMProvider."""

    def __init__(self, settings: Settings) -> None:
        if settings.gemini_api_key is None:
            raise RuntimeError(
                "GeminiProvider requires GEMINI_API_KEY. "
                "Get a free key at https://aistudio.google.com/ or use LLM_PROVIDER=mock."
            )
        # Imported lazily so the rest of the package doesn't pay the SDK import
        # cost when Gemini isn't selected.
        from google import genai

        self._client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
        self._model = settings.gemini_model

    async def complete_structured(
        self,
        system: str,
        user: str,
        response_model: type[T],
        temperature: float = 0.0,
    ) -> T:
        from google.genai import errors as genai_errors
        from google.genai import types

        gemini_schema = _pydantic_to_gemini_schema(response_model)
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=gemini_schema,
        )

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=user,
                config=config,
            )
        except genai_errors.APIError as e:
            raise GeminiProviderError(
                f"Gemini API call failed for {response_model.__name__}: {e}"
            ) from e

        # `response.text` is the JSON string the SDK extracted. We re-validate
        # with Pydantic so a deviating shape raises ValidationError -> retry
        # with feedback, matching the OpenAI/Anthropic providers exactly.
        raw = response.text
        if not raw:
            raise GeminiProviderError(
                f"Gemini returned an empty response for {response_model.__name__}; "
                f"prompt_feedback={getattr(response, 'prompt_feedback', None)}"
            )
        return response_model.model_validate_json(raw)
