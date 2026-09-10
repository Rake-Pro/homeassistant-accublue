"""Config flow for the AccuBlue Local integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.helpers import selector

from .const import CONF_ADDRESS, CONF_SANITIZER, DEFAULT_SANITIZER, DOMAIN, LOCAL_NAME_PREFIX
from .coordinator import AccuBlueConfigEntry
from .protocol import SANITIZERS

_SANITIZER_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=SANITIZERS,
        translation_key=CONF_SANITIZER,
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)


class AccuBlueConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle discovery and manual setup of an AccuBlue Home meter."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the flow."""
        self._discovered: dict[str, str] = {}
        self._address: str | None = None
        self._name: str | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a meter found by the bluetooth matcher."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._address = discovery_info.address
        self._name = discovery_info.name or discovery_info.address
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered meter."""
        assert self._address is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self._name or self._address,
                data={CONF_ADDRESS: self._address},
                options={CONF_SANITIZER: user_input.get(CONF_SANITIZER, DEFAULT_SANITIZER)},
            )
        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema(
                {vol.Required(CONF_SANITIZER, default=DEFAULT_SANITIZER): _SANITIZER_SELECTOR}
            ),
            description_placeholders={"name": self._name or self._address},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a meter out of the ones the Bluetooth stack can see."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered.get(address, address),
                data={CONF_ADDRESS: address},
                options={CONF_SANITIZER: user_input.get(CONF_SANITIZER, DEFAULT_SANITIZER)},
            )

        configured = self._async_current_ids()
        self._discovered = {
            info.address: info.name or info.address
            for info in async_discovered_service_info(self.hass, connectable=True)
            if (info.name or "").startswith(LOCAL_NAME_PREFIX) and info.address not in configured
        }
        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(self._discovered),
                    vol.Required(CONF_SANITIZER, default=DEFAULT_SANITIZER): _SANITIZER_SELECTOR,
                }
            ),
        )

    @staticmethod
    def async_get_options_flow(config_entry: AccuBlueConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return AccuBlueOptionsFlow()


class AccuBlueOptionsFlow(OptionsFlow):
    """Let the user change the sanitizer."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_SANITIZER, DEFAULT_SANITIZER)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required(CONF_SANITIZER, default=current): _SANITIZER_SELECTOR}
            ),
        )
