"""OpenTelemetry distributed tracing integration.

Opt-in: only initializes when ``otel_enabled=True`` in config. Automatically
instruments FastAPI, httpx (used by S1Client), and Motor (MongoDB) if the
respective instrumentation packages are available.

Call ``setup_tracing(app)`` from main.py during application creation.
"""

from __future__ import annotations

from loguru import logger


def setup_tracing(app: object) -> None:
    """Initialize OpenTelemetry tracing if enabled in config.

    This function is safe to call unconditionally — it does nothing when
    ``otel_enabled`` is False or when the required packages are not installed.

    Args:
        app: The FastAPI application instance.
    """
    from config import get_settings

    settings = get_settings()
    if not settings.otel_enabled:
        logger.debug("OpenTelemetry tracing is disabled (otel_enabled=False)")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning(
            "OpenTelemetry packages not installed — tracing disabled. "
            "Install: opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp"
        )
        return

    # Configure the tracer provider
    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    logger.info(
        "OpenTelemetry tracing enabled — exporting to {} as '{}'",
        settings.otel_endpoint,
        settings.otel_service_name,
    )

    # Auto-instrument FastAPI
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)  # type: ignore[arg-type]
        logger.info("OpenTelemetry: FastAPI instrumented")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-fastapi not installed — skipping")
    except Exception as exc:
        logger.warning("Failed to instrument FastAPI: {}", exc)

    # Auto-instrument httpx (used by S1Client for SentinelOne API calls)
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        logger.info("OpenTelemetry: httpx instrumented")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-httpx not installed — skipping")
    except Exception as exc:
        logger.warning("Failed to instrument httpx: {}", exc)

    # Auto-instrument Motor/PyMongo (MongoDB driver)
    try:
        from opentelemetry.instrumentation.pymongo import PymongoInstrumentor

        PymongoInstrumentor().instrument()
        logger.info("OpenTelemetry: PyMongo instrumented")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-pymongo not installed — skipping")
    except Exception as exc:
        logger.warning("Failed to instrument PyMongo: {}", exc)
