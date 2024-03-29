// pulse timer native module
// Copyright © 2020 by Thorsten von Eicken.

#define DYN_LOAD (0)  // 0->built statically into the firmware, 1->dynamically loaded module

#include <assert.h>
#include <string.h>
#if DYN_LOAD
#include "py/dynruntime.h"
#else
#include "py/nativeglue.h"
#endif
// ESP-IDF imports
#include <esp_err.h>
#include <driver/pcnt.h>

// from smallint.h
#define MP_SMALL_INT_POSITIVE_MASK ~(WORD_MSBIT_HIGH | (WORD_MSBIT_HIGH >> 1))

extern bool mp_sched_schedule(mp_obj_t function, mp_obj_t arg);
extern void mp_hal_wake_main_task_from_isr(void);

uint32_t mp_hal_ticks_us(void) {
    return esp_timer_get_time();
}

STATIC void pt_isr_handler(void *arg) {
    uint32_t now = esp_timer_get_time() & (MICROPY_PY_UTIME_TICKS_PERIOD - 1);
    mp_obj_t handler = arg;
    mp_sched_schedule(handler, MP_OBJ_NEW_SMALL_INT(now));
    mp_hal_wake_main_task_from_isr();
}

// set_time_handler replaces the handler registered with ESP-IDF by a different one that
// schedules a python function passing it the time in microseconds (same as time.ticks_us).
// It is used by first setting up the pin using a standard dummy python handler and then
// changing the handler, this ensures that all handlers are removed when the Pin is deallocated.
// Note that the handler does _not_ receive the Pin as an argument, so a different handler must be
// registered for each pin (this is a limitation of the soft IRQ scheduling).
STATIC mp_obj_t set_time_handler(mp_obj_t pin, mp_obj_t handler) {
        uint id = (uint)mp_obj_get_int(pin);
        esp_err_t err = gpio_isr_handler_add(id, pt_isr_handler, (void *)handler);
        const char* ret = esp_err_to_name(err);
        return ret ? mp_obj_new_str(ret, strlen(ret)) : mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_2(set_time_handler_obj, set_time_handler);


#if DYN_LOAD
mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
        MP_DYNRUNTIME_INIT_ENTRY
        mp_store_global(MP_QSTR_set_time_handler, MP_OBJ_FROM_PTR(&espidf_set_time_handler_obj));
        MP_DYNRUNTIME_INIT_EXIT
}
#else
STATIC const mp_rom_map_elem_t pulsetimer_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_pulsetimeru8g2_draw) },
    { MP_ROM_QSTR(MP_QSTR_set_time_handler), MP_ROM_PTR(&set_time_handler_obj) },
};

STATIC MP_DEFINE_CONST_DICT(pulsetimer_module_globals, pulsetimer_module_globals_table);

const mp_obj_module_t mp_module_pulsetimer = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&pulsetimer_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_pulsetimer, mp_module_pulsetimer, MODULE_PULSETIMER_ENABLED);
#endif
