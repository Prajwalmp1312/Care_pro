"""Deterministic helpers for comparing structured medical report metrics."""

from __future__ import annotations

import re
from typing import Any


_MISSING_TEXT = {"", "-", "n/a", "na", "none", "null", "[]", "{}"}


def metric_value_is_present(value: Any) -> bool:
    """Return whether a stored metric contains an actual report value."""
    if value is None:
        return False
    if isinstance(value, dict):
        if "value" in value:
            return metric_value_is_present(value.get("value"))
        return any(metric_value_is_present(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(metric_value_is_present(item) for item in value)
    if isinstance(value, str):
        return value.strip().lower() not in _MISSING_TEXT
    return True


def normalize_metric_value(value: Any) -> float | None:
    """Extract one comparable number without treating composite values as scalars."""
    if isinstance(value, dict):
        value = value.get("value")
    if isinstance(value, (list, tuple, set)):
        populated = [item for item in value if metric_value_is_present(item)]
        if len(populated) != 1:
            return None
        value = populated[0]
        if isinstance(value, dict):
            value = value.get("value")
        elif isinstance(value, (list, tuple, set)):
            return None
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    value_text = str(value).strip()
    if re.search(r"\d\s*/\s*\d", value_text):
        return None
    match = re.match(r"^[<>≤≥~]?\s*(-?\d+(?:\.\d+)?)", value_text)
    return float(match.group(1)) if match else None


def format_metric_value(value: Any) -> str | None:
    """Convert legacy lists and newer value/unit objects into display-safe text."""
    if not metric_value_is_present(value):
        return None
    if isinstance(value, dict):
        if "value" in value:
            displayed = format_metric_value(value.get("value"))
            unit = str(value.get("unit") or "").strip()
            return " ".join(part for part in (displayed, unit) if part)
        parts = [
            f"{key}: {format_metric_value(item)}"
            for key, item in value.items()
            if metric_value_is_present(item)
        ]
        return "; ".join(parts) or None
    if isinstance(value, (list, tuple, set)):
        populated = [item for item in value if metric_value_is_present(item)]
        if (
            isinstance(value, tuple)
            and len(populated) == 2
            and all(normalize_metric_value(item) is not None for item in populated)
        ):
            return "/".join(str(item).strip() for item in populated)
        parts = [format_metric_value(item) for item in populated]
        return ", ".join(part for part in parts if part) or None
    return str(value).strip()


def metric_unit(value: Any) -> str | None:
    if isinstance(value, dict):
        unit = str(value.get("unit") or "").strip()
        if unit:
            return unit
        return metric_unit(value.get("value"))
    if isinstance(value, (list, tuple, set)):
        populated = [item for item in value if metric_value_is_present(item)]
        return metric_unit(populated[0]) if len(populated) == 1 else None
    if not isinstance(value, str) or re.search(r"\d\s*/\s*\d", value):
        return None
    match = re.match(
        r"^[<>≤≥~]?\s*-?\d+(?:\.\d+)?\s*([^\d\s].*?)\s*$",
        value,
    )
    return match.group(1).strip() if match and match.group(1).strip() else None


def compare_metrics(first_metrics: dict | None, second_metrics: dict | None) -> list[dict]:
    """Compare only the metric keys that contain data in either selected report."""
    first_metrics = first_metrics if isinstance(first_metrics, dict) else {}
    second_metrics = second_metrics if isinstance(second_metrics, dict) else {}
    all_keys = sorted(
        set(first_metrics) | set(second_metrics),
        key=lambda item: str(item).lower(),
    )
    comparison = []

    for key in all_keys:
        old_raw = first_metrics.get(key)
        new_raw = second_metrics.get(key)
        old_present = metric_value_is_present(old_raw)
        new_present = metric_value_is_present(new_raw)
        if not old_present and not new_present:
            continue

        old_value = format_metric_value(old_raw) if old_present else None
        new_value = format_metric_value(new_raw) if new_present else None
        old_number = normalize_metric_value(old_raw) if old_present else None
        new_number = normalize_metric_value(new_raw) if new_present else None
        old_unit = metric_unit(old_raw) if old_present else None
        new_unit = metric_unit(new_raw) if new_present else None
        units_match = (
            (not old_unit and not new_unit)
            or (
                old_unit is not None
                and new_unit is not None
                and old_unit.casefold() == new_unit.casefold()
            )
        )

        difference = None
        if not old_present:
            status = "new"
        elif not new_present:
            status = "removed"
        elif old_number is not None and new_number is not None and units_match:
            difference = round(new_number - old_number, 2)
            status = (
                "increased" if difference > 0
                else "decreased" if difference < 0
                else "unchanged"
            )
        elif (old_value or "").casefold() != (new_value or "").casefold():
            status = "changed"
        else:
            status = "unchanged"

        comparison.append(
            {
                "metric": str(key),
                "first_value": old_value,
                "second_value": new_value,
                "difference": difference,
                "unit": old_unit if old_unit and units_match else new_unit if units_match else None,
                "status": status,
            }
        )

    return comparison
