#! /usr/bin/python3

# Generator for stubs to call C functions from python

import sys

# map types....
type_map = { "I": "uint", "i": "int", "H": "uint16", "h": "int16", "B": "uint8", "b": "int8",
        "P": "void*", "s": "char*", "": "void" }

# convert return values....
return_map = { "I": "mp_obj_new_int({})", "s": "mp_obj_new_str({0}, strlen({0}))", "": "{}" }

# files to import
imports = [
    "esp_err.h",
    ]

# functions for which to create stubs
entry_points = []

for l in sys.stdin:
    l = l.strip()
    if l.startswith("i "):
        # #import filename
        fn = l[1:].strip()
        imports.append(fn)
    elif l.startswith("f "):
        # function template
        ll = l.split()
        if len(ll) != 4:
            print("Cannot find 4 words in '{}'".format(l))
            continue
        entry_points.append((ll[1], ll[2], ll[3]))
    elif l.startswith("#") or len(l) == 0:
        pass
    else:
        print("Cannot parse '{}'".format(l))
print("Imports:", imports, file=sys.stderr)
print("Entry points:", entry_points, file=sys.stderr)

# Generate espidf module to expose functions to python
builtin = False # sys.argv[1] == '--builtin'
print('#include <assert.h>')
print('#include <string.h>')
if builtin:
    print('#include "py/runtime.h"')
else:
    print('#include "py/dynruntime.h"')

print('// ESP-IDF imports')
for im in imports:
    print("#include <{}>".format(im))
for name, args, res in entry_points:
    print()
    print("STATIC mp_obj_t espidf_{}(".format(name), end='')
    print(", ".join(["mp_obj_t arg{}".format(ix) for ix in range(len(args))]), end='')
    print(") {")
    for ix, fmt in enumerate(args):
        print("\t// convert arg{}".format(ix))
        if fmt == "P":
            print("\tmp_buffer_info_t val{}_buf;".format(ix))
            print("\tmp_get_buffer_raise(arg{0}, &val{0}_buf, MP_BUFFER_RW);".format(ix))
            print("\tvoid *val{0} = (void *)(val{0}_buf.buf);".format(ix))

        elif fmt in frozenset(["I", "i", "H", "h", "B", "b"]):
            print("\t{1} val{0} = ({1})mp_obj_get_int(arg{0});".format(ix, type_map[fmt]))
    print("\t// call")
    if res == "":
        print("\tmp_obj_t ret = mp_const_none;")
        print("\t{}(".format(name), end='')
    else:
        print("\tconst {} ret = {}(".format(type_map[res], name), end='')
    print(", ".join([ "val{}".format(ix) for ix in range(len(args)) ]), end='')
    print(");")
    print("\treturn " + return_map[res].format('ret') + ";\n}")
    if len(args) < 4:
        print("STATIC MP_DEFINE_CONST_FUN_OBJ_{}(espidf_{}_obj, espidf_{});".format(
            len(args), name, name))
    else:
        print("STATIC MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(espidf_{}_obj, {}, {}, espidf_{});".format(
            len(args), len(args), name, name))
print()
if builtin:
    # generate module built into the firmware
    print("STATIC const mp_rom_map_elem_t mp_module_espidf_globals_table[] = {")
    print("\t{ MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_espidf) },")
    for name, _, _ in entry_points:
        print("\t{{ MP_ROM_QSTR(MP_QSTR_{}), MP_ROM_PTR(&espidf_{}) }},".format(name, name))
    print('''\
};
STATIC MP_DEFINE_CONST_DICT(mp_module_espidf_globals, mp_module_espidf_globals_table);

const mp_obj_module_t mp_module_espidf = {
.base = { &mp_type_module },
.globals = (mp_obj_dict_t*)&mp_module_espidf_globals,
};

#endif
''', end='')
else:
    # generate dynamically loadable module
    print("mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {")
    print("\tMP_DYNRUNTIME_INIT_ENTRY")
    for name, _, _ in entry_points:
        print("\tmp_store_global(MP_QSTR_{0}, MP_OBJ_FROM_PTR(&espidf_{0}_obj));".format(name))
    print("\tMP_DYNRUNTIME_INIT_EXIT")
    print("}")
