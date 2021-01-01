import time
from machine import Pin


# ADE7816 is a minimal driver for the ADE7816 6-Ch Energy Monitoring IC.
# Applications should instantiate ADE7816_I2C.
class ADE7816:
    # registers

    # The constructor waits for the device to be ready (indicated by irq1 being high) and
    # reads the checksum register to verify against the expected value.
    def __init__(self, irq1):
        # wait for chip to be ready
        irq1.init(mode=Pin.IN, pull=Pin.PULL_UP)
        while irq1():
            time.sleep_ms(50)

        # verify the register checksum as a way to validate the right chip is connected
        # TODO: this will fail if the device has already been modified, should reall compute the
        # checksum from the actual registers.
        cksum = self.read32(0xE51F)
        if cksum != 0x33666787:
            raise ValueError("Bad ADE7816 checksum: 0x%x" % cksum)


# ADE7816 is a minimal I2C driver for the ADE7816 6-Ch Energy Monitoring IC.
#
# Driver notes:
# - The ADE uses 16-bit register addresses, these are passed as "memory address" using
#   self.i2c.xxx_mem which sends the address in big-endian format, which the device expects.
class ADE7816_I2C(ADE7816):
    def __init__(self, i2c, irq1, addr=0x38):
        self.i2c = i2c
        self.addr = addr
        super().__init__(irq1)
        self.write8(0xEC01, 0x02)  # lock to I2C port in config2 register

    # read an 8-bit register, internal method
    def read8(self, reg):
        return self.i2c.readfrom_mem(self.addr, reg, 1, addrsize=16)[0]

    # read a 16-bit register, internal method
    def read16(self, reg):
        v = self.i2c.readfrom_mem(self.addr, reg, 2, addrsize=16)
        return v[0] << 8 | v[1]

    # read a 32-bit register, internal method
    def read32(self, reg):
        v = self.i2c.readfrom_mem(self.addr, reg, 4, addrsize=16)
        return v[0] << 24 | v[1] << 16 | v[2] << 8 | v[3]

    # write an 8-bit register, internal method
    def write8(self, reg, v):
        self.i2c.writeto_mem(self.addr, reg, bytes((v,)), addrsize=16)

    # write a 16-bit register, internal method
    def write16(self, reg, v):
        self.i2c.writeto_mem(self.addr, reg, bytes((v >> 8, v)), addrsize=16)


if __name__ == "__main__":
    from machine import I2C

    i2c = I2C(1, scl=Pin(18), sda=Pin(19))
    ade = ADE7816_I2C(i2c, Pin(17))
