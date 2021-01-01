import pytest
from u8g2_font import Font
import u8g2_font


def test_constructor():
    f = Font("luRS24_te.u8f")
    assert f.name == "luRS24_te"
    assert len(f.data) > 17000 and len(f.data) < 20000


def test_find_glyph_ascii():
    f = Font("luRS24_te.u8f")
    for cp in [0, 32, 33, 64, 65, 66, 96, 97, 98, 126, 161, 254, 255]:
        glix = f.find_glyph(cp)
        assert f.data[glix - 2] == cp


def test_find_glyph_unicode():
    f = Font("luRS24_te.u8f")
    for cp in [256, 652]:
        glix = f.find_glyph(cp)
        print(f"cp={cp} found at:", glix)
        assert f.data[glix - 3] << 8 | f.data[glix - 2] == cp


def test_find_glyph_notfound():
    f = Font("luRS24_te.u8f")
    for cp in [10, 130, 400, 8357]:
        glix = f.find_glyph(cp)
        print(f"cp={cp} found at:", glix)
        assert glix is None


def test_get_bitfield():
    f = Font("luRS24_te.u8f")
    for i in range(9):
        data = 0xFF >> i
        for j in range(8):
            w = j + 1
            value = data & ((1 << w)-1)
            # single byte case
            f.data = bytes([data])
            f.init_bitfield(0)
            assert f.get_bitfield(w) == value
            # straddling two bytes
            f.data = bytes([data & 0x0F, data >> 4])
            f.init_bitfield(1)
            f.bf_data = f.data[0]
            f.bf_left = 4
            assert f.get_bitfield(w) == value


def test_get_two_bitfield():
    f = Font("luRS24_te.u8f")
    for i in range(9):
        data = 0xFF >> i
        value1 = data & 0xF
        value2 = data >> 4
        # left nibble
        f.data = bytes([data])
        f.init_bitfield(0)
        assert f.get_bitfield(4) == value1
        # right nibble
        assert f.get_bitfield(4) == value2


pixels = []


def setpixel(x, y, color):
    pixels.append((x, y, color))


def test_glyph_header_A():
    f = Font("luRS24_te.u8f")
    code_point = 65  # A
    x = y = 0
    self = f
    # the following code is extracted from draw_glyph and is what we're testing
    gl_ix = self.find_glyph(code_point)
    assert gl_ix is not None
    assert f.data[gl_ix - 2] == code_point
    print(f"len={f.data[gl_ix-1]}")
    print([i for i in f.data[4:9]])
    print(["%02x" % i for i in f.data[gl_ix : gl_ix + 6]])
    # extract glyph header info
    self.init_bitfield(gl_ix)
    w = self.get_bitfield(self.data[u8g2_font.U8_BPCW])
    h = self.get_bitfield(self.data[u8g2_font.U8_BPCH])
    x += self.get_bitfield(self.data[u8g2_font.U8_BPCX]) - (
        1 << (self.data[u8g2_font.U8_BPCX] - 1)
    )
    y -= self.get_bitfield(self.data[u8g2_font.U8_BPCY]) - (
        1 << (self.data[u8g2_font.U8_BPCY] - 1)
    )
    cd = self.get_bitfield(self.data[u8g2_font.U8_BPCD]) - (
        1 << (self.data[u8g2_font.U8_BPCD] - 1)
    )
    print(w, h, x, y, cd)
    # checks (against BDF version of font)
    # BBX 23 25 0 0
    # DWIDTH 23 0
    assert w == 23
    assert h == 25
    assert x == 0
    assert y == 0
    assert cd == 23
    # let it render and check the pixels
    global pixels
    pixels = []
    f.draw_glyph(setpixel, code_point, 0, 0, 1)
    # print(pixels)
    assert len(pixels) == 209


def test_glyph_header_hyphen():
    f = Font("luRS24_te.u8f")
    code_point = 45  # hyphen
    self = f
    # the following code is extracted from draw_glyph and is what we're testing
    gl_ix = self.find_glyph(code_point)
    assert gl_ix is not None
    l = f.data[gl_ix - 1]
    # extract glyph header info
    self.init_bitfield(gl_ix)
    w = self.get_bitfield(self.data[u8g2_font.U8_BPCW])
    h = self.get_bitfield(self.data[u8g2_font.U8_BPCH])
    x = self.get_bitfield(self.data[u8g2_font.U8_BPCX]) - (1 << (self.data[u8g2_font.U8_BPCX] - 1))
    y = self.get_bitfield(self.data[u8g2_font.U8_BPCY]) - (1 << (self.data[u8g2_font.U8_BPCY] - 1))
    cd = self.get_bitfield(self.data[u8g2_font.U8_BPCD]) - (
        1 << (self.data[u8g2_font.U8_BPCD] - 1)
    )
    print(f"w={w} h={h} x={x} y={y} d={cd}")
    # checks (against BDF version of font)
    # BBX 7 3 2 9
    # DWIDTH 11 0
    assert w == 7
    assert h == 3
    assert x == 2
    assert y == 9
    assert cd == 11
    # let it render and check the pixels
    global pixels
    pixels = []
    f.draw_glyph(setpixel, code_point, 0, 0, 1)
    print(pixels)
    assert len(pixels) == 15+6
    assert pixels[0][0] == x
    assert pixels[0][1] == -h -y
    assert pixels[0][2] == 1


def xxxtest_glyph_header_hyphen():
    f = Font("7x14_tn.u8f")
    code_point = 42  # 45  # hyphen
    self = f
    # the following code is extracted from draw_glyph and is what we're testing
    gl_ix = self.find_glyph(code_point)
    assert gl_ix is not None
    l = f.data[gl_ix - 1]
    print(f"len={l}")
    print([i for i in f.data[4:9]])
    print(["%02x" % i for i in f.data[gl_ix : gl_ix + l - 2]])
    # extract glyph header info
    self.init_bitfield(gl_ix)
    w = self.get_bitfield(self.data[u8g2_font.U8_BPCW])
    h = self.get_bitfield(self.data[u8g2_font.U8_BPCH])
    x = self.get_bitfield(self.data[u8g2_font.U8_BPCX]) - (1 << (self.data[u8g2_font.U8_BPCX] - 1))
    y = self.get_bitfield(self.data[u8g2_font.U8_BPCY]) - (1 << (self.data[u8g2_font.U8_BPCY] - 1))
    cd = self.get_bitfield(self.data[u8g2_font.U8_BPCD]) - (
        1 << (self.data[u8g2_font.U8_BPCD] - 1)
    )
    print(w, h, x, y, cd)
    # checks (against BDF version of font)
    # BBX 7 3 2 9
    # assert w == 7
    # assert h == 3
    # assert x == 2
    # assert y == -9
    # assert cd == 11
    # let it render and check the pixels
    global pixels
    pixels = []
    f.draw_glyph(setpixel, code_point, 0, 0, 1)
    # print(pixels)
