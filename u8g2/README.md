u8g2 for MicroPython
====================

This library is a MicroPython port of the u8g2 font library. The u8g2 fonts are very
compact allowing even large fonts to fit into the flash of a microcontroller. The decoding
of the fonts is also quite efficient enabling direct rendering from the encoded form without
separate "decompression" step.

The u8g2 library can be found at https://github.com/olikraus/u8g2. Cloning that repo provides
access to the C encoding of a large number of fonts. Specifically, the C font files are found
in the `tools/font/build/single_font_files` subdirectory. For example, the Lucida Regular Sans
24 point font with an extended character set is in `u8g2_font_luRS24_te.c` and encodes over 430
glyphs in under 18KB.

The `u8g2_convert.py` script converts a C font file to a binary `.u8f` file, which can be copied
to the filesystem of a MicroPython microcontroller and which can be read directly by the
`u8g2_font.py` library. The `u8g2_font` library provides a `Font` class, which renders one font
as found in one `.u8f` file. The library reads the whole file into RAM and its `draw_glyph`
function renders a glyph directly from the compressed format into a framebuffer using a provided
`hline` function.

The `u8g2_convert.py` script also produces a `.py` file which can be added to the manifest used to
build a custom MicroPython firmware thereby building the font into the firmware. On the esp32 the
benefit is that the font remains in flash at all times, very little memory is used (for the decoded
font descriptor once the font is loaded). To use the built-in font specify its name without file
extension, such as `"luRS18_te"`.

The most commonly used functions of the `Font` class are:
- `text` renders a string using a provided `hline` function. The MicroPython `FrameBuffer`
  `hline` method can be used directly. Note that the x-y coordinates are for the _baseline_
  to the left of the first character and the library expects y coordinates to increase towards
  the bottom of the display.
- `dim` returns the total width and height of a string. Both the ascend height and the total height
  are returned.

The `draw_glyph` method is at the core of the library. It decodes a glyph and renders it in one
step. On the one hand This function is relatively fast, on the other it could be faster... The first
place to optimize is to provide a fast `hline` function. The next is to (manually) inline the
`hline` function into `draw_glyph`, although this only really makes sense if the picel format is
simple, such as 8 bits per pixel. At some point it probably makes sense to code-up a C version of
`draw_glyph`...
