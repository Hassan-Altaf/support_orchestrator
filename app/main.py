"""FastAPI app factory + lifespan + middleware + exception handlers.

`create_app(settings=None, *, provider=None)` is the test-friendly entry
point. Production deployments use the module-level `app` (created with
default settings). Tests can pass a custom `Settings` and/or an
already-configured `LLMProvider` (e.g. a MockProvider with a canned
response queue) to bypass the factory's default wiring.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import router as api_router
from app.api.schemas import ErrorResponse
from app.config import Settings, get_settings
from app.llm import get_llm_provider
from app.llm.provider import LLMProvider
from app.orchestration.graph import compile_graph
from app.utils.logging import (
    bind_request_id,
    clear_request_id,
    configure_logging,
    get_logger,
    get_request_id,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise structured logging, build the provider, compile the graph once."""
    settings: Settings = app.state.settings
    configure_logging(settings)
    log = get_logger("app.lifespan")

    provider: LLMProvider = getattr(app.state, "provider", None) or get_llm_provider(settings)
    app.state.provider = provider
    app.state.graph = compile_graph(provider, settings)

    log.info(
        "app_startup",
        llm_provider=settings.llm_provider,
        app_version=settings.app_version,
        max_retries=settings.max_retries,
    )
    try:
        yield
    finally:
        log.info("app_shutdown")


def create_app(
    settings: Settings | None = None,
    *,
    provider: LLMProvider | None = None,
) -> FastAPI:
    """Build a FastAPI instance.

    `provider` lets tests inject a MockProvider before the lifespan runs;
    otherwise the lifespan calls `get_llm_provider(settings)`.
    """
    settings = settings or get_settings()

    app = FastAPI(
        title="Support Orchestrator",
        description=(
            "AI-powered, multi-step support ticket orchestration "
            "(FastAPI + LangGraph). Each request flows through a "
            "classifier -> extractor -> (optional escalation) -> "
            "customer-response -> internal-summary graph."
        ),
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.state.settings = settings
    if provider is not None:
        app.state.provider = provider

    # CORS: per the W3C spec, `allow_origins=["*"]` combined with
    # `allow_credentials=True` is invalid — browsers silently reject it. We
    # only opt into credentials when a concrete origin allowlist is configured.
    wildcard_origin = "*" in settings.cors_origins
    if wildcard_origin and len(settings.cors_origins) > 1:
        get_logger("app.cors").warning(
            "cors_wildcard_with_explicit_origins",
            origins=settings.cors_origins,
            note="'*' overrides any explicit origins; collapsing to ['*'].",
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        # Credentials require a concrete origin allowlist per the CORS spec.
        # Tighten cors_origins to a real list (no '*') to re-enable cookies/auth.
        allow_credentials=not wildcard_origin,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Bind a uuid4 request_id to logging context and echo as X-Request-ID."""
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        bind_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            clear_request_id()
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        body = ErrorResponse(
            error="validation_error",
            detail=str(exc.errors()),
            request_id=get_request_id(),
        )
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        """Wrap intentional HTTPExceptions in the same ErrorResponse envelope."""
        body = ErrorResponse(
            error="http_error",
            detail=str(exc.detail),
            request_id=get_request_id(),
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Log the full exception server-side, return a safe envelope client-side.
        get_logger("app.exception").exception(
            "unhandled_exception",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        body = ErrorResponse(
            error="internal_server_error",
            detail="An unexpected error occurred. Reference X-Request-ID in support requests.",
            request_id=get_request_id(),
        )
        return JSONResponse(status_code=500, content=body.model_dump(mode="json"))

    app.include_router(api_router)
    return app


# Module-level instance for `uvicorn app.main:app`.
# When tests need a custom provider or settings, they import `create_app`
# directly and skip this global.
app = create_app()
