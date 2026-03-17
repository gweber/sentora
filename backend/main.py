"""FastAPI application factory.

Creates and configures the FastAPI app with:
- Lifespan events (DB connect/disconnect)
- Global exception handlers
- Request logging middleware
- All domain routers mounted under /api/v1
- Static file serving for the built Vue frontend (catch-all SPA route)
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from audit.chain.router import router as audit_chain_router
from audit.router import router as audit_router
from config import get_settings
from database import DatabaseUnavailableError, close_db, connect_db
from domains.admin.router import router as admin_router
from domains.admin.router import ws_router as admin_ws_router

# Domain routers
from domains.agents.apps_router import router as apps_router
from domains.agents.groups_router import router as groups_router
from domains.agents.router import router as agents_router
from domains.agents.sites_router import router as sites_router
from domains.api_keys.router import router as api_keys_router
from domains.auth.router import router as auth_router
from domains.classification.router import router as classification_router
from domains.compliance.router import router as compliance_router
from domains.config.router import branding_router
from domains.config.router import router as config_router
from domains.dashboard.router import router as dashboard_router
from domains.demo.router import router as demo_router
from domains.enforcement.router import router as enforcement_router
from domains.eol.router import router as eol_router
from domains.export.router import router as export_router
from domains.fingerprint.router import fingerprint_router, suggestions_router
from domains.library.router import router as library_router
from domains.sources.collections import INSTALLED_APPS, SYNC_CHECKPOINT, SYNC_META, SYNC_RUNS
from domains.sync.router import router as sync_router
from domains.tags.router import router as tags_router
from domains.taxonomy.router import router as taxonomy_router
from domains.tenant.router import router as tenant_router
from domains.webhooks.router import router as webhooks_router
from errors import SentoraError
from middleware.error_handler import (
    database_unavailable_handler,
    sentora_error_handler,
    unhandled_exception_handler,
)
from middleware.metrics import MetricsMiddleware
from middleware.rate_limit import RateLimitMiddleware
from middleware.request_logging import RequestLoggingMiddleware

# Frontend dist directory — built by `npm run build` and copied/mounted here
_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

# Maximum request body size (10 MB)
_MAX_BODY_SIZE = 10 * 1024 * 1024


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to every HTTP response."""

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # HSTS only in production (assumes TLS termination at reverse proxy)
        if not get_settings().is_development:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; connect-src 'self' wss: ws:; font-src 'self'"
            )
        return response


class BodySizeLimitMiddleware:
    """Reject requests whose body exceeds a configured maximum.

    Checks the Content-Length header when present and also wraps the ASGI
    receive channel to enforce the limit on chunked/streaming uploads that
    omit Content-Length.
    """

    def __init__(self, app: ASGIApp, *, max_size: int = _MAX_BODY_SIZE) -> None:
        self.app = app
        self.max_size = max_size

    async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Fast-path: check Content-Length header if present
        headers = dict(scope.get("headers", []))
        cl_header = headers.get(b"content-length")
        if cl_header is not None:
            try:
                cl = int(cl_header)
            except ValueError:
                response = JSONResponse(
                    {"detail": "Invalid Content-Length header"},
                    status_code=400,
                )
                await response(scope, receive, send)
                return
            if cl > self.max_size:
                response = JSONResponse(
                    {"detail": "Request body too large"},
                    status_code=413,
                )
                await response(scope, receive, send)
                return

        # Wrap receive to enforce limit on streamed/chunked bodies
        body_size = 0
        max_size = self.max_size
        exceeded = False

        async def receive_wrapper():  # noqa: ANN202
            nonlocal body_size, exceeded
            message = await receive()
            if message.get("type") == "http.request":
                body_size += len(message.get("body", b""))
                if body_size > max_size:
                    exceeded = True
                    raise ValueError("Request body too large")
            return message

        try:
            await self.app(scope, receive_wrapper, send)
        except ValueError:
            if exceeded:
                response = JSONResponse(
                    {"detail": "Request body too large"},
                    status_code=413,
                )
                await response(scope, receive, send)
            else:
                raise


