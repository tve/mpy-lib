# Copyright © 2020 by Thorsten von Eicken. MIT License.
#
# u8g2 fonts from https://github.com/olikraus/u8g2

import time

HDR_CACHE_SZ = 100  # up to 100 cached glyph headers

try:
    from micropython import const
    import micropython
    from uarray import array
except ImportError:
    from array import array

    def const(x):
        return x

    ptr8 = const
    ptr16 = const

    class micropython:
        def viper(x):
            return x


# The font format consists of a font header followed by compressed glyphs.

U8_CNT = const(0)  # glyph count
U8_MODE = const(1)  # mode: 0: proportional, 1: common height, 2: monospace, 3: mult. of 8
U8_BP0 = const(2)  # bits_per_0: number of bits used to encode unset-pixel run-length
U8_BP1 = const(3)  # bits_per_1: number of bits used to encode set-pixel run-length
U8_BPCW = const(4)  # bits_per_char_width: number of bits used to encode character width
U8_BPCH = const(5)  # bits per char heigh
U8_BPCX = const(6)  # bits per char x offset
U8_BPCY = const(7)  # bits per char y offset
U8_BPCD = const(8)  # bits per char x delta to next char
U8_MAXW = const(9)  # max char width
U8_MAXH = const(10)  # max char height
U8_XO = const(11)
U8_YO = const(12)
U8_AA = const(13)  # height of A ascend
U8_DG = const(14)  # height of g descend
U8_AP = const(15)  # height of ( ascend
U8_DP = const(16)  # height of ) descent
U8_IXA = const(17)  # 2 byte offset from end of header (pos 23) to start of A
U8_IXa = const(19)  # 2 byte offset from end of header (pos 23) to start of a
U8_IXU = const(21)  # 2 byte offset from end of header (pos 23) to unicode table
U8_GLYPHS = const(23)  # first glyph

# Glyph format:
# 0.	1/2 Byte(s)	Unicode of character/glyph
# 1. (+1)	1 Byte	jump offset to next glyph
# bitcntW	glyph bitmap width (variable width)
# bitcntH	glyph bitmap height (variable width)
# bitcntX	glyph bitmap x offset (variable width)
# bitcntY	glyph bitmap y offset (variable width)
# bitcntD	character pitch (variable width)
# n Bytes	Bitmap (horizontal, RLE)


# Font reads a full u8g2 font from a file in compressed format and renders glyphs from the
# compressed format as-is.
class Font:
    def __init__(self, filepath, hline=None):
        self.name = filepath.split("/")[-1]
        if self.name.endswith(".u8f"):
            self.name = self.name[:-4]
            try:
                self.data = open(filepath, "rb").read()
            except OSError as e:
                raise ValueError(filepath + ": " + str(e))
        else:
            f = __import__(self.name)
            self.data = f.data
        self.hline = hline
        self.fb = None
        self.ascend = self.data[U8_AA]  # font ascend from "A"
        desc = 256 - self.data[U8_DG]  # font descent from "g" (as positive value)
        self.height = self.ascend + desc  # total font height
        self.hdr_cache = {}  # header cache

    ticks = 0
    ticks_hdr = 0

    # find_glyph returns the index into the font data array where the glyph with the
    # requested code_point can be found. The returned index points to the "bitcntW" field.
    def find_glyph(self, code_point: int) -> int:
        data = self.data
        ix = 23
        if code_point < 0x100:
            # "ascii" portion, first use offsets
            if code_point >= 97:  # after a
                ix += data[U8_IXa] << 8 | data[U8_IXa + 1]
            elif code_point >= 65:  # after A
                ix += data[U8_IXA] << 8 | data[U8_IXA + 1]
            # linear search
            while code_point != data[ix]:
                off = data[ix + 1]
                if off == 0:
                    return None
                ix += off
            return ix + 2
        else:
            # "unicode" portion, use unicode jump table
            ix += data[U8_IXU] << 8 | data[U8_IXU + 1]
            glyphs = int(ix)
            while True:
                glyphs += data[ix] << 8 | data[ix + 1]  # where this block starts
                cp = data[ix + 2] << 8 | data[ix + 3]  # highest code point in this block
                if code_point <= cp:
                    break
                ix += 4
                if ix > int(len(self.data)):
                    return None
            # linear search
            ix = glyphs
            cp = data[ix] << 8 | data[ix + 1]
            while code_point != cp:
                if cp == 0:
                    return None
                ix += data[ix + 2]
                cp = data[ix] << 8 | data[ix + 1]
            return ix + 3

    # get_bf returns a bit field at offset ix (in bits!) of data, of width bits.
    # signed indicates whether the bit field is signed or not.
    @micropython.viper
    @staticmethod
    def get_bf(data: ptr8, ix: int, width: int, signed: bool) -> int:
        if width > 8:
            raise ValueError("too wide a bitfield")
        d = int(data[ix >> 3] + (data[(ix >> 3) + 1] << 8))
        d = int((d >> (ix & 7)) & ((1 << width) - 1))
        if not signed:
            return d
        else:
            return d - (1 << (width - 1))

    def glyph_hdr(self, ix):
        data = self.data
        # width
        bits = data[U8_BPCW]
        w = self.get_bf(data, ix, bits, False)
        ix += bits
        # height
        bits = data[U8_BPCH]
        h = self.get_bf(data, ix, bits, False)
        ix += bits
        # x offset
        bits = data[U8_BPCX]
        x = self.get_bf(data, ix, bits, True)
        ix += bits
        # y offset
        bits = data[U8_BPCY]
        y = h + self.get_bf(data, ix, bits, True)
        ix += bits
        # cd
        bits = data[U8_BPCD]
        cd = self.get_bf(data, ix, bits, True)
        ix += bits
        #
        if ix > 0xFFFFFF:
            raise ValueError("ix too big (%d)" % ix)
        return array("b", (w, h, x, y, cd, ix >> 16, (ix >> 8) & 0xFF, ix & 0xFF))

    def glyph_header(self, code_point):
        if code_point in self.hdr_cache:
            return self.hdr_cache[code_point]
        # construct header info
        gl_ix = self.find_glyph(code_point)
        if gl_ix is None:
            return None
        hdr = self.glyph_hdr(gl_ix * 8)
        # save in cache and return
        self.hdr_cache[code_point] = hdr
        if len(self.hdr_cache) == HDR_CACHE_SZ:
            print("OOPS: font cache size reached ****")
        return hdr

