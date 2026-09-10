# Changelog

## 0.1.0

- First release.
- Local BLE control of the Leslie's AccuBlue Home (LaMotte Spin Touch OEM) disc photometer. No vendor app, no cloud, no account.
- Bluetooth discovery config flow plus a manual picker over adapters and ESPHome Bluetooth proxies.
- Results computed on the Home Assistant host from the meter's raw well counts using the Disk 203 curves.
- Sensors: free chlorine, total chlorine, combined chlorine, pH, total alkalinity, calcium hardness, cyanuric acid, copper, iron, phosphate, plus salt and bromine for those sanitizers.
- Diagnostic sensors: last test, test progress, test counter, last error, firmware.
- Binary sensors: measuring, problem.
- Buttons: run test, fetch pending test, clear error. Select: sanitizer.
- Services: `accublue_local.run_test`, `accublue_local.calibrate`.
- Results, status and timestamp persist across restarts.
- Diagnostics download with the last status frame, the raw wells and the computed results.
