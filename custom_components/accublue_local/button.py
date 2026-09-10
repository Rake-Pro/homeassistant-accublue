"""Buttons for the AccuBlue Local integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AccuBlueConfigEntry, AccuBlueCoordinator, AccuBlueEntity


@dataclass(frozen=True, kw_only=True)
class AccuBlueButtonDescription(ButtonEntityDescription):
    """A button that runs one coordinator command."""

    press_fn: Callable[[AccuBlueCoordinator], Awaitable[None]]


BUTTONS: tuple[AccuBlueButtonDescription, ...] = (
    AccuBlueButtonDescription(
        key="run_test",
        translation_key="run_test",
        press_fn=lambda coordinator: coordinator.async_run_test(),
    ),
    AccuBlueButtonDescription(
        key="fetch_pending",
        translation_key="fetch_pending",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda coordinator: coordinator.async_fetch_pending(),
    ),
    AccuBlueButtonDescription(
        key="clear_error",
        translation_key="clear_error",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda coordinator: coordinator.async_clear_error(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AccuBlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AccuBlue buttons."""
    coordinator = entry.runtime_data
    async_add_entities(AccuBlueButton(coordinator, description) for description in BUTTONS)


class AccuBlueButton(AccuBlueEntity, ButtonEntity):
    """A button that talks to the meter once."""

    entity_description: AccuBlueButtonDescription

    def __init__(
        self,
        coordinator: AccuBlueCoordinator,
        description: AccuBlueButtonDescription,
    ) -> None:
        """Initialise the button."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Run the command."""
        await self.entity_description.press_fn(self.coordinator)
