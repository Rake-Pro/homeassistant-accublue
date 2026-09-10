# AccuBlue Local

Home Assistant custom integration for the Leslie's AccuBlue Home pool water tester (LaMotte Spin Touch OEM disc photometer). Local BLE only.

## What it is

- Talks to the meter directly over Bluetooth LE. No vendor app, no Leslie's account, no cloud call, no membership check.
- Results are computed on the Home Assistant host from the meter's raw well counts. The meter only ships absorbance counts; the numbers are produced here.
- One test = one connection. The integration connects, runs the command, disconnects. Nothing is polled.

## How it works

| Step | Detail |
|---|---|
| Discovery | Advertised local name `AccuBlueHome` + 6 hex, matched on the name prefix |
| Transport | GATT service `00001500-0000-1000-8001-bbbd00000500`, one central at a time |
| Command | Write to `1502`, always zero padded to 12 bytes |
| Status | Notify + read on `1503`, 39 bytes: progress, measuring bit, errors, firmware, serial, test counter |
| Test data | Notify on `1501` (set 0), read `1504` (set 1) and `1505` (set 2), 88 bytes each = 4 channels x 11 wells, uint16 LE |
| Math | Absorbance `-log10(well / blank)` per channel, then a cubic curve per factor from the Disk 203 tables |
| Duration | About 66 seconds per spin; the integration allows 120 seconds |

## Install

HACS custom repository:

| Step | Action |
|---|---|
| 1 | HACS > Integrations > three dot menu > Custom repositories |
| 2 | Repository `https://github.com/Rake-Pro/homeassistant-accublue`, category `Integration` |
| 3 | Install `AccuBlue Local` |
| 4 | Restart Home Assistant |

Manual:

| Step | Action |
|---|---|
| 1 | Copy `custom_components/accublue_local` into your `config/custom_components/` |
| 2 | Restart Home Assistant |

## Setup

- The meter is usually found on its own: Settings > Devices and services > a discovered `AccuBlueHome...` entry.
- Otherwise add it: Settings > Devices and services > Add integration > AccuBlue Local, then pick the meter from the list of AccuBlue advertisers currently in range.
- Pick the sanitizer during setup (`chlorine`, `salt`, `bromine`). It decides which factors the disc reports. It can be changed later in the integration options or with the Sanitizer select.
- Load a disc, close the lid, press the Run test button or call `accublue_local.run_test`.

## Entities

| Entity | Type | Unit | Notes |
|---|---|---|---|
| Free chlorine | sensor | ppm | |
| Total chlorine | sensor | ppm | clamped to at least free chlorine |
| Combined chlorine | sensor | ppm | total minus free |
| Bromine | sensor | ppm | bromine sanitizer only, disabled otherwise |
| pH | sensor | - | device class `ph`, clamped 6.3 to 8.7 |
| Total alkalinity | sensor | ppm | |
| Calcium hardness | sensor | ppm | capped at 900 |
| Cyanuric acid | sensor | ppm | floor of 5 |
| Copper | sensor | ppm | |
| Iron | sensor | ppm | |
| Salt | sensor | ppm | salt sanitizer only, disabled otherwise, capped at 9999 |
| Phosphate | sensor | ppb | |
| Last test | sensor | timestamp | when the last result was computed |
| Test progress | sensor | % | 0 to 97 while a disc spins |
| Test counter | sensor | - | diagnostic, the meter's lifetime test count |
| Last error | sensor | enum | diagnostic: none, lid_opened, speed_lock, motor_stall, byte_overflow |
| Firmware | sensor | - | diagnostic, from the status frame |
| Measuring | binary_sensor | - | device class `running` |
| Problem | binary_sensor | - | device class `problem`, on when the meter latched an error |
| Run test | button | - | spins a disc |
| Fetch pending test | button | - | pulls a result already sitting in the meter |
| Clear error | button | - | clears the latched hardware error |
| Sanitizer | select | - | chlorine / salt / bromine, persisted |

- Measurement sensors are unknown until the first test, then keep their last value. They are not cleared on restart.
- Entities stay available while the config entry is loaded. The meter is only reachable during a command, so there is no connectivity entity.

## Services

| Service | Fields | Notes |
|---|---|---|
| `accublue_local.run_test` | `device_id` (optional), `config_entry_id` (optional), `sanitizer` (optional) | `sanitizer` overrides the configured one for this run only. Targets are optional when only one meter is set up. |
| `accublue_local.calibrate` | `device_id` (optional), `config_entry_id` (optional) | Spin/rotation calibration (`05`). There is no photometric calibration on this meter. |

## Range

| Observation | Value |
|---|---|
| Home Assistant host Intel adapter, 30 cm from the meter | -75 dBm |
| Link drops at | -80 dBm and below |
| Office to meter | -81 to -91 dBm, unusable |

- The meter's radio is weak. An adapter on the Home Assistant host is only enough if the meter sits next to it.
- Recommended: an ESPHome Bluetooth proxy within a few metres of where the meter lives. The integration goes through proxies without any extra configuration.
- Only one central can be connected at a time. Close the Leslie's app before running a test.

## Errors

| Code | Meaning | Fix |
|---|---|---|
| 1 | Lid opened | Close the lid, then Clear error |
| 2 | Speed lock | Reseat the disc, then Clear error |
| 4 | Motor stall | Check the disc and the chamber, then Clear error |
| 8 | Byte overflow | Clear error and rerun |

## Credits

- Protocol recovered from the vendor app's LaMotte device library (`DotNetABHApi`), decompiled from `com.lesliespool.mobile`. No vendor code is included or redistributed here.
- The curve coefficients are the device's published Disk 203 reagent curves, reproduced so the same numbers can be computed locally.
- Reference client and raw capture: `IoT-Lab/devices/accublue-home`.
- Not affiliated with Leslie's or LaMotte.
