"""Model wrappers adding caching and rate limiting to any PydanticAI model.

These replace the old client decorator classes. Wrapping at the model layer
means they apply to every provider, and to tool calls and retries as well as to
the first request of a run.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, cast

from pydantic import TypeAdapter
from pydantic_ai.messages import (
    ModelResponse,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.wrapper import WrapperModel

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pydantic_ai import RunContext
    from pydantic_ai.messages import (
        ModelMessage,
        ModelRequestPart,
        ModelResponsePart,
    )
    from pydantic_ai.models import (
        KnownModelName,
        Model,
        ModelRequestParameters,
        StreamedResponse,
    )
    from pydantic_ai.settings import ModelSettings

    from .cache import ResponseCache
    from .rate_limiter import RateLimiter

# `WrapperModel` is annotated with the `KnownModelName` literal union but
# resolves any string at runtime, so plain model names the literal has not
# caught up with (a self-hosted endpoint, say) are cast through.
_RESPONSE_ADAPTER: TypeAdapter[ModelResponse] = TypeAdapter(ModelResponse)


def _describe_part(part: ModelRequestPart | ModelResponsePart) -> tuple[str, ...]:
    """Reduce one message part to the content that decides the answer.

    Parts are projected by their own `part_kind` discriminator rather than by
    stripping fields whose names look volatile. A name-based denylist has two
    faults: it reaches into `args` and `metadata` and erases anything that
    happens to share a name, and it silently lets new per-run fields into the
    key. Both showed up here — `usage` and `provider_response_id` on every
    `ModelResponse` meant no multi-turn request ever hit the cache, and this
    library's runs are always multi-turn because tools and retries add turns.
    """
    kind = part.part_kind
    if isinstance(part, ToolCallPart):
        return (kind, part.tool_name, part.args_as_json_str())
    if isinstance(part, ToolReturnPart):
        return (kind, part.tool_name, str(part.content))
    if isinstance(part, RetryPromptPart):
        return (kind, str(part.content))
    content = getattr(part, "content", None)
    return (kind, "" if content is None else str(content))


def describe_messages(messages: list[ModelMessage]) -> str:
    """Render a message history as a value that is stable across runs."""
    return json.dumps(
        [
            [message.kind, *(_describe_part(part) for part in message.parts)]
            for message in messages
        ]
    )


def describe_request_parameters(parameters: ModelRequestParameters) -> str:
    """Render the parts of a request's parameters that change the response.

    Tool schemas are included, not just names: two agents whose tools share a
    name but differ in signature must not share a cache entry.
    """
    return json.dumps(
        {
            "tools": sorted(
                (tool.name, json.dumps(tool.parameters_json_schema, sort_keys=True))
                for tool in parameters.function_tools
            ),
            "outputs": sorted(
                (tool.name, json.dumps(tool.parameters_json_schema, sort_keys=True))
                for tool in parameters.output_tools
            ),
            "output_mode": str(parameters.output_mode),
            "allow_text_output": parameters.allow_text_output,
        },
        sort_keys=True,
    )


class CachedModel(WrapperModel):
    """Serve repeated identical requests from an on-disk cache."""

    def __init__(self, wrapped: Model | str, cache: ResponseCache) -> None:
        """Wrap `wrapped`, storing and reusing responses in `cache`."""
        super().__init__(cast("Model | KnownModelName", wrapped))
        self.cache = cache

    def cache_key(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> str:
        """Derive a cache key covering everything that changes the response.

        The provider, the model name, the settings, the whole message history,
        and the request parameters all take part. Leaving any of them out lets
        one request serve another's answer, which is how the previous cache
        could return an empty plan for a prompt that had only ever been chatted.
        """
        return self.cache.build_key(
            self.system,
            self.model_name,
            json.dumps(sorted((model_settings or {}).items()), default=str),
            describe_messages(messages),
            describe_request_parameters(model_request_parameters),
        )

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """Return a cached response when one exists, otherwise call the model."""
        key = self.cache_key(messages, model_settings, model_request_parameters)

        cached = self.cache.get(key)
        if cached is not None:
            response = _RESPONSE_ADAPTER.validate_json(cached)
            response.provider_details = {
                **(response.provider_details or {}),
                "from_cache": True,
            }
            return response

        response = await super().request(
            messages,
            model_settings,
            model_request_parameters,
        )
        self.cache.set(key, _RESPONSE_ADAPTER.dump_json(response))
        return response


class RateLimitedModel(WrapperModel):
    """Hold requests back so they stay within a token-bucket budget.

    Streaming is limited too. `WrapperModel.request_stream` delegates straight
    through, so without the override a streaming caller would spend nothing
    from the budget the limiter exists to enforce.
    """

    def __init__(self, wrapped: Model | str, rate_limiter: RateLimiter) -> None:
        """Wrap `wrapped`, admitting requests through `rate_limiter`."""
        super().__init__(cast("Model | KnownModelName", wrapped))
        self.rate_limiter = rate_limiter

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """Wait for capacity, then call the wrapped model."""
        await self.rate_limiter.aacquire()
        return await super().request(
            messages,
            model_settings,
            model_request_parameters,
        )

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
        run_context: RunContext[Any] | None = None,
    ) -> AsyncGenerator[StreamedResponse]:
        """Wait for capacity, then stream from the wrapped model."""
        await self.rate_limiter.aacquire()
        async with super().request_stream(
            messages,
            model_settings,
            model_request_parameters,
            run_context,
        ) as stream:
            yield stream
