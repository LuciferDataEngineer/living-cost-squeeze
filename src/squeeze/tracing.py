"""OpenTelemetry spans for each pipeline step.

Local runs can also export to Jaeger over OTLP. CI keeps the JSONL file
written next to the timings summary.
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Status, StatusCode

from squeeze.paths import TRACES

_PROVIDER: TracerProvider | None = None


class JsonlSpanExporter(SpanExporter):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("")

    def export(self, spans):
        with self.path.open("a", encoding="utf-8") as handle:
            for span in spans:
                duration_ms = (span.end_time - span.start_time) / 1_000_000
                handle.write(
                    json.dumps(
                        {
                            "name": span.name,
                            "duration_ms": round(duration_ms, 2),
                            "status": span.status.status_code.name,
                            "attributes": dict(span.attributes or {}),
                        }
                    )
                    + "\n"
                )
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


def setup_tracing(path: Path | None = None) -> None:
    global _PROVIDER
    provider = TracerProvider(resource=Resource.create({"service.name": "living-cost-squeeze"}))
    provider.add_span_processor(SimpleSpanProcessor(JsonlSpanExporter(path or TRACES)))
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        if not endpoint.endswith("/v1/traces"):
            endpoint = endpoint.rstrip("/") + "/v1/traces"
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    _PROVIDER = provider


def shutdown_tracing() -> None:
    if _PROVIDER is not None:
        _PROVIDER.force_flush()
        _PROVIDER.shutdown()


@contextmanager
def step(name: str, **attributes: str | int | float):
    tracer = trace.get_tracer("squeeze")
    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            span.set_attribute(key, value)
        started = time.perf_counter()
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
        finally:
            span.set_attribute("duration_ms", round((time.perf_counter() - started) * 1000, 2))