def _configure_logging(level: str) -> None:
    """Configure loguru with JSON-structured output.

    Removes the default loguru sink and replaces it with a JSON-formatted
    sink to stdout suitable for log aggregators.

    Args:
        level: Logging level name (e.g. "INFO", "DEBUG").
    """
    logger.remove()
    logger.add(
        sys.stdout,
        level=level,
        serialize=True,
        colorize=False,
    )


async def _phase_scheduler(phase_name: str) -> None:
    """Background task that independently schedules a single sync phase.

    Reads the per-phase interval from config (``schedule_{phase}_minutes``).
    Falls back to the global ``refresh_interval_minutes`` when the per-phase
    value is 0.  Setting both to 0 disables scheduling for this phase.

    On startup, resumes any existing checkpoint for this phase before entering
    the normal schedule loop.
    """
    from database import get_db
    from domains.config import repository as config_repo
    from domains.sync.manager import sync_manager
    from utils.dt import utc_now
    from utils.leader_election import LeaderElection

    await asyncio.sleep(30)

    leader = LeaderElection(get_db(), f"sync_sched_{phase_name}", ttl_seconds=90)
    runner = sync_manager.get_runner(phase_name)
    if not runner:
        logger.error("Phase scheduler — unknown phase: {}", phase_name)
        return

    logger.info("Phase scheduler [{}] started", phase_name)
    first_cycle = True

    def _get_interval(cfg: Any) -> int:  # noqa: ANN401
        per_phase = getattr(cfg, f"schedule_{phase_name}_minutes", 0)
        return per_phase if per_phase > 0 else cfg.refresh_interval_minutes  # type: ignore[union-attr]

    try:
        while True:
            if not await leader.try_become_leader():
                await asyncio.sleep(15)
                continue

            try:
                cfg = await config_repo.get(get_db())
                interval = _get_interval(cfg)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Phase scheduler [{}] — config read failed: {}", phase_name, exc)
                await asyncio.sleep(60)
                continue

            if interval <= 0:
                first_cycle = False
                await asyncio.sleep(60)
                continue

            if first_cycle:
                first_cycle = False
                # Resume checkpoint if one exists
                cp = await runner.load_checkpoint()
                if cp and cp.get("status") != "completed":
                    logger.info("Phase scheduler [{}] — resuming from checkpoint", phase_name)
                    if not runner.is_running:
                        result = await runner.resume()
                        if result is None:
                            await asyncio.sleep(30)
                    continue

                # Check when this phase last ran — skip if not overdue
                try:
                    meta = await get_db()[SYNC_META].find_one({"_id": "global"})
                    last_synced_at = meta.get(f"{phase_name}_synced_at") if meta else None
                except Exception:
                    last_synced_at = None

                if last_synced_at:
                    from datetime import datetime

                    last_dt = datetime.fromisoformat(last_synced_at)
                    elapsed_s = (utc_now() - last_dt).total_seconds()
                    remaining_s = max(0, interval * 60 - elapsed_s)
                    if remaining_s > 0:
                        logger.info(
                            "Phase scheduler [{}] — next run in {:.0f}s", phase_name, remaining_s
                        )
                        await asyncio.sleep(remaining_s)
                    else:
                        logger.info("Phase scheduler [{}] — overdue, triggering now", phase_name)
                else:
                    logger.info("Phase scheduler [{}] — no prior sync, triggering now", phase_name)
            else:
                # Sleep in 30s chunks so config changes take effect quickly
                remaining = interval * 60
                while remaining > 0:
                    chunk = min(30, remaining)
                    await asyncio.sleep(chunk)
                    remaining -= chunk
                    try:
                        cfg = await config_repo.get(get_db())
                        new_interval = _get_interval(cfg)
                    except Exception:
                        break
                    if new_interval != interval:
                        logger.info(
                            "Phase scheduler [{}] — interval changed {}→{}min",
                            phase_name,
                            interval,
                            new_interval,
                        )
                        interval = new_interval
                        remaining = new_interval * 60

            # Wait for phase to finish if already running (with timeout)
            if runner.is_running:
                logger.info("Phase scheduler [{}] — already running, waiting…", phase_name)
                waited = 0
                while runner.is_running and waited < 3600:
                    await asyncio.sleep(10)
                    waited += 10
                    if waited % 30 == 0:
                        await leader.heartbeat()
                if runner.is_running:
                    logger.error(
                        "Phase scheduler [{}] — stuck running for 1h, skipping cycle", phase_name
                    )
                continue

            # Resume from checkpoint if one exists (e.g. previous run crashed
            # mid-sync).  Only fall through to a fresh trigger if there is
            # nothing to resume.
            cp = await runner.load_checkpoint()
            if cp and cp.get("status") != "completed":
                logger.info("Phase scheduler [{}] — resuming from checkpoint", phase_name)
                result = await runner.resume()
                if result is not None:
                    # Wait for the resumed run to finish before the next cycle
                    waited = 0
                    while runner.is_running and waited < 3600:
                        await asyncio.sleep(10)
                        waited += 10
                        if waited % 30 == 0:
                            await leader.heartbeat()
                    await leader.heartbeat()
                    continue
                # resume() returned None (busy or lock held) — fall through

            # Trigger the phase
            logger.info("Phase scheduler [{}] — triggering (interval={}min)", phase_name, interval)
            result = await runner.trigger(mode="incremental")
            if result is None:
                logger.warning(
                    "Phase scheduler [{}] — trigger returned None (busy/locked), skipping",
                    phase_name,
                )
                await asyncio.sleep(60)
                continue

            # Wait for completion before starting next interval (with timeout)
            waited = 0
            while runner.is_running and waited < 3600:
                await asyncio.sleep(10)
                waited += 10
                if waited % 30 == 0:
                    await leader.heartbeat()
            if runner.is_running:
                logger.error("Phase scheduler [{}] — phase stuck running for 1h", phase_name)

            await leader.heartbeat()
    except asyncio.CancelledError:
        await leader.resign()
        logger.info("Phase scheduler [{}] stopped", phase_name)
        raise


