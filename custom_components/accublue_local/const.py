"""Constants for the AccuBlue Local integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "accublue_local"
MANUFACTURER = "Leslie's / LaMotte"
MODEL = "AccuBlue Home"
LOCAL_NAME_PREFIX = "AccuBlueHome"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
]

CONF_ADDRESS = "address"
CONF_SANITIZER = "sanitizer"
DEFAULT_SANITIZER = "chlorine"

STORAGE_VERSION = 1

# The meter is only connected to while a command runs. Nothing polls it.
CONNECT_TIMEOUT = 30.0   # seconds to establish the GATT link
TEST_TIMEOUT = 120.0     # whole run-test / fetch sequence; a spin takes about 66 s
STATUS_TIMEOUT = 20.0    # gap between two status notifications before giving up

SERVICE_RUN_TEST = "run_test"
SERVICE_CALIBRATE = "calibrate"

ATTR_DEVICE_ID = "device_id"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_SANITIZER = "sanitizer"
