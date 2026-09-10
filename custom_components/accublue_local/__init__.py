"""The AccuBlue Local integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DEVICE_ID,
    ATTR_SANITIZER,
    DOMAIN,
    PLATFORMS,
    SERVICE_CALIBRATE,
    SERVICE_RUN_TEST,
)
from .coordinator import AccuBlueConfigEntry, AccuBlueCoordinator, AccuBlueError
from .protocol import SANITIZERS

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_TARGET_SCHEMA = {
    vol.Optional(ATTR_DEVICE_ID): cv.string,
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
}
SERVICE_RUN_TEST_SCHEMA = vol.Schema(
    {**_TARGET_SCHEMA, vol.Optional(ATTR_SANITIZER): vol.In(SANITIZERS)}
)
SERVICE_CALIBRATE_SCHEMA = vol.Schema(_TARGET_SCHEMA)


def _resolve(hass: HomeAssistant, call: ServiceCall) -> AccuBlueCoordinator:
    """Find the coordinator a service call is aimed at."""
    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
        and getattr(entry, "runtime_data", None) is not None
    ]

    if entry_id := call.data.get(ATTR_CONFIG_ENTRY_ID):
        for entry in entries:
            if entry.entry_id == entry_id:
                return entry.runtime_data
        raise AccuBlueError(f"config entry {entry_id} is not a loaded AccuBlue entry")

    if device_id := call.data.get(ATTR_DEVICE_ID):
        device = dr.async_get(hass).async_get(device_id)
        if device is None:
            raise AccuBlueError(f"unknown device {device_id}")
        for entry in entries:
            if entry.entry_id in device.config_entries:
                return entry.runtime_data
        raise AccuBlueError(f"device {device_id} does not belong to an AccuBlue entry")

    if len(entries) == 1:
        return entries[0].runtime_data
    raise AccuBlueError("more than one AccuBlue meter is set up; pass device_id")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration level services once."""

    async def handle_run_test(call: ServiceCall) -> None:
        coordinator = _resolve(hass, call)
        await coordinator.async_run_test(call.data.get(ATTR_SANITIZER))

    async def handle_calibrate(call: ServiceCall) -> None:
        coordinator = _resolve(hass, call)
        await coordinator.async_calibrate()

    hass.services.async_register(
        DOMAIN, SERVICE_RUN_TEST, handle_run_test, schema=SERVICE_RUN_TEST_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CALIBRATE, handle_calibrate, schema=SERVICE_CALIBRATE_SCHEMA
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AccuBlueConfigEntry) -> bool:
    """Set up AccuBlue Local from a config entry."""
    coordinator = AccuBlueCoordinator(hass, entry)
    await coordinator.async_load_stored()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: AccuBlueConfigEntry) -> None:
    """Reload when the options change so the sanitizer specific entities follow."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AccuBlueConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