async def _weekly_full_sync_scheduler() -> None:
    """Background task that triggers a weekly full sync on Sundays.

    Runs once per day, checks if today is Sunday, and triggers an
    orchestrated full sync if one hasn't already run today.
    """
    from datetime import date

    from database import get_db
    from domains.sync.manager import sync_manager
    from utils.dt import utc_now
    from utils.leader_election import LeaderElection

    await asyncio.sleep(60)

    leader = LeaderElection(get_db(), "sync_weekly_full", ttl_seconds=90)

    last_full_sync_date: date | None = None
    try:
        meta = await get_db()[SYNC_META].find_one({"_id": "global"})
        if meta and meta.get("last_full_sync_date"):
            last_full_sync_date = date.fromisoformat(meta["last_full_sync_date"])
    except Exception as exc:
        logger.warning("Weekly scheduler — could not load last full sync date: {}", exc)

    try:
        while True:
            if not await leader.try_become_leader():
                await asyncio.sleep(60)
                continue

            today = utc_now().date()
            if (  # noqa: SIM102
                utc_now().weekday() == 6 and last_full_sync_date != today
            ):
                if not sync_manager.is_running():
                    logger.info("Weekly scheduler — Sunday full sync")
                    result = await sync_manager.trigger_all(mode="full")
                    if result.get("phases_started"):
                        last_full_sync_date = today
                    else:
                        logger.warning("Weekly scheduler — no phases started, will retry next hour")
                    try:
                        await get_db()[SYNC_META].update_one(
                            {"_id": "global"},
                            {"$set": {"last_full_sync_date": today.isoformat()}},
                            upsert=True,
                        )
                    except Exception as exc:
                        logger.warning(
                            "Weekly scheduler — could not persist last_full_sync_date: {}", exc
                        )

            # Sleep ~1h in 30s increments to keep the leadership heartbeat alive
            for _ in range(120):
                await asyncio.sleep(30)
                await leader.heartbeat()
    except asyncio.CancelledError:
        await leader.resign()
        raise


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle.

    Connects to MongoDB on startup and closes the connection on shutdown.
    Also seeds the taxonomy collection with default data if empty.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control to the application after startup is complete.
    """
    settings = get_settings()
    _configure_logging(settings.log_level)

    logger.info("Starting Sentora (env={})", settings.app_env)
    await connect_db()

    # Ensure all MongoDB indexes exist
    try:
        from database import get_db
        from db_indexes import ensure_all_indexes

        await ensure_all_indexes(get_db())
    except Exception as exc:
        logger.warning("Could not ensure indexes: {}", exc)

    # Seed taxonomy on first run (skipped gracefully if DB is unavailable)
    try:
        from database import get_db
        from domains.taxonomy.seed import seed_taxonomy_if_empty

        await seed_taxonomy_if_empty(get_db())
    except DatabaseUnavailableError:
        logger.warning("Skipping taxonomy seed — MongoDB not available")

    # Mark any classification runs stuck in "running" as failed (stale from prior crash)
    try:
        from database import get_db
        from utils.dt import utc_now

        db = get_db()
        result = await db["classification_runs"].update_many(
            {"status": "running"},
            {
                "$set": {
                    "status": "failed",
                    "completed_at": utc_now(),
                    "error": "Process restarted while run was in progress",
                }
            },
        )
        if result.modified_count:
            logger.warning(
                "Marked {} stale classification run(s) as failed on startup",
                result.modified_count,
            )
        # Mark sync runs stuck in "running" — use "interrupted" if any
        # checkpoint exists (legacy or per-phase), "failed" otherwise.
        checkpoint = await db[SYNC_CHECKPOINT].find_one({"_id": "current"})
        phase_checkpoints = await db[SYNC_CHECKPOINT].count_documents(
            {"_id": {"$regex": "^phase:"}},
        )
        has_resumable = checkpoint is not None or phase_checkpoints > 0
        stale_status = "interrupted" if has_resumable else "failed"
        stale_message = (
            "Process restarted — sync will resume from checkpoint"
            if has_resumable
            else "Process restarted while sync was in progress"
        )
        result = await db[SYNC_RUNS].update_many(
            {"status": "running"},
            {
                "$set": {
                    "status": stale_status,
                    "completed_at": utc_now(),
                    "message": stale_message,
                }
            },
        )
        if result.modified_count:
            logger.warning(
                "Marked {} stale sync run(s) as {} on startup",
                result.modified_count,
                stale_status,
            )
        # If checkpoints or stale runs exist, the previous sync holder is
        # provably dead.  Delete stale distributed locks (both legacy
        # single-lock and per-phase locks).
        if has_resumable or result.modified_count:
            # Clear legacy sync_pipeline lock
            deleted = await db["distributed_locks"].delete_one(
                {"_id": "sync_pipeline"},
            )
            if deleted.deleted_count:
                logger.info("Cleared stale distributed lock 'sync_pipeline'")
            # Clear per-phase locks
            phase_locks = await db["distributed_locks"].delete_many(
                {"_id": {"$regex": "^sync_phase_"}},
            )
            if phase_locks.deleted_count:
                logger.info("Cleared {} stale per-phase locks", phase_locks.deleted_count)
        # Clear stale library ingestion locks (same pattern as sync locks)
        lib_locks = await db["distributed_locks"].delete_many(
            {"_id": {"$regex": "^library_source_"}},
        )
        if lib_locks.deleted_count:
            logger.info("Cleared {} stale library ingestion locks", lib_locks.deleted_count)
        # Also clear backup operation lock in case it was held during crash
        bk_lock = await db["distributed_locks"].delete_one({"_id": "backup_operation"})
        if bk_lock.deleted_count:
            logger.info("Cleared stale backup operation lock")

        # Mark library ingestion runs stuck in "running" as failed
        result = await db["library_ingestion_runs"].update_many(
            {"status": "running"},
            {
                "$set": {
                    "status": "failed",
                    "completed_at": utc_now(),
                    "errors": ["Process restarted while ingestion was in progress"],
                }
            },
        )
        if result.modified_count:
            logger.warning(
                "Marked {} stale library ingestion run(s) as failed on startup",
                result.modified_count,
            )
        # Same for any tag apply operations stuck in "running"
        result = await db["tag_rules"].update_many(
            {"apply_status": "running"},
            {"$set": {"apply_status": "failed"}},
        )
        if result.modified_count:
            logger.warning(
                "Marked {} stale tag apply(s) as failed on startup", result.modified_count
            )
    except Exception as exc:
        logger.warning("Could not clean up stale runs on startup: {}", exc)

    # Bootstrap max_app_id from existing installed_apps if not yet set.
    # normalize_app stores the source integer app ID in the "source_id" field.
    # Legacy documents pre-dating this field simply won't match the filter and
    # are excluded; the watermark will be established by the next full sync.
    try:
        from database import get_db

        db = get_db()
        meta = await db[SYNC_META].find_one({"_id": "global"})
        if not (meta and meta.get("max_app_id")):
            pipeline: list[dict[str, Any]] = [
                {"$match": {"source_id": {"$exists": True, "$ne": ""}}},
                {"$addFields": {"id_long": {"$toLong": "$source_id"}}},
                {"$group": {"_id": None, "max_id": {"$max": "$id_long"}}},
            ]
            result = await db[INSTALLED_APPS].aggregate(pipeline).next()
            if result and result.get("max_id"):
                await db[SYNC_META].update_one(
                    {"_id": "global"},
                    {"$set": {"max_app_id": str(result["max_id"])}},
                    upsert=True,
                )
                logger.info(
                    "Bootstrapped max_app_id={} from existing installed_apps", result["max_id"]
                )
    except StopAsyncIteration:
        pass  # collection is empty or pre-dates source_id field — full sync will set watermark
    except Exception as exc:
        logger.warning("Could not bootstrap max_app_id: {}", exc)

    # Ensure materialized app summaries exist (instant reads for /api/v1/apps/)
    try:
        from database import get_db as _get_db_for_summaries
        from domains.agents.app_cache import ensure_app_summaries_exist

        await ensure_app_summaries_exist(_get_db_for_summaries())
    except Exception as exc:
        logger.warning("Could not build app summaries on startup: {}", exc)

    # Initialize audit hash-chain (create genesis entry if not exists)
    try:
        from audit.chain.commands import initialize_chain
        from database import get_db as _get_db_for_chain

        await initialize_chain(_get_db_for_chain())
        logger.info("Audit hash-chain ready")
    except Exception as exc:
        logger.warning("Could not initialize audit hash-chain: {}", exc)

    # Load sync run history from MongoDB so state survives process restarts
    try:
        from domains.sync.manager import sync_manager

        await sync_manager.init()
    except Exception as exc:
        logger.warning("Could not initialize SyncManager from DB: {}", exc)

    # Initialize library ingestion manager (PubSub relay for multi-worker WS)
    try:
        from domains.library.ingestion_manager import ingestion_manager

        await ingestion_manager.init()
    except Exception as exc:
        logger.warning("Could not initialize IngestionManager: {}", exc)

    # Start user revocation cache refresh (bounds disabled-user JWT gap to ~30s)
    from utils.user_revocation import refresh_revoked_users_loop

    revocation_task = asyncio.create_task(refresh_revoked_users_loop())

    # Start session revocation cache refresh (bounds revoked-session JWT gap to ~30s)
    from domains.auth.session_revocation import refresh_revoked_sessions_loop

    session_revocation_task = asyncio.create_task(refresh_revoked_sessions_loop())

    # Start per-phase schedulers — each phase runs on its own independent schedule
    phase_scheduler_tasks: list[asyncio.Task] = []  # type: ignore[type-arg]
    for phase in ("sites", "groups", "agents", "apps", "tags"):
        task = asyncio.create_task(_phase_scheduler(phase))
        phase_scheduler_tasks.append(task)
    # Weekly full sync scheduler (Sundays)
    weekly_task = asyncio.create_task(_weekly_full_sync_scheduler())
    phase_scheduler_tasks.append(weekly_task)
    logger.info("Phase schedulers started (5 phases + weekly full sync)")

    # Start backup scheduler if enabled
    backup_scheduler_task: asyncio.Task | None = None  # type: ignore[type-arg]
    if settings.backup_enabled:
        from utils.backup_scheduler import backup_scheduler

        backup_scheduler_task = asyncio.create_task(backup_scheduler())
        logger.info("Backup scheduler started")

    yield

    revocation_task.cancel()
    with suppress(asyncio.CancelledError):
        await revocation_task

    session_revocation_task.cancel()
    with suppress(asyncio.CancelledError):
        await session_revocation_task

    if backup_scheduler_task:
        backup_scheduler_task.cancel()
        with suppress(asyncio.CancelledError, RuntimeError):
            await backup_scheduler_task

    for task in phase_scheduler_tasks:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    # Clean up ingestion manager PubSub task
    try:
        from domains.library.ingestion_manager import ingestion_manager

        if ingestion_manager._pubsub_task is not None:
            ingestion_manager._pubsub_task.cancel()
            with suppress(asyncio.CancelledError):
                await ingestion_manager._pubsub_task
    except Exception:
        pass

    await close_db()
    logger.info("Sentora shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    The backend serves the compiled Vue frontend from ``frontend/dist/`` so
    a single process handles both the API and the UI. During development the
    Vite dev server (port 5003) can be used instead — CORS is opened for it.

    Returns:
        A fully configured FastAPI instance ready to serve requests.
    """
    settings = get_settings()

    app = FastAPI(
        title="Sentora",
        description="Software Fingerprint & Asset Classification Tool",
        version="0.1.0",
        docs_url="/api/docs" if settings.is_development else None,
        redoc_url="/api/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )

    # CORS — allow Vite dev server during development
    origins = ["http://localhost:5003"] if settings.is_development else []
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=settings.is_development,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID", "X-Tenant-ID", "X-API-Key"],
    )

    # Multi-tenancy middleware (conditionally mounted)
    if settings.multi_tenancy_enabled:
        from middleware.tenant import TenantMiddleware

        app.add_middleware(TenantMiddleware)

    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)

    # Exception handlers (most specific first)
    app.add_exception_handler(SentoraError, sentora_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(DatabaseUnavailableError, database_unavailable_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Health check — used by Docker healthcheck and load balancers
    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", include_in_schema=False)
    async def health_ready() -> JSONResponse:
        """Readiness probe — verifies MongoDB is reachable."""
        try:
            from database import check_replica_set_status, get_db

            await get_db().command("ping")
            result: dict = {"status": "ready"}
            rs = await check_replica_set_status()
            if rs:
                result["replica_set"] = rs.get("set_name")
                result["members"] = rs.get("member_count")
                healthy = all(m.get("health") == 1 for m in rs.get("members", []))
                if not healthy:
                    result["status"] = "degraded"
            return JSONResponse(result)
        except Exception:
            return JSONResponse({"status": "not_ready"}, status_code=503)

    # Replica set status endpoint (admin only)
    from domains.auth.entities import UserRole
    from middleware.auth import require_role

    @app.get(
        "/health/replica",
        include_in_schema=False,
        dependencies=[Depends(require_role(UserRole.admin))],
    )
    async def health_replica() -> JSONResponse:
        """Return full replica set status (admin only)."""
        from database import check_replica_set_status

        rs = await check_replica_set_status()
        if rs is None:
            return JSONResponse(
                {"detail": "Not running in replica set mode"},
                status_code=404,
            )
        return JSONResponse(rs)

    # Prometheus metrics endpoint (admin only)

    @app.get(
        "/metrics",
        include_in_schema=False,
        dependencies=[Depends(require_role(UserRole.admin))],
    )
    async def prometheus_metrics() -> Response:
        """Return Prometheus metrics in text exposition format."""
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
        from starlette.responses import Response as StarletteResponse

        return StarletteResponse(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    # OpenAPI spec export (requires authentication)
    @app.get(
        "/api/spec.json",
        include_in_schema=False,
        dependencies=[Depends(require_role(UserRole.admin))],
    )
    async def openapi_json() -> JSONResponse:
        """Return the OpenAPI schema as JSON."""
        return JSONResponse(app.openapi())

    @app.get(
        "/api/spec.yaml",
        include_in_schema=False,
        dependencies=[Depends(require_role(UserRole.admin))],
    )
    async def openapi_yaml() -> Response:
        """Return the OpenAPI schema as YAML (requires PyYAML)."""
        try:
            import yaml
        except ImportError:
            return JSONResponse(
                {"detail": "PyYAML is not installed — use /api/spec.json instead"},
                status_code=501,
            )
        from starlette.responses import Response as StarletteResponse

        return StarletteResponse(
            content=yaml.dump(app.openapi(), default_flow_style=False, sort_keys=False),
            media_type="application/x-yaml",
        )

    # Deployment info — public, no auth (frontend needs it before login)
    @app.get("/api/v1/deployment-info", include_in_schema=False)
    async def deployment_info() -> dict:
        """Return deployment mode and feature flags for the frontend."""
        return {
            "deployment_mode": settings.deployment_mode,
            "multi_tenancy_enabled": settings.multi_tenancy_enabled,
            "oidc_enabled": settings.oidc_enabled,
            "saml_enabled": settings.saml_enabled,
        }

    # Dev-only: reset rate limiters (for E2E testing)
    if settings.is_development:

        @app.post("/api/v1/test/reset-rate-limits", include_in_schema=False)
        async def reset_rate_limits() -> dict[str, str]:
            """Reset all in-memory rate limiters. Dev/test only."""
            from domains.auth.router import (
                _refresh_limiter,
                _register_limiter,
                _totp_limiter,
            )

            _register_limiter.reset()
            _refresh_limiter.reset()
            _totp_limiter.reset()
            # Also reset global middleware rate limiter
            inner = app.middleware_stack
            while inner is not None:
                if isinstance(inner, RateLimitMiddleware):
                    inner._global_limiter.reset()
                    for limiter in inner._strict_limiters.values():
                        limiter.reset()
                    break
                inner = getattr(inner, "app", None)
            return {"status": "ok"}

    # OpenTelemetry tracing (opt-in)
    from middleware.tracing import setup_tracing

    setup_tracing(app)

    # API routers
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(agents_router, prefix="/api/v1/agents", tags=["agents"])
    app.include_router(apps_router, prefix="/api/v1/apps", tags=["apps"])
    app.include_router(groups_router, prefix="/api/v1/groups", tags=["groups"])
    app.include_router(sites_router, prefix="/api/v1/sites", tags=["sites"])
    app.include_router(taxonomy_router, prefix="/api/v1/taxonomy", tags=["taxonomy"])
    app.include_router(sync_router, prefix="/api/v1/sync", tags=["sync"])
    app.include_router(
        classification_router, prefix="/api/v1/classification", tags=["classification"]
    )
    app.include_router(fingerprint_router, prefix="/api/v1/fingerprints", tags=["fingerprint"])
    app.include_router(suggestions_router, prefix="/api/v1/suggestions", tags=["suggestions"])
    app.include_router(config_router, prefix="/api/v1/config", tags=["config"])
    app.include_router(branding_router, prefix="/api/v1/branding", tags=["branding"])
    app.include_router(audit_router, prefix="/api/v1/audit", tags=["audit"])
    app.include_router(audit_chain_router, prefix="/api/v1/audit/chain", tags=["audit-chain"])
    app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])
    app.include_router(tags_router, prefix="/api/v1/tags", tags=["tags"])
    app.include_router(webhooks_router, prefix="/api/v1/webhooks", tags=["webhooks"])
    app.include_router(library_router, prefix="/api/v1/library", tags=["library"])
    app.include_router(demo_router, prefix="/api/v1/demo", tags=["demo"])
    app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
    app.include_router(admin_ws_router, prefix="/api/v1/admin", tags=["admin"])
    app.include_router(compliance_router, prefix="/api/v1/compliance", tags=["compliance"])
    app.include_router(enforcement_router, prefix="/api/v1/enforcement", tags=["enforcement"])
    app.include_router(eol_router, prefix="/api/v1/eol", tags=["eol"])
    app.include_router(export_router, prefix="/api/v1/export", tags=["export"])
    app.include_router(api_keys_router, prefix="/api/v1/api-keys", tags=["api-keys"])
    app.include_router(tenant_router, prefix="/api/v1/tenants", tags=["tenants"])

    # Serve compiled frontend static assets.
    # Mount /assets so Vite's content-hashed filenames resolve correctly.
    # The SPA catch-all handles all remaining paths → index.html.
    if _FRONTEND_DIST.exists():
        assets_dir = _FRONTEND_DIST / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse:
            """Serve index.html for all non-API routes (Vue Router SPA support).

            Any path that isn't matched by an API route falls through to this
            handler, which returns the frontend's index.html so Vue Router can
            handle client-side navigation.

            Args:
                full_path: The unmatched URL path.

            Returns:
                FileResponse serving frontend/dist/index.html.
            """
            return FileResponse(str(_FRONTEND_DIST / "index.html"))

    return app


app = create_app()
