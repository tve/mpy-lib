import time, machine

out_pin = 21
in_pin = 22
print("Testing counter, outputting on pin %d and reading counter on pin %d", out_pin, in_pin)

print("Loading counter module")
time.sleep_ms(100)
import counter

print("Instantiating output pin")
out = machine.Pin(out_pin, machine.Pin.OUT, value=0)

print("Instantiating up counter")
ctr_pin = machine.Pin(in_pin, machine.Pin.IN)
ctr = counter.Counter(0, in_pin)

if True:
    print("Testing positive edge")
    assert ctr.value() == 0, ctr.value()
    out(1)
    assert ctr.value() == 1, ctr.value()

    print("Testing negative edge")
    out(0)
    assert ctr.value() == 1, ctr.value()

    print("Testing 100 pulses")
    for i in range(100):
        out(1)
        out(0)
    assert ctr.value() == 101, ctr.value()

if True:
    print("Testing anemometer")
    from wind import Anemo

    import logging
    logging.basicConfig(logging.DEBUG)
    logging.info("Log test")

    # configure pin with pull-up
    anemo = Anemo(ctr, 1)  # 2.5 mph per Hz
    ctr.value(0)
    anemo.read()
    print("Ctr is %d" % ctr.value())
    now = time.ticks_ms()
    for i in range(100):
        out(1)
        out(0)
    time.sleep_ms(4000-time.ticks_diff(time.ticks_ms(), now))
    anemo.read()
    print("Ctr is %d" % ctr.value())



print("DONE")
