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
langfuse_context: Any = None
try:
    from langfuse import Langfuse as LangfuseClient
    from langfuse.decorators import observe as langfuse_observe, langfuse_context as _langfuse_context
    Langfuse = LangfuseClient
    observe = langfuse_observe
    langfuse_context = _langfuse_context
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


def safe_update_observation(
    *,
    model: str | None = None,
    usage: dict[str, int] | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    """Attach model/token/cost to current @observe span. No-op if Langfuse disabled.

    Safe to call unconditionally — silently does nothing if Langfuse is not
    active or if the underlying API call fails.
    """
    if not _LANGFUSE_INITIALIZED or langfuse_context is None:
        return

    try:
        kwargs: dict[str, object] = {}
        if model is not None:
            kwargs["model"] = model
        if usage is not None:
            kwargs["usage"] = usage
        if metadata is not None:
            kwargs["metadata"] = metadata
        langfuse_context.update_current_observation(**kwargs)
    except Exception as exc:  # noqa: BLE001 - never break request pipeline
        logger.debug("Langfuse update_current_observation failed: %s", exc)


def safe_update_trace(
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    """Attach identity/session to current trace root. No-op if Langfuse disabled.

    Safe to call unconditionally — silently does nothing if Langfuse is not
    active or if the underlying API call fails.
    """
    if not _LANGFUSE_INITIALIZED or langfuse_context is None:
        return

    try:
        kwargs: dict[str, object] = {}
        if user_id is not None:
            kwargs["user_id"] = user_id
        if session_id is not None:
            kwargs["session_id"] = session_id
        if tags is not None:
            kwargs["tags"] = tags
        if metadata is not None:
            kwargs["metadata"] = metadata
        langfuse_context.update_current_trace(**kwargs)
    except Exception as exc:  # noqa: BLE001 - never break request pipeline
        logger.debug("Langfuse update_current_trace failed: %s", exc)


def safe_get_trace_id() -> str | None:
    """Get current Langfuse trace ID for DB correlation. None if disabled.

    Safe to call unconditionally — returns None if Langfuse is not active
    or if the underlying API call fails.
    """
    if not _LANGFUSE_INITIALIZED or langfuse_context is None:
        return None

    try:
        trace_id: str = langfuse_context.get_current_trace_id()
        return trace_id if trace_id else None
    except Exception as exc:  # noqa: BLE001 - never break request pipeline
        logger.debug("Langfuse get_current_trace_id failed: %s", exc)
        return None


def redact_for_langfuse(
    *,
    question_len: int = 0,
    answer_len: int = 0,
    citation_count: int = 0,
    evidence_grade: str | None = None,
    evidence_label: str | None = None,
    refusal_code: str | None = None,
    verification_status: str | None = None,
    doc_count: int | None = None,
) -> dict[str, object]:
    """Create PII-safe summary for Langfuse observation metadata.

    Returns a dict with only safe metrics — never raw question text,
    answer text, document snippets, or document names (which may contain
    client names in a law firm context). Compliant with NFR-004.
    """
    summary: dict[str, object] = {
        "question_len": question_len,
        "answer_len": answer_len,
        "citation_count": citation_count,
    }
    if evidence_grade is not None:
        summary["evidence_grade"] = evidence_grade
    if evidence_label is not None:
        summary["evidence_label"] = evidence_label
    if refusal_code is not None:
        summary["refusal_code"] = refusal_code
    if verification_status is not None:
        summary["verification_status"] = verification_status
    if doc_count is not None:
        summary["doc_count"] = doc_count
    return summary


def set_genai_span_attributes(
    *,
    system: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    request_id: str | None = None,
) -> None:
    """Set GenAI semantic convention attributes on current OTEL span (NFR-022).

    No-op if OTEL is disabled or no current span exists.
    """
    if not OTEL_ENABLED:
        return

    try:
        current_span = trace.get_current_span()
        if current_span is None or not current_span.is_recording():
            return

        current_span.set_attribute("gen_ai.system", system)
        current_span.set_attribute("gen_ai.request.model", model)
        current_span.set_attribute("gen_ai.usage.prompt_tokens", prompt_tokens)
        current_span.set_attribute("gen_ai.usage.completion_tokens", completion_tokens)
        current_span.set_attribute("llm.latency_ms", latency_ms)
        if request_id is not None:
            current_span.set_attribute("llm.request_id", request_id)
    except Exception as exc:  # noqa: BLE001 - never break request pipeline
        logger.debug("set_genai_span_attributes failed: %s", exc)


# ---------------------------------------------------------------------------
# OTEL Custom Metrics (NFR-022)
# ---------------------------------------------------------------------------

_METER: Any = None
_REQUEST_COUNTER: Any = None
_LATENCY_HISTOGRAM: Any = None
_TOKEN_COUNTER: Any = None
_CACHE_HIT_COUNTER: Any = None
_COST_COUNTER: Any = None

try:
    from opentelemetry import metrics as _otel_metrics

    _METER = _otel_metrics.get_meter("docqa.api")
    _REQUEST_COUNTER = _METER.create_counter(
        "docqa.request.count",
        description="Total API requests",
    )
    _LATENCY_HISTOGRAM = _METER.create_histogram(
        "docqa.request.latency_ms",
        description="Request latency in milliseconds",
        unit="ms",
    )
    _TOKEN_COUNTER = _METER.create_counter(
        "docqa.tokens.total",
        description="Total tokens consumed",
    )
    _CACHE_HIT_COUNTER = _METER.create_counter(
        "docqa.cache.hit",
        description="Cache hit count",
    )
    _COST_COUNTER = _METER.create_counter(
        "docqa.cost.usd",
        description="Estimated cost in USD",
    )
except Exception:  # noqa: BLE001 - metrics SDK optional
    pass


def record_request_metrics(
    *,
    latency_ms: int,
    tokens_in: int,
    tokens_out: int,
    cost_est: float,
    cache_hit: bool,
    component: str,
    refusal_code: str | None = None,
) -> None:
    """Record OTEL custom metrics for a request (NFR-022).

    Safe to call unconditionally — no-op if metrics SDK is unavailable.
    """
    try:
        attrs = {"component": component}
        if refusal_code:
            attrs["refusal_code"] = refusal_code
        attrs["cache_hit"] = str(cache_hit).lower()

        if _REQUEST_COUNTER is not None:
            _REQUEST_COUNTER.add(1, attrs)
        if _LATENCY_HISTOGRAM is not None:
            _LATENCY_HISTOGRAM.record(latency_ms, {"component": component})
        if _TOKEN_COUNTER is not None:
            _TOKEN_COUNTER.add(tokens_in, {"direction": "input", "component": component})
            _TOKEN_COUNTER.add(tokens_out, {"direction": "output", "component": component})
        if cache_hit and _CACHE_HIT_COUNTER is not None:
            _CACHE_HIT_COUNTER.add(1, {"cache_type": component})
        if _COST_COUNTER is not None and cost_est > 0:
            _COST_COUNTER.add(cost_est, {"component": component})
    except Exception as exc:  # noqa: BLE001 - never break request pipeline
        logger.debug("record_request_metrics failed: %s", exc)


def flush_langfuse() -> None:
    """Flush pending Langfuse traces on shutdown.

    Call this in app shutdown event to ensure all traces are sent
    before the process exits. Flushes both the Langfuse client and
    the decorator context (which maintains its own trace buffer).
    """
    # Flush the decorator context first (used by @observe decorators)
    if langfuse_context is not None:
        try:
            langfuse_context.flush()
            logger.debug("Langfuse decorator context flushed.")
        except Exception as exc:  # noqa: BLE001 - defensive flush
            logger.warning("Langfuse decorator context flush failed: %s", exc)

    # Flush the explicit client (used for manual tracing)
    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
            logger.debug("Langfuse client flushed.")
        except Exception as exc:  # noqa: BLE001 - defensive flush
            logger.warning("Langfuse client flush failed: %s", exc)
