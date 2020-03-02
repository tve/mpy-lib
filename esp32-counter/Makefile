# Location of top-level MicroPython directory
MPY_DIR = /home/src/esp32/micropython

# Location of C stub generator
GENSTUB = ../genstub/genstub.py

# Name of module
MOD = counter

# Source files (.c or .py)
SRC = modpcnt.c counter.py

# Architecture to build for (x86, x64, armv7m, xtensa, xtensawin)
ARCH = xtensawin
PORT = esp32

# Espressif ESP-IDF path
IDF_PATH := $(abspath $(MPY_DIR)/../esp-idf-micropython)
# Board to get correct ESP-IDF config
BOARD := GENERIC
# xtensa toolchain bin dir
PATH := $(HOME)/.espressif/tools/xtensa-esp32-elf/esp-2019r2-8.2.0/xtensa-esp32-elf/bin:$(PATH)

# Include to get the rules for compiling and linking the module
include $(MPY_DIR)/py/dynruntime.mk
include $(MPY_DIR)/ports/$(PORT)/dynruntime.mk

$(SRC): $(GENSTUB) #build/sdkconfig.h
	$(ECHO) "GEN $@"
	$(Q)$< <pcnt.in >$@
