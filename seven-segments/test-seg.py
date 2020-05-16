# show splash screen on display
import machine, time
from ssd1306 import SSD1306_I2C
import seg7

scl1, sda1 = 18, 4  # oled
scl1_pin = machine.Pin(scl1)
sda1_pin = machine.Pin(sda1)
display = SSD1306_I2C(128, 64, machine.I2C(scl=scl1_pin, sda=sda1_pin, freq=1000000))
display.fill(1)
display.fill_rect(10, 10, 108, 44, 0)
display.text("7-SEG test", 20, 20, 1)
display.show()
time.sleep_ms(1000)

while True:
    for i in range(256):
        i_str = "%x:%04.1fo" % (i&0xF, i/10)
        display.fill(0)
        #seg7.draw_number(display, i_str, 1, 10, 16, 48, 1, i % 3 + 1)
        seg7.draw_number(display, i_str, 1, 10, 12, 32, 1, i % 3 + 1)
        display.show()
        time.sleep_ms(500)
