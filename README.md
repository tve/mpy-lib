mpy-lib -- MicroPython libraries
================================

This repository contains a number of python libraries designed to work in Micropython.
Most of the libraries are tested with the Esp32 but a number should work with any port of
Micropython.
If not otherwise mentioned, all libraries use the MIT license (same as Micropython itself),

Quick index:
- ade7816: unfinished driver for ADE7816 Energy Monitoring IC
- ble-gattc: object-oriented asyncio-ready interface to a BLE GATT device/sensor
- button: simple classes to debounce a physical button with asyncio
- esp32-adccal: native code module to use the ESP-IDF ADC calibration functions
- esp32-counter: native code module to use the esp32's pulse counter hardware
- esp32-pulsetimer: native code module to get Pin IRQ callbacks with a timestamp
- genstub: generate stubs for native code modules
- material-gui: simple graphical user interface using material design color schemes
- seven-segments: write large numbers to a framebuffer using a seven segment retro look
- sntp: simple network time protocol implementation to synchronize the esp32 time
- sysinfo: small module for mqboard to periodically send system info via MQTT
- u8g2: pure python implementation of u8g2 font rendering

© 2020 by Thorsten von Eicken. MIT License.
