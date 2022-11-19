# simple test app to repeatedly scan the bus and blink an LED for troubleshooting purposes
# Copyright © 2022 by Thorsten von Eicken.

from machine import Pin
from onewire import OneWire
import time

ow = OneWire(Pin(4))
led = Pin(2, Pin.OUT)

while True:
    try:
        ow.reset()
        led.value(0)
        devs = ow.scan()
        print("Found %d devices" % len(devs))
        for _ in range(len(devs)):
            led(1)
            time.sleep_ms(200)
            led(0)
            time.sleep_ms(200)

    except Exception as e:
        print("OneWire", e)
        led.value(1)
    time.sleep(2)
