ADE7816 Energy Metering IC Driver
=================================

This driver interfaces to the ADE7816 using I2C. A minimal configuration is:

| Signal     | GPIO    | Function |
| ---------- | ------- | -------- |
| SDA (MOSI) | io18    | I2C interface |
| SCK (SCLK) | io19    | I2C interface |
| ~IRQ1      | io17    | rstdone       |
| ~SS (CS)   | pup     | select I2C    |