#    @micropython.viper
#    def draw_fast(self, gl_ix: int, fb_ix: int, width: int, height: int, color: int):
#        fb = ptr16(self.fb)
#        stride = 240
#        data = ptr8(self.data)
#        zbits = data[U8_BP0]
#        obits = data[U8_BP1]
#        cur_x = int(0)
#        fb_ix_end = fb_ix + height * stride
#        while fb_ix < fb_ix_end:
#            zeros = int(self.get_bf(data, gl_ix, zbits, False))
#            gl_ix += zbits
#            ones = int(self.get_bf(data, gl_ix, obits, False))
#            gl_ix += obits
#            # repeat the run until we read a 0 bit
#            while True:
#                # skip the zeros (transparent)
#                cur_x += zeros
#                while cur_x >= width:
#                    cur_x -= width
#                    fb_ix += stride
#                # draw the ones
#                for _ in range(ones):
#                    fb[fb_ix + cur_x] = color
#                    cur_x += 1
#                    if cur_x == width:
#                        fb_ix += stride
#                        cur_x = 0
#                # read next bit and repeat if it's a one
#                bit = (data[gl_ix >> 3] >> (gl_ix & 7)) & 1
#                gl_ix += 1
#                if bit == 0:
#                    break

    # draw_glyph draws the glyph corresponding to code_point at position x,y, where y is the
    # baseline. It returns the delta-x to the next glyph.
    def draw_glyph(self, hline, code_point, x, y, color):
        t0 = time.ticks_ms()
        hdr = self.glyph_header(code_point)
        if hdr is None:
            return None
        w, h, dx, dy, cd, ix1, ix2, ix3 = hdr
        gl_ix = (ix1 << 16) | ((ix2 & 0xFF) << 8) | (ix3 & 0xFF)
        if w == 0:  # character without pixels (e.g. space)
            return cd
        Font.ticks_hdr += time.ticks_diff(time.ticks_ms(), t0)
        # advance to first pixel of char
        x += dx
        y -= dy
        # if the framebuffer has a u8g2_glyph method call it to draw the glyph
        try:
            data = self.data
            self.fb.u8g2_glyph((data, data[U8_BP0], data[U8_BP1]), gl_ix, x, y, w, h, color)
            # self.draw_fast(gl_ix, x + 240 * y, w, h, color)
            return cd
        except AttributeError:
            # draw runlengths
            cur_x = 0
            end_y = y + h
            # consume runs of 0's and 1's until we reach the bottom of the glyph
            data = self.data
            zbits = data[U8_BP0]
            obits = data[U8_BP1]
            while y < end_y:
                zeros = self.get_bf(data, gl_ix, zbits, False)
                gl_ix += zbits
                ones = self.get_bf(data, gl_ix, obits, False)
                gl_ix += obits
                # repeat the run until we read a 0 bit
                while True:
                    # skip the zeros (transparent)
                    cur_x += zeros
                    while cur_x >= w:
                        cur_x -= w
                        y += 1
                    # draw the ones
                    o = ones
                    left = w - cur_x
                    while o >= left:
                        hline(x + cur_x, y, left, color)
                        o -= left
                        cur_x = 0
                        y += 1
                        left = w
                    if o > 0:
                        hline(x + cur_x, y, o, color)
                        cur_x += o
                    # read next bit and repeat if it's a one
                    bit = (data[gl_ix >> 3] >> (gl_ix & 7)) & 1
                    gl_ix += 1
                    if bit == 0:
                        break

        return cd

    # text draws the string starting at coordinates x;y, where y is the baseline of the text.
    # It returns the rendered text width.
    def text(self, string, x0, y, color, hline=None):
        t0 = time.ticks_ms()
        if hline is None:
            hline = self.hline
        x = x0
        for ch in string:
            cd = self.draw_glyph(hline, ord(ch), x, y, color)
            if cd is None:
                raise ValueError("Glyph %d not found" % ord(ch))
            else:
                x += cd
        Font.ticks += time.ticks_diff(time.ticks_ms(), t0)
        return x - x0

    # dim returns the width, total height, and height above baseline of the string in pixels
    def dim(self, string):
        t0 = time.ticks_ms()
        width = 0
        height = 0
        rise = 0
        for ch in string:
            cp = ord(ch)
            #
            t1 = time.ticks_ms()
            hdr = self.glyph_header(cp)
            if hdr is None:
                raise ValueError("Glyph %d (%s) not found" % (cp, ch))
            Font.ticks_hdr += time.ticks_diff(time.ticks_ms(), t1)
            h = hdr[1]
            up = hdr[3]
            cd = hdr[4]
            #
            width += cd
            if h > height:
                height = h
            if up > rise:
                rise = up
        Font.ticks += time.ticks_diff(time.ticks_ms(), t0)
        return width, height, rise
