# VAJRA F4

- MCU: STM32F405 (1 MB flash)
- INAV target: `VAJRA_F4` (the name it reports over MSP_BOARD_INFO; `match` in manifest.json)
- Bluetooth bridge: ESP32-C3 ("SpeedyBee-C3"), flashes the STM32 over BLE

## Releases

| Firmware | Version | Release | Notes |
|---|---|---|---|
| INAV | 9.0.1 | `vajra-f4-inav-9.0.1` | First release. Recommended. CRC 0x98059EBF, 586,552 bytes. |

Release names follow `vajra-f4-<firmware>-<version>`, e.g. `vajra-f4-inav-9.1.0`.
