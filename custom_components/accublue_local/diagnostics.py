"""Diagnostics for the AccuBlue Local integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import AccuBlueConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AccuBlueConfigEntry
) -> dict[str, Any]:
    """Return the last status, the raw wells and the computed results."""
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": {
            "data": dict(entry.data),
            "options": dict(entry.options),
            "title": entry.title,
        },
        "sanitizer": coordinator.sanitizer,
        "last_test": data.last_test.isoformat() if data.last_test else None,
        "status": data.status,
        "wells": data.wells,
        "results": data.results,
    }
