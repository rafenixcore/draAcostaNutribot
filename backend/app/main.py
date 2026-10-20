import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

import app.models  # noqa: F401 — registers all ORM models on Base.metadata
from app.api.router import api_router
from app.core.circuit_breaker import CircuitBreakerMiddleware
from app.core.config import settings
from app.core.database import Base, engine
from app.core.limiter import limiter
from app.core.logging_config import setup_logging

setup_logging(settings.is_production)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_cors = settings.CORS_ORIGINS.strip()
_allow_origins = ["*"] if _cors == "*" else [o.strip() for o in _cors.split(",") if o.strip()]
_allow_credentials = _allow_origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SlowAPIMiddleware)

# Circuit breaker — trips on sustained 5xx errors
app.add_middleware(CircuitBreakerMiddleware)

# Sirve logo-doctora.jpeg y otros assets para que los emails los muestren
_public_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "public"
if _public_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_public_dir)), name="static")
    logger.info("Static files served from %s", _public_dir)


@app.on_event("startup")
async def create_tables() -> None:
    """Create missing tables only in local development.

    Deployed environments run Alembic before Uvicorn starts; running create_all
    afterwards can race or conflict with versioned migrations.
    """
    if settings.is_production:
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.on_event("startup")
async def start_scheduler():
    if settings.REMINDER_ENABLED:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler

            from app.core.database import async_session_factory
            from app.services.reminder_service import check_and_send_reminders

            scheduler = AsyncIOScheduler()

            async def job():
                try:
                    async with async_session_factory() as db:
                        sent = await check_and_send_reminders(db)
                        if sent:
                            logger.info("Enviados %d recordatorios automáticos", sent)
                        else:
                            logger.debug("Sin recordatorios pendientes")
                except Exception:
                    logger.exception("Error en reminder job")

            # Ejecutar inmediatamente al iniciar
            await job()
            # Y repetir cada N minutos
            scheduler.add_job(
                job,
                "interval",
                minutes=settings.REMINDER_INTERVAL_MINUTES,
                id="diet_reminders",
                replace_existing=True,
            )
            scheduler.start()
            logger.info(
                "Reminder scheduler iniciado (cada %d min, umbral %d días)",
                settings.REMINDER_INTERVAL_MINUTES,
                settings.REMINDER_DAYS,
            )
        except Exception:
            logger.exception("No se pudo iniciar el reminder scheduler")


@app.get("/")
async def root():
    return {"status": "ok", "service": "diet-telegram-agent"}


app.include_router(api_router, prefix="/api")
