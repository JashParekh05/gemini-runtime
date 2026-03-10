"""OpenTelemetry setup — extends the tracing already present in gemini-cli core."""

from __future__ import annotations

import logging

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from shared.config import settings

logger = logging.getLogger(__name__)

_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None


def setup_telemetry(service_name: str) -> None:
    global _tracer_provider, _meter_provider

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": "0.1.0",
            "deployment.environment": "development",
        }
    )

    # ── traces ─────────────────────────────────────────────────────────────────
    _tracer_provider = TracerProvider(resource=resource)

    if settings.otel_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
            _tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("OTLP trace exporter configured: %s", settings.otel_endpoint)
        except ImportError:
            logger.warning("opentelemetry-exporter-otlp not installed, falling back to console")
            _tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        _tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(_tracer_provider)

    # ── metrics ────────────────────────────────────────────────────────────────
    reader = PeriodicExportingMetricReader(ConsoleMetricExporter(), export_interval_millis=60_000)
    _meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(_meter_provider)

    logger.info("OpenTelemetry configured for service: %s", service_name)


def get_tracer(name: str = "gemini-runtime") -> trace.Tracer:
    return trace.get_tracer(name)


def get_meter(name: str = "gemini-runtime") -> metrics.Meter:
    return metrics.get_meter(name)


# ── standard metrics ───────────────────────────────────────────────────────────

def create_standard_metrics(service_name: str) -> dict[str, object]:
    meter = get_meter(service_name)
    return {
        "tool_latency": meter.create_histogram(
            "agent.tool.latency",
            unit="ms",
            description="Latency of individual tool calls",
        ),
        "tokens_total": meter.create_counter(
            "agent.tokens.total",
            unit="tokens",
            description="Total tokens consumed",
        ),
        "errors_total": meter.create_counter(
            "agent.errors.total",
            description="Total agent errors",
        ),
        "sessions_active": meter.create_up_down_counter(
            "agent.sessions.active",
            description="Currently active sessions",
        ),
    }
