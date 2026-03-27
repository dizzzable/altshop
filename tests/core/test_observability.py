from src.core.observability import (
    clear_metrics_registry,
    emit_counter,
    render_metrics_text,
    set_gauge,
)


def setup_function() -> None:
    clear_metrics_registry()


def teardown_function() -> None:
    clear_metrics_registry()


def test_render_metrics_text_exports_counters_and_gauges() -> None:
    emit_counter("payment_webhook_enqueue_failures_total", gateway_type="platega")
    emit_counter("payment_webhook_enqueue_failures_total", gateway_type="platega")
    set_gauge("backend_dependency_status", 1, dependency="postgresql")

    rendered = render_metrics_text()

    assert "# TYPE payment_webhook_enqueue_failures_total counter" in rendered
    assert 'payment_webhook_enqueue_failures_total{gateway_type="platega"} 2' in rendered
    assert "# TYPE backend_dependency_status gauge" in rendered
    assert 'backend_dependency_status{dependency="postgresql"} 1' in rendered
