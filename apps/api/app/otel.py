import os
from contextlib import contextmanager
from typing import Any, Callable, Generator, TypeVar, TYPE_CHECKING

from app.config import (
    OTEL_ENABLED,
    OTEL_SERVICE_NAME,
    LANGFUSE_ENABLED,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
    LANGFUSE_HOST,
)
from app.telemetry import logger

F = TypeVar("F", bound=Callable[..., Any])

if TYPE_CHECKING:
    from fastapi import FastAPI

_OTEL_INITIALIZED = False
_TRACER: Any = None

# Langfuse state (NFR-045)
_LANGFUSE_INITIALIZED = False
_langfuse_client: Any = None

# Try to import Langfuse (optional dependency)
Langfuse: Any = None
observe: Any = None
try:
    from langfuse import Langfuse as LangfuseClient
    from langfuse.decorators import observe as langfuse_observe
    Langfuse = LangfuseClient
    observe = langfuse_observe
except ImportError:
    pass


def _noop_observe(
    *,
    name: str | None = None,
    as_type: str | None = None,
    capture_input: bool = True,
    capture_output: bool = True,
) -> Callable[[F], F]:
    """No-op @observe decorator when Langfuse is not installed.

    Provides graceful degradation: functions work normally without tracing.
    """
    def decorator(func: F) -> F:
        return func
    return decorator


def get_observe_decorator() -> Callable[..., Callable[[F], F]]:
    """Get the @observe decorator (Langfuse or no-op fallback).

    Usage:
        from app.otel import get_observe_decorator
        observe = get_observe_decorator()

        @observe(name="my_function", capture_input=False, capture_output=False)
        def my_function(): ...
    """
    if observe is not None and LANGFUSE_ENABLED:
        return observe  # type: ignore[no-any-return]
    return _noop_observe

try:
    from opentelemetry import trace
    _TRACER = trace.get_tracer("docqa.api")
except Exception:
    pass


@contextmanager
def span(name: str, **attrs: Any) -> Generator[Any, None, None]:
    if not _TRACER or not OTEL_ENABLED:
        yield None
        return
    with _TRACER.start_as_current_span(name) as s:
        for key, value in attrs.items():
            if value is not None:
                s.set_attribute(key, value)
        yield s


def setup_otel(app: "FastAPI") -> None:
    global _OTEL_INITIALIZED
    if _OTEL_INITIALIZED or not OTEL_ENABLED:
        return

    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    if not connection_string:
        logger.warning("OpenTelemetry disabled: APPLICATIONINSIGHTS_CONNECTION_STRING not set.")
        return

    try:
        from opentelemetry import trace as otel_trace
        AzureMonitorTraceExporter: Any = None
        try:
            from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter as AzureExporter
            AzureMonitorTraceExporter = AzureExporter
        except Exception:
            from opentelemetry.exporter.azuremonitor import AzureMonitorTraceExporter as AzureExporterAlt
            AzureMonitorTraceExporter = AzureExporterAlt
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.urllib import URLLibInstrumentor
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception as exc:  # noqa: BLE001 - defensive import
        logger.warning("OpenTelemetry unavailable: %s", exc)
        return

    resource = Resource.create({SERVICE_NAME: OTEL_SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    exporter = AzureMonitorTraceExporter(connection_string=connection_string)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    otel_trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    URLLibInstrumentor().instrument()
    _OTEL_INITIALIZED = True
    logger.info("OpenTelemetry enabled for FastAPI.")


def setup_langfuse() -> None:
    """Initialize Langfuse LLM observability (NFR-045).

    Langfuse provides a debugging UI for LLM traces. When enabled:
    - Every LLM call is traced with model, tokens, latency
    - Traces visible at Langfuse dashboard
    - PII-safe: capture_input=False, capture_output=False by default

    Requires:
    - LANGFUSE_ENABLED=1
    - LANGFUSE_PUBLIC_KEY=pk-lf-xxx
    - LANGFUSE_SECRET_KEY=sk-lf-xxx
    """
    global _LANGFUSE_INITIALIZED, _langfuse_client

    if _LANGFUSE_INITIALIZED:
        return

    if not LANGFUSE_ENABLED:
        logger.debug("Langfuse disabled: LANGFUSE_ENABLED not set or missing keys.")
        return

    if Langfuse is None:
        logger.warning("Langfuse disabled: langfuse package not installed.")
        return

    try:
        _langfuse_client = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST,
        )
        _LANGFUSE_INITIALIZED = True
        logger.info("Langfuse enabled: %s", LANGFUSE_HOST)
    except Exception as exc:  # noqa: BLE001 - defensive init
        logger.warning("Langfuse initialization failed: %s", exc)


def flush_langfuse() -> None:
    """Flush pending Langfuse traces on shutdown.

    Call this in app shutdown event to ensure all traces are sent
    before the process exits.
    """
    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
            logger.debug("Langfuse traces flushed.")
        except Exception as exc:  # noqa: BLE001 - defensive flush
            logger.warning("Langfuse flush failed: %s", exc)
