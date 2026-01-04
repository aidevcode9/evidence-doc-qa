import os

from .config import OTEL_ENABLED, OTEL_SERVICE_NAME
from .telemetry import logger

_OTEL_INITIALIZED = False


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
