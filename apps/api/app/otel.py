import os
from contextlib import contextmanager
from app.config import OTEL_ENABLED, OTEL_SERVICE_NAME
from app.telemetry import logger

_OTEL_INITIALIZED = False

try:
    from opentelemetry import trace
    _TRACER = trace.get_tracer("docqa.api")
except Exception:
    _TRACER = None


@contextmanager
def span(name: str, **attrs):
    if not _TRACER or not OTEL_ENABLED:
        yield None
        return
    with _TRACER.start_as_current_span(name) as s:
        for key, value in attrs.items():
            if value is not None:
                s.set_attribute(key, value)
        yield s


def setup_otel(app) -> None:
    global _OTEL_INITIALIZED
    if _OTEL_INITIALIZED or not OTEL_ENABLED:
        return

    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    if not connection_string:
        logger.warning("OpenTelemetry disabled: APPLICATIONINSIGHTS_CONNECTION_STRING not set.")
        return

    try:
        from opentelemetry import trace
        try:
            from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
        except Exception:
            from opentelemetry.exporter.azuremonitor import AzureMonitorTraceExporter
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
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    URLLibInstrumentor().instrument()
    _OTEL_INITIALIZED = True
    logger.info("OpenTelemetry enabled for FastAPI.")
