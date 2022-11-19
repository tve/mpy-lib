# DS18x20 temperature sensor driver for MicroPython.
# MIT license; Copyright (c) 2016 Damien P. George

from micropython import const

_CONVERT = const(0x44)
_RD_SCRATCH = const(0xBE)
_WR_SCRATCH = const(0x4E)


# Note about parasitically powered DS18B20 sensors: these sensors need a strong pull-up when
# performing a conversion. This is achieved in this driver by switching the OW interface pin
# from the normally used open drain mode to totem-pole output. For a small number of sensors
# it is recommended to use a 180 Ohm series resistor on the output pin followed by a 2.2K-4.7K
# pull-up resistor. The purpose of the series resistor is to slow the slew rate and absorb
# reflections. This can work well with up to a handful of sensors and about 10m of wires.
# Beyond that a more sophisticated driver with slew rate control is needed (and using
# a DS2483 can avoid lots of headaches).


class DS18X20:
    def __init__(self, onewire):
        self.ow = onewire
        self.buf = bytearray(9)

    def __repr__(self):
        return "DS18X20(%r)" % self.ow

    def scan(self):
        pin = self.ow.pin
        pin.init(pin.OPEN_DRAIN, pin.PULL_UP)
        return [rom for rom in self.ow.scan() if rom[0] in (0x10, 0x22, 0x28)]

    def convert_temp(self):
        pin = self.ow.pin
        self.ow.reset()
        pin.init(pin.OUT, value=1)  # switch to strong drive to power conversion
        self.ow.writebyte(self.ow.SKIP_ROM)
        self.ow.writebyte(_CONVERT)

    def read_scratch(self, rom):
        pin = self.ow.pin
        pin.init(pin.OPEN_DRAIN, pin.PULL_UP)
        self.ow.select_rom(rom)
        self.ow.writebyte(_RD_SCRATCH)
        self.ow.readinto(self.buf)
        self.ow.check_crc8(self.buf)
        return self.buf

    def write_scratch(self, rom, buf):
        pin = self.ow.pin
        pin.init(pin.OPEN_DRAIN, pin.PULL_UP)
        self.ow.select_rom(rom)
        self.ow.writebyte(_WR_SCRATCH)
        self.ow.write(buf)

    # set_resolution sets the resolution for ds18b20 conversions to 9, 10, 11, or 12 bits
    def set_resolution(self, rom, bits):
        self.buf[0] = 0
        self.buf[1] = 0
        conf = (((bits - 9) & 3) << 5) | 0x1F
        self.buf[2] = conf
        self.write_scratch(rom, memoryview(self.buf[0:3]))
        check_buf = self.read_scratch(rom)
        if check_buf[2] != conf:
            raise ValueError("Config failed")

    def read_temp(self, rom):
        pin = self.ow.pin
        pin.init(pin.OPEN_DRAIN, pin.PULL_UP)
        buf = self.read_scratch(rom)
        if rom[0] == 0x10:
            # DS18S20
            if buf[1]:
                t = buf[0] >> 1 | 0x80
                t = -((~t + 1) & 0xFF)
            else:
                t = buf[0] >> 1
            return t - 0.25 + (buf[7] - buf[6]) / buf[7]
        else:
            # DS18B20A (0x28), DS1922 (0x22)
            t = buf[1] << 8 | buf[0]
            if t == 0x0550:
                raise ValueError("Invalid temperature")
            if t & 0x8000:  # sign bit set
                t = -((t ^ 0xFFFF) + 1)
            return t / 16
