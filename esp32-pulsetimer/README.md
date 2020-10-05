ESP32 Pulse Timer
=================

This module exposes a simple function `set_time_handler` that changes the hard interrupt handler
on a gpio pin to one that calls a python function ("soft IRQ handler") with the time of the
interrupt instead of the Pin object that is passed when using `machine.Pin.isr` callback.
This enables simple timing of (relatively infrequent) pulse edges.

Example:
```
def dummy(p): pass # dummy handler for first IRQ registration
q = [] # queue to accumulate pulse times
def pulse(t): q.append(t)  # pulse IRQ handler, receives time and queues it
pt_pin = machine.Pin(in_pin, machine.Pin.IN)  # enable pin as input
pt_pin.irq(dummy, machine.Pin.IRQ_RISING)  # set dummy IRQ handler to activate IRQ
pulsetimer.set_time_handler(in_pin, pulse)  # change IRQ handler
```

This implementation relies on having a soft-IRQ queue in MicroPython and ultimately in being able to
run the python handlers faster than the interrupts are coming in. An better imlpementation might be
to have a circular queue of times in C and provide a way to retrieve that from python.
