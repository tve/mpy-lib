import time, machine

out_pin = 21
in_pin = 22
print("Testing pulsetimer, outputting on pin %d and reading pulsetimer on pin %d", out_pin, in_pin)

print("Loading pulsetimer module")
time.sleep_ms(100)
import pulsetimer

print("Instantiating output pin")
out = machine.Pin(out_pin, machine.Pin.OUT, value=0)

print("Setting up pulsetimer")
pt_pin = machine.Pin(in_pin, machine.Pin.IN)


def dummy(p):
    pass


q = []


def pulse(t):
    q.append(t)


pt_pin.irq(dummy, machine.Pin.IRQ_RISING)
pulsetimer.set_time_handler(in_pin, pulse)


if True:
    print("Testing positive edge")
    assert len(q) == 0
    out(1)
    time.sleep_ms(100)
    print(q)
    assert len(q) == 1

    print("Testing negative edge")
    out(0)
    time.sleep_ms(100)
    assert len(q) == 1

    print("Testing 10 pulses")
    for i in range(10):
        out(1)
        out(0)
        time.sleep_ms(20)
    time.sleep_ms(100)
    print([time.ticks_diff(q[i], q[i - 1]) for i in range(1, len(q))])
    assert len(q) == 11


print("DONE")
