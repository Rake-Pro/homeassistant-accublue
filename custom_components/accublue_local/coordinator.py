"""Coordinator for the AccuBlue Local integration.

The meter is connected to only while a command runs; there is no polling and no
update_interval. The coordinator keeps the last status and the last results and
pushes them out with async_set_updated_data.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from bleak.backends.device import BLEDevice
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import protocol
from .const import (
    CONF_ADDRESS,
    CONF_SANITIZER,
    CONNECT_TIMEOUT,
    DEFAULT_SANITIZER,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    STATUS_TIMEOUT,
    STORAGE_VERSION,
    TEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

AccuBlueConfigEntry = ConfigEntry["AccuBlueCoordinator"]


class AccuBlueError(HomeAssistantError):
    """Raised when the meter cannot be reached or refuses a command."""


@dataclass
class AccuBlueData:
    """Everything the entities render."""

    status: dict[str, Any] | None = None
    results: dict[str, float] | None = None
    wells: list[list[list[int]]] | None = None
    last_test: datetime | None = None
    sanitizer: str = DEFAULT_SANITIZER
    busy: bool = False

    def as_stored(self) -> dict[str, Any]:
        """Serialise the parts worth surviving a restart."""
        return {
            "status": self.status,
            "results": self.results,
            "wells": self.wells,
            "last_test": self.last_test.isoformat() if self.last_test else None,
            "sanitizer": self.sanitizer,
        }


class AccuBlueCoordinator(DataUpdateCoordinator[AccuBlueData]):
    """Owns the BLE session, the last known data and the persistent store."""

    config_entry: AccuBlueConfigEntry

    def __init__(self, hass: HomeAssistant, entry: AccuBlueConfigEntry) -> None:
        """Initialise the coordinator without any polling."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=None,
        )
        self.address: str = entry.data[CONF_ADDRESS]
        self.device_name: str = entry.title
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._lock = asyncio.Lock()
        self.data = AccuBlueData(sanitizer=entry.options.get(CONF_SANITIZER, DEFAULT_SANITIZER))

    async def _async_update_data(self) -> AccuBlueData:
        """Never scheduled; the data is pushed by the command handlers."""
        return self.data

    # ----- persistence -------------------------------------------------

    async def async_load_stored(self) -> None:
        """Restore the last results so sensors are not unknown after a restart."""
        stored = await self._store.async_load()
        if stored:
            last_test = stored.get("last_test")
            self.data = AccuBlueData(
                status=stored.get("status"),
                results=stored.get("results"),
                wells=stored.get("wells"),
                last_test=dt_util.parse_datetime(last_test) if last_test else None,
                sanitizer=self.sanitizer,
            )
        self.async_set_updated_data(self.data)

    async def _async_save(self) -> None:
        await self._store.async_save(self.data.as_stored())

    # ----- state -------------------------------------------------------

    @property
    def sanitizer(self) -> str:
        """Sanitizer chosen in the options."""
        return self.config_entry.options.get(CONF_SANITIZER, DEFAULT_SANITIZER)

    @property
    def device_info(self) -> DeviceInfo:
        """Device registry entry for the meter."""
        status = self.data.status or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self.address)},
            connections={(CONNECTION_BLUETOOTH, self.address)},
            name=self.device_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version=status.get("fw"),
            serial_number=status.get("serial"),
        )

    @callback
    def _publish(self) -> None:
        self.async_set_updated_data(self.data)

    @callback
    def _set_status(self, status: dict[str, Any]) -> None:
        self.data.status = status
        self._publish()

    # ----- commands ----------------------------------------------------

    async def async_read_status(self) -> None:
        """Connect, read the status characteristic, disconnect."""
        await self._session("status", self.sanitizer)

    async def async_run_test(self, sanitizer: str | None = None) -> None:
        """Spin a disc and compute the results."""
        await self._session("test", sanitizer or self.sanitizer)

    async def async_fetch_pending(self) -> None:
        """Pull a test that is already sitting in the meter."""
        await self._session("fetch", self.sanitizer)

    async def async_clear_error(self) -> None:
        """Clear the meter's latched hardware error."""
        await self._session("clear", self.sanitizer)

    async def async_calibrate(self) -> None:
        """Start the meter's spin calibration."""
        await self._session("calibrate", self.sanitizer)

    async def async_set_sanitizer(self, sanitizer: str) -> None:
        """Persist a new sanitizer and recompute the last results with it."""
        self.hass.config_entries.async_update_entry(
            self.config_entry, options={**self.config_entry.options, CONF_SANITIZER: sanitizer}
        )
        self.data.sanitizer = sanitizer
        if self.data.wells:
            self.data.results = protocol.calculate(self.data.wells, sanitizer)
            await self._async_save()
        self._publish()

    # ----- BLE session -------------------------------------------------

    async def _connect(self) -> BleakClientWithServiceCache:
        ble_device: BLEDevice | None = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise AccuBlueError(
                f"AccuBlue Home {self.address} is not in range of any adapter or Bluetooth proxy"
            )
        return await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            self.device_name,
            disconnected_callback=self._on_disconnect,
            timeout=CONNECT_TIMEOUT,
        )

    @callback
    def _on_disconnect(self, _client: BleakClientWithServiceCache) -> None:
        _LOGGER.debug("%s: disconnected", self.address)

    async def _session(self, action: str, sanitizer: str) -> None:
        """Run one command against the meter and disconnect again."""
        if self._lock.locked():
            raise AccuBlueError("another AccuBlue command is already running")
        async with self._lock:
            self.data.busy = True
            self._publish()
            try:
                client = await self._connect()
                try:
                    await self._run(client, action, sanitizer)
                finally:
                    await client.disconnect()
            finally:
                self.data.busy = False
                self._publish()

    async def _run(self, client: BleakClientWithServiceCache, action: str, sanitizer: str) -> None:
        status_q: asyncio.Queue[bytes] = asyncio.Queue()
        data_q: asyncio.Queue[bytes] = asyncio.Queue()

        @callback
        def _on_status(_char: Any, payload: bytearray) -> None:
            raw = bytes(payload)
            _LOGGER.debug("%s: status notify %s", self.address, raw.hex())
            status_q.put_nowait(raw)
            self._set_status(protocol.parse_status(raw))

        @callback
        def _on_data(_char: Any, payload: bytearray) -> None:
            raw = bytes(payload)
            _LOGGER.debug("%s: set 0 notify %s", self.address, raw.hex())
            data_q.put_nowait(raw)

        await client.start_notify(protocol.STATUS, _on_status)
        if action in ("test", "fetch"):
            await client.start_notify(protocol.TEST_DATA0, _on_data)

        raw_status = bytes(await client.read_gatt_char(protocol.STATUS))
        _LOGGER.debug("%s: status read %s", self.address, raw_status.hex())
        status = protocol.parse_status(raw_status)
        self._set_status(status)

        if action == "status":
            return

        if action == "clear":
            code = protocol.ERROR_CODES.get(status["last_error"], 0)
            await self._write(client, protocol.cmd(protocol.CMD_CLEAR_ERROR, code))
            return

        if action == "calibrate":
            await self._write(client, protocol.cmd(protocol.CMD_CALIBRATE))
            return

        if status["error"] != "none":
            raise AccuBlueError(
                f"meter reports hardware error {status['error']}; clear it first"
            )

        if action == "test":
            await self._write(client, protocol.cmd(protocol.CMD_RUN_TEST))
        else:
            if not status["pending_test_data"]:
                raise AccuBlueError("no pending test data in the meter")
            await self._write(client, protocol.cmd(protocol.CMD_FETCH_PENDING))

        async with asyncio.timeout(TEST_TIMEOUT):
            await self._await_results(client, data_q, status_q, action, sanitizer)

    async def _write(self, client: BleakClientWithServiceCache, payload: bytes) -> None:
        _LOGGER.debug("%s: write cmd %s", self.address, payload.hex())
        await client.write_gatt_char(protocol.CMD, payload, response=True)

    async def _await_results(
        self,
        client: BleakClientWithServiceCache,
        data_q: asyncio.Queue[bytes],
        status_q: asyncio.Queue[bytes],
        action: str,
        sanitizer: str,
    ) -> None:
        while data_q.empty():
            try:
                raw = await asyncio.wait_for(status_q.get(), STATUS_TIMEOUT)
            except TimeoutError:
                if not data_q.empty():
                    break
                raise AccuBlueError("timed out waiting for the meter") from None
            status = protocol.parse_status(raw)
            if status["error"] != "none":
                raise AccuBlueError(f"hardware error during test: {status['error']}")
            # The meter can park the result instead of notifying it; ask for it.
            if (
                action == "test"
                and status["pending_test_data"]
                and not status["measuring"]
                and data_q.empty()
            ):
                await self._write(client, protocol.cmd(protocol.CMD_FETCH_PENDING))

        set0 = await data_q.get()
        set1 = bytes(await client.read_gatt_char(protocol.TEST_DATA1))
        set2 = bytes(await client.read_gatt_char(protocol.TEST_DATA2))
        _LOGGER.debug("%s: set 1 %s", self.address, set1.hex())
        _LOGGER.debug("%s: set 2 %s", self.address, set2.hex())

        wells = [protocol.parse_wells(set0), protocol.parse_wells(set1), protocol.parse_wells(set2)]
        self.data.wells = wells
        self.data.sanitizer = sanitizer
        self.data.results = protocol.calculate(wells, sanitizer)
        self.data.last_test = dt_util.utcnow()
        _LOGGER.debug("%s: results %s", self.address, self.data.results)
        await self._async_save()
        self._publish()


class AccuBlueEntity(CoordinatorEntity[AccuBlueCoordinator]):
    """Base entity: one device, always available while the entry is loaded."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AccuBlueCoordinator, key: str) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.address}_{key}"
        self._attr_translation_key = key

    @property
    def device_info(self) -> DeviceInfo:
        """Return the meter's device entry."""
        return self.coordinator.device_info

    @property
    def available(self) -> bool:
        """Stay available; results simply keep their last value."""
        return True
