from modadccal import *
from machine import ADC


class ADCCal:
    def __init__(self, width=ADC.WIDTH_10BIT, atten=ADC.ATTN_11DB, vref=1100):
        self._cal = bytearray(4 * 8)
        self._cal_method = esp_adc_cal_characterize(1, atten, width, vref, self._cal)

    def method(self):
        return self._cal_method

    def correct(self, raw):
        return esp_adc_cal_raw_to_voltage(raw, self._cal)
