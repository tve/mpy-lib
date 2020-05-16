ESP32_SRC := /home/src/esp32
BOARD ?= GENERIC
MPY_DIR := $(ESP32_SRC)/micropython
IDF_PATH := $(ESP32_SRC)/esp-idf-micropython
PATH := $(IDF_PATH)/xtensa-esp32-elf/bin:$(PATH)

GENSTUB = ../genstub/genstub.py
MOD := modadccal
SPEC := adccal.in

SRC := modadccal.c
ARCH := xtensawin
PORT = esp32

include $(MPY_DIR)/py/dynruntime.mk
include $(MPY_DIR)/ports/$(PORT)/dynruntime.mk

$(MOD).mpy: | $(MPY_DIR)/ports/$(PORT)/port_fun.inc

$(SRC): $(GENSTUB) $(SPEC) build/sdkconfig.h
	$(ECHO) "GEN $@"
	$(Q)$< <$(SPEC) >$@
