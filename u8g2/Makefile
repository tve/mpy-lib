# Location of top-level MicroPython directory
MPY_DIR = /home/src/esp32/mpy-1.13/micropython

# Name of module
MOD = modu8g2

# Source files (.c or .py)
SRC = modu8g2.c

# Architecture to build for (x86, x64, armv7m, xtensa, xtensawin)
ARCH = xtensawin
PORT = esp32

# Espressif ESP-IDF path
IDF_PATH := $(abspath $(MPY_DIR)/../esp-idf)
# Board to get correct ESP-IDF config
BOARD := BLUE_SPIRAM_OTA
# xtensa toolchain bin dir
PATH := $(MPY_DIR)/tools/tools/xtensa-esp32-elf/esp-2019r2-8.2.0/xtensa-esp32-elf/bin:$(PATH)
SHELL := env PATH=$(PATH) /bin/bash

# Include to get the rules for compiling and linking the module
include $(MPY_DIR)/py/dynruntime.mk
