from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.core.redis import close_redis, get_redis


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle context: startup and shutdown logic."""
    setup_logging(debug=settings.DEBUG)
    logger.info("app_starting", app_name=settings.APP_NAME, env=settings.APP_ENV)

    # Initialize Redis connection pool
    try:
        redis = get_redis()
        await redis.ping()
        logger.info("redis_connected", url=settings.REDIS_URL)
    except Exception as exc:
        logger.warning("redis_connection_warning", error=str(exc))

    yield

    # Clean shutdown
    logger.info("app_stopping")
    await close_redis()


app = FastAPI(
    title=settings.APP_NAME,
    description="Production-Grade Distributed Financial Ledger & Asynchronous Event Ingestion API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Uniform structured response for Pydantic schema validation failures."""
    logger.warning("request_validation_failed", path=request.url.path, errors=exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request body or parameters failed validation.",
                "details": jsonable_encoder(exc.errors()),
            }
        },
    )


# Include health endpoints at top-level
app.include_router(health_router)

# Include v1 endpoints
app.include_router(api_v1_router)
