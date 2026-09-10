"""Binary sensors for the AccuBlue Local integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AccuBlueConfigEntry, AccuBlueCoordinator, AccuBlueEntity

MEASURING = BinarySensorEntityDescription(
    key="measuring",
    translation_key="measuring",
    device_class=BinarySensorDeviceClass.RUNNING,
)
PROBLEM = BinarySensorEntityDescription(
    key="problem",
    translation_key="problem",
    device_class=BinarySensorDeviceClass.PROBLEM,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AccuBlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AccuBlue binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            AccuBlueMeasuring(coordinator, MEASURING),
            AccuBlueProblem(coordinator, PROBLEM),
        ]
    )


class AccuBlueBinarySensor(AccuBlueEntity, BinarySensorEntity):
    """Base binary sensor."""

    def __init__(
        self,
        coordinator: AccuBlueCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description


class AccuBlueMeasuring(AccuBlueBinarySensor):
    """True while the disc is spinning."""

    @property
    def is_on(self) -> bool | None:
        """Return whether a test is running."""
        status = self.coordinator.data.status
        if status is None:
            return None
        return bool(status.get("measuring")) or self.coordinator.data.busy


class AccuBlueProblem(AccuBlueBinarySensor):
    """True while the meter reports a hardware error."""

    @property
    def is_on(self) -> bool | None:
        """Return whether the meter latched an error."""
        status = self.coordinator.data.status
        if status is None:
            return None
        return status.get("error") != "none"
