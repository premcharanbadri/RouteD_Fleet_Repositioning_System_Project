"""FastAPI application factory: wires the layers together and boots demo data."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.api import analytics, routes, simulation
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty

settings = get_settings()


class BodySizeLimit(BaseHTTPMiddleware):
    # Reject oversized request bodies before they reach a handler.
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        length = request.headers.get("content-length")
        if length is not None and int(length) > settings.max_request_bytes:
            return JSONResponse({"detail": "Request body too large"}, status_code=413)
        return await call_next(request)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_if_empty(db)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="RouteIQ",
        description="AI-assisted demand forecasting, fleet repositioning & dispatch",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(BodySizeLimit)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(routes.router)
    app.include_router(analytics.router)
    app.include_router(simulation.router)
    return app


app = create_app()
