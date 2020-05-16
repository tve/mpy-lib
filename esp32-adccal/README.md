ESP32 ADC Calibration module for MicroPython
============================================

This module provides access to the ESP32 Analog to Digital Converter (ADC) calibration.
It is a dynamically loadable native module that calls the ESP-IDF's ADC calibration functions
and it works in conjunction with the standard `machine.ADC` module.

From a practical standpoint most ESP32's in use today have a factory calibration of the reference
voltage burned into eFuse. This means that the corection performed by this module takes that
into account. To obtain higher accuracy the use must perform a two-point calibration at 150mV and
850mV and burn the result into a eFuse. Agin, the correction performed by this module takes a
two-point calibration into account, however, this module does not provide a way to
perform the calibration and eFuse burning itself.

Constructor
-----------

### `adccal.ADCCal(width=machine.ADC.WIDTH_12BIT, atten=machine.ADC.ATTN_11DB, vref=1100)`

Initialize the calibration table for the given attenuation, conversion width, and
default internal reference voltage (in millivolts). Internally calls the ESP-IDF
`esp_adc_cal_characterize` function, please see the ESP-IDF docs for more details.

Typically the eFuse Vref calibration was performed and burned-in at the factory.
To get a two-point calibration this must be performed explicitly (not yet supported in this module).

This function always sets up calibration for ADC1 given that ADC2 is not really usable.

Methods
-------

### `ADCCal.correct(raw_reading)`

Given a raw reading (made using `machine.ADC.read` _not_ `machine.ADC.read_u16`) returns the
corrected reading in millivolts. Internally uses the ESP-IDF's `esp_adc_cal_raw_to_voltage`
function.

### `ADCCal.method()`

Returns the calibration method being used:
 - 0=default vref provided (`ESP_ADC_CAL_VAL_DEFAULT_VREF`)
 - 1=eFuse Vref (`ESP_ADC_CAL_VAL_EFUSE_VREF`)
 - 2=two-point calibration (`ESP_ADC_CAL_VAL_EFUSE_TP`)
