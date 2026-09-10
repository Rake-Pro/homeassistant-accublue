"""Sensors for the AccuBlue Local integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfRatio,
    PERCENTAGE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AccuBlueConfigEntry, AccuBlueCoordinator, AccuBlueData, AccuBlueEntity
from .protocol import ERRORS

PPM = UnitOfRatio.PARTS_PER_MILLION
PPB = UnitOfRatio.PARTS_PER_BILLION

# key -> (unit, decimals shown by HA, device_class)
RESULT_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="free_chlorine", translation_key="free_chlorine",
        native_unit_of_measurement=PPM, state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="total_chlorine", translation_key="total_chlorine",
        native_unit_of_measurement=PPM, state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="combined_chlorine", translation_key="combined_chlorine",
        native_unit_of_measurement=PPM, state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="ph", translation_key="ph",
        device_class=SensorDeviceClass.PH, state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="alkalinity", translation_key="alkalinity",
        native_unit_of_measurement=PPM, state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="calcium_hardness", translation_key="calcium_hardness",
        native_unit_of_measurement=PPM, state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="cyanuric_acid", translation_key="cyanuric_acid",
        native_unit_of_measurement=PPM, state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="copper", translation_key="copper",
        native_unit_of_measurement=PPM, state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="iron", translation_key="iron",
        native_unit_of_measurement=PPM, state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="phosphate", translation_key="phosphate",
        native_unit_of_measurement=PPB, state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
)

# Only produced by one sanitizer each; created disabled unless that sanitizer is selected.
SANITIZER_SENSORS: dict[str, SensorEntityDescription] = {
    "salt": SensorEntityDescription(
        key="salt", translation_key="salt",
        native_unit_of_measurement=PPM, state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "bromine": SensorEntityDescription(
        key="bromine", translation_key="bromine",
        native_unit_of_measurement=PPM, state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
}


@dataclass(frozen=True, kw_only=True)
class AccuBlueStatusSensorDescription(SensorEntityDescription):
    """A sensor fed from the status frame instead of the results."""

    value_fn: Callable[[AccuBlueData], str | int | float | datetime | None]


STATUS_SENSORS: tuple[AccuBlueStatusSensorDescription, ...] = (
    AccuBlueStatusSensorDescription(
        key="last_test", translation_key="last_test",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.last_test,
    ),
    AccuBlueStatusSensorDescription(
        key="test_progress", translation_key="test_progress",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: (data.status or {}).get("progress"),
    ),
    AccuBlueStatusSensorDescription(
        key="test_counter", translation_key="test_counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (data.status or {}).get("test_counter"),
    ),
    AccuBlueStatusSensorDescription(
        key="last_error", translation_key="last_error",
        device_class=SensorDeviceClass.ENUM,
        options=list(ERRORS.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (data.status or {}).get("last_error"),
    ),
    AccuBlueStatusSensorDescription(
        key="firmware", translation_key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (data.status or {}).get("fw"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AccuBlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AccuBlue sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        AccuBlueResultSensor(coordinator, description) for description in RESULT_SENSORS
    ]
    for sanitizer, description in SANITIZER_SENSORS.items():
        entities.append(
            AccuBlueResultSensor(
                coordinator, description, enabled=coordinator.sanitizer == sanitizer
            )
        )
    entities.extend(
        AccuBlueStatusSensor(coordinator, description) for description in STATUS_SENSORS
    )
    async_add_entities(entities)


class AccuBlueResultSensor(AccuBlueEntity, SensorEntity):
    """One measured water factor. Unknown until the first test."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: AccuBlueCoordinator,
        description: SensorEntityDescription,
        enabled: bool = True,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_entity_registry_enabled_default = enabled

    @property
    def native_value(self) -> float | None:
        """Return the last computed value for this factor."""
        results = self.coordinator.data.results or {}
        return results.get(self.entity_description.key)


class AccuBlueStatusSensor(AccuBlueEntity, SensorEntity):
    """A value taken from the meter's status frame."""

    entity_description: AccuBlueStatusSensorDescription

    def __init__(
        self,
        coordinator: AccuBlueCoordinator,
        description: AccuBlueStatusSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the current status value."""
        return self.entity_description.value_fn(self.coordinator.data)
