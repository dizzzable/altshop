from __future__ import annotations

from collections import defaultdict
from threading import Lock

from loguru import logger

_registry_lock = Lock()
_counter_registry: dict[str, dict[tuple[tuple[str, str], ...], float]] = defaultdict(dict)
_gauge_registry: dict[str, dict[tuple[tuple[str, str], ...], float]] = defaultdict(dict)


def _normalize_label_value(value: object) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _normalize_labels(labels: dict[str, object]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((name, _normalize_label_value(value)) for name, value in labels.items()))


def _escape_metric_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _render_metric_line(
    metric_name: str,
    labels: tuple[tuple[str, str], ...],
    value: float,
) -> str:
    rendered = metric_name
    if labels:
        rendered_labels = ",".join(
            f'{name}="{_escape_metric_label(label_value)}"' for name, label_value in labels
        )
        rendered += f"{{{rendered_labels}}}"

    numeric_value = int(value) if value.is_integer() else value
    return f"{rendered} {numeric_value}"


def emit_counter(metric_name: str, /, **labels: object) -> None:
    normalized_labels = _normalize_labels(labels)
    with _registry_lock:
        samples = _counter_registry.setdefault(metric_name, {})
        samples[normalized_labels] = samples.get(normalized_labels, 0.0) + 1.0

    if labels:
        rendered_labels = ", ".join(f"{name}={labels[name]!r}" for name in sorted(labels))
        logger.info("counter {} {}", metric_name, rendered_labels)
        return

    logger.info("counter {}", metric_name)


def set_gauge(metric_name: str, value: float | int, /, **labels: object) -> None:
    normalized_labels = _normalize_labels(labels)
    with _registry_lock:
        samples = _gauge_registry.setdefault(metric_name, {})
        samples[normalized_labels] = float(value)


def render_metrics_text() -> str:
    with _registry_lock:
        counter_snapshot = {
            metric_name: dict(samples)
            for metric_name, samples in _counter_registry.items()
        }
        gauge_snapshot = {
            metric_name: dict(samples)
            for metric_name, samples in _gauge_registry.items()
        }

    lines: list[str] = []
    for metric_name, metric_type, samples in (
        *(
            (name, "counter", counter_snapshot[name])
            for name in sorted(counter_snapshot)
        ),
        *((name, "gauge", gauge_snapshot[name]) for name in sorted(gauge_snapshot)),
    ):
        lines.append(f"# TYPE {metric_name} {metric_type}")
        for labels, value in sorted(samples.items()):
            lines.append(_render_metric_line(metric_name, labels, value))

    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def clear_metrics_registry() -> None:
    with _registry_lock:
        _counter_registry.clear()
        _gauge_registry.clear()
