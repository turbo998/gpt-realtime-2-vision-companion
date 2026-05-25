"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.config import get_settings

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    logger.info("Starting app env=%s version=%s", settings.app_env, __version__)
    yield
    logger.info("Shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="gpt-realtime-2-vision-companion",
        version=__version__,
        description="Real-time voice + vision AI companion backend for blind & low-vision users.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "version": __version__})

    try:
        from app.ws_session import router as ws_router

        app.include_router(ws_router)
    except Exception as exc:  # pragma: no cover
        logger.warning("ws_session not registered yet: %s", exc)

    return app


app = create_app()
