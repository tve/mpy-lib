#include <assert.h>
#include <string.h>
#include "py/dynruntime.h"
// ESP-IDF imports
#include <esp_err.h>
#include <driver/pcnt.h>

STATIC mp_obj_t espidf_esp_err_to_name(mp_obj_t arg0) {
	// convert arg0
	uint val0 = (uint)mp_obj_get_int(arg0);
	// call
	const char* ret = esp_err_to_name(val0);
	return mp_obj_new_str(ret, strlen(ret));
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(espidf_esp_err_to_name_obj, espidf_esp_err_to_name);

STATIC mp_obj_t espidf_pcnt_unit_config(mp_obj_t arg0) {
	// convert arg0
	mp_buffer_info_t val0_buf;
	mp_get_buffer_raise(arg0, &val0_buf, MP_BUFFER_RW);
	void *val0 = (void *)(val0_buf.buf);
	// call
	const uint ret = pcnt_unit_config(val0);
	return mp_obj_new_int(ret);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(espidf_pcnt_unit_config_obj, espidf_pcnt_unit_config);

STATIC mp_obj_t espidf_pcnt_get_counter_value(mp_obj_t arg0, mp_obj_t arg1) {
	// convert arg0
	uint val0 = (uint)mp_obj_get_int(arg0);
	// convert arg1
	mp_buffer_info_t val1_buf;
	mp_get_buffer_raise(arg1, &val1_buf, MP_BUFFER_RW);
	void *val1 = (void *)(val1_buf.buf);
	// call
	const uint ret = pcnt_get_counter_value(val0, val1);
	return mp_obj_new_int(ret);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_2(espidf_pcnt_get_counter_value_obj, espidf_pcnt_get_counter_value);

STATIC mp_obj_t espidf_pcnt_counter_pause(mp_obj_t arg0) {
	// convert arg0
	uint val0 = (uint)mp_obj_get_int(arg0);
	// call
	const uint ret = pcnt_counter_pause(val0);
	return mp_obj_new_int(ret);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(espidf_pcnt_counter_pause_obj, espidf_pcnt_counter_pause);

STATIC mp_obj_t espidf_pcnt_counter_resume(mp_obj_t arg0) {
	// convert arg0
	uint val0 = (uint)mp_obj_get_int(arg0);
	// call
	const uint ret = pcnt_counter_resume(val0);
	return mp_obj_new_int(ret);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(espidf_pcnt_counter_resume_obj, espidf_pcnt_counter_resume);

STATIC mp_obj_t espidf_pcnt_counter_clear(mp_obj_t arg0) {
	// convert arg0
	uint val0 = (uint)mp_obj_get_int(arg0);
	// call
	const uint ret = pcnt_counter_clear(val0);
	return mp_obj_new_int(ret);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(espidf_pcnt_counter_clear_obj, espidf_pcnt_counter_clear);

STATIC mp_obj_t espidf_pcnt_intr_disable(mp_obj_t arg0) {
	// convert arg0
	uint val0 = (uint)mp_obj_get_int(arg0);
	// call
	const uint ret = pcnt_intr_disable(val0);
	return mp_obj_new_int(ret);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(espidf_pcnt_intr_disable_obj, espidf_pcnt_intr_disable);

mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
	MP_DYNRUNTIME_INIT_ENTRY
	mp_store_global(MP_QSTR_esp_err_to_name, MP_OBJ_FROM_PTR(&espidf_esp_err_to_name_obj));
	mp_store_global(MP_QSTR_pcnt_unit_config, MP_OBJ_FROM_PTR(&espidf_pcnt_unit_config_obj));
	mp_store_global(MP_QSTR_pcnt_get_counter_value, MP_OBJ_FROM_PTR(&espidf_pcnt_get_counter_value_obj));
	mp_store_global(MP_QSTR_pcnt_counter_pause, MP_OBJ_FROM_PTR(&espidf_pcnt_counter_pause_obj));
	mp_store_global(MP_QSTR_pcnt_counter_resume, MP_OBJ_FROM_PTR(&espidf_pcnt_counter_resume_obj));
	mp_store_global(MP_QSTR_pcnt_counter_clear, MP_OBJ_FROM_PTR(&espidf_pcnt_counter_clear_obj));
	mp_store_global(MP_QSTR_pcnt_intr_disable, MP_OBJ_FROM_PTR(&espidf_pcnt_intr_disable_obj));
	MP_DYNRUNTIME_INIT_EXIT
}
