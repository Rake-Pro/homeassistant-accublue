"""Sanitizer select for the AccuBlue Local integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_SANITIZER
from .coordinator import AccuBlueConfigEntry, AccuBlueCoordinator, AccuBlueEntity
from .protocol import SANITIZERS

SANITIZER = SelectEntityDescription(
    key=CONF_SANITIZER,
    translation_key=CONF_SANITIZER,
    options=SANITIZERS,
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AccuBlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AccuBlue select."""
    async_add_entities([AccuBlueSanitizerSelect(entry.runtime_data, SANITIZER)])


class AccuBlueSanitizerSelect(AccuBlueEntity, SelectEntity):
    """Mirrors the sanitizer option and recomputes the last results."""

    def __init__(
        self,
        coordinator: AccuBlueCoordinator,
        description: SelectEntityDescription,
    ) -> None:
        """Initialise the select."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def current_option(self) -> str:
        """Return the configured sanitizer."""
        return self.coordinator.sanitizer

    async def async_select_option(self, option: str) -> None:
        """Persist the sanitizer."""
        await self.coordinator.async_set_sanitizer(option)
