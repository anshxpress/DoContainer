import logging
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor

logger = logging.getLogger(__name__)

# Set tracer provider
provider = TracerProvider()

# Setup exporter: default to a simple ConsoleSpanExporter or no-op if disabled to keep terminal clean
otel_console_export = os.getenv("OTEL_CONSOLE_EXPORT", "false").lower() == "true"

if otel_console_export:
    processor = SimpleSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)

trace.set_tracer_provider(provider)
tracer = trace.get_tracer("docscope")

def instrument_app(app):
    """
    Day 4: Instrument FastAPI application with OpenTelemetry middleware.
    """
    try:
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        logger.info("FastAPI application instrumented with OpenTelemetry.")
    except Exception as e:
        logger.warning(f"FastAPI OpenTelemetry instrumentation failed: {e}")

def instrument_celery():
    """
    Day 4: Instrument Celery workers with OpenTelemetry tracer hooks.
    """
    try:
        CeleryInstrumentor().instrument(tracer_provider=provider)
        logger.info("Celery workers instrumented with OpenTelemetry.")
    except Exception as e:
        logger.warning(f"Celery OpenTelemetry instrumentation failed: {e}")
