# Location of top-level MicroPython directory
MPY_DIR = /home/src/esp32/micropython

# Location of C stub generator
GENSTUB = ../genstub/genstub.py

# Name of module
MOD = modpcnt

# Source files (.c or .py)
SRC = modpcnt.c
SPEC = pcnt.in

# Architecture to build for (x86, x64, armv7m, xtensa, xtensawin)
ARCH = xtensawin
PORT = esp32

# Espressif ESP-IDF path
IDF_PATH := $(abspath $(MPY_DIR)/../esp-idf-micropython)
# Board to get correct ESP-IDF config
BOARD := GENERIC
# xtensa toolchain bin dir
PATH := $(HOME)/.espressif/tools/xtensa-esp32-elf/esp-2019r2-8.2.0/xtensa-esp32-elf/bin:$(PATH)
SHELL := env PATH=$(PATH) /bin/bash

# Include to get the rules for compiling and linking the module
include $(MPY_DIR)/py/dynruntime.mk
include $(MPY_DIR)/ports/$(PORT)/dynruntime.mk

$(MOD).mpy: | $(MPY_DIR)/ports/$(PORT)/port_fun.inc

$(SRC): $(GENSTUB) $(SPEC) build/sdkconfig.h
	$(ECHO) "GEN $@"
	$(Q)$< <$(SPEC) >$@
