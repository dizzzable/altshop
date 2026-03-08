from __future__ import annotations

from loguru import logger


def emit_counter(metric_name: str, /, **labels: object) -> None:
    if labels:
        rendered_labels = ", ".join(f"{name}={labels[name]!r}" for name in sorted(labels))
        logger.info("counter {} {}", metric_name, rendered_labels)
        return

    logger.info("counter {}", metric_name)
