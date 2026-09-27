"""Small, dependency-free resilience helpers for external AI providers."""

from __future__ import annotations

import logging
import os
import random
import re
import time
from typing import Any, Callable, TypeVar


logger = logging.getLogger(__name__)

T = TypeVar("T")

_TRANSIENT_PROVIDER_CODES = {408, 429, 500, 502, 503, 504}


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def _bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def provider_status_code(exc: Exception) -> int | None:
    """Extract an HTTP-like status code from Google SDK and transport errors."""
    candidates = [
        getattr(exc, "code", None),
        getattr(exc, "status_code", None),
        getattr(getattr(exc, "response", None), "status_code", None),
    ]
    for candidate in candidates:
        if callable(candidate):
            try:
                candidate = candidate()
            except TypeError:
                candidate = None
        try:
            code = int(candidate)
        except (TypeError, ValueError):
            continue
        if 100 <= code <= 599:
            return code

    match = re.search(r"\b(408|429|500|502|503|504)\b", str(exc))
    return int(match.group(1)) if match else None


def call_with_transient_retry(
    operation: Callable[[], T],
    *,
    provider_name: str = "AI provider",
    attempts: int | None = None,
    base_delay_seconds: float | None = None,
    sleep: Callable[[float], Any] = time.sleep,
    random_value: Callable[[], float] = random.random,
) -> T:
    """Retry only capacity, throttling, and temporary server failures.

    The total attempts and delay are deliberately bounded so an overloaded
    provider cannot hold an API worker indefinitely. Non-transient errors are
    returned to the caller immediately so its existing fallback can run.
    """
    max_attempts = attempts if attempts is not None else _bounded_int(
        "GEMINI_RETRY_ATTEMPTS", 3, 1, 4
    )
    base_delay = base_delay_seconds if base_delay_seconds is not None else _bounded_float(
        "GEMINI_RETRY_BASE_SECONDS", 0.75, 0.1, 5.0
    )
    max_attempts = max(1, min(int(max_attempts), 4))
    base_delay = max(0.0, min(float(base_delay), 5.0))

    for attempt_number in range(1, max_attempts + 1):
        try:
            return operation()
        except Exception as exc:
            status_code = provider_status_code(exc)
            should_retry = (
                status_code in _TRANSIENT_PROVIDER_CODES
                and attempt_number < max_attempts
            )
            if not should_retry:
                raise

            # Exponential delay with +/-20% jitter reduces synchronized retries
            # when several API workers encounter the same capacity spike.
            delay = min(
                base_delay * (2 ** (attempt_number - 1)) * (0.8 + 0.4 * random_value()),
                8.0,
            )
            logger.warning(
                "%s returned transient status %s; retrying attempt %d/%d in %.2fs",
                provider_name,
                status_code,
                attempt_number + 1,
                max_attempts,
                delay,
            )
            sleep(delay)

    raise RuntimeError("AI retry loop ended unexpectedly")
