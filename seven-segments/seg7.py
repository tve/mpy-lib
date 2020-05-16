# Seven segment display of hex digits.
# From https://stackoverflow.com/a/35566101/3807231

# Order 7 segments clockwise from top left, with crossbar last.
# Coordinates of each segment are (x0, y0, x1, y1)
# given as offsets from top left measured in segment lengths.
offsets = b"\x04\x45\x56\x26\x12\x01\x15"  # same as below encoded in bytes w/ 2bits per digit
# offsets = (
#    (0, 0, 1, 0),  # top
#    (1, 0, 1, 1),  # upper right
#    (1, 1, 1, 2),  # lower right
#    (0, 2, 1, 2),  # bottom
#    (0, 1, 0, 2),  # lower left
#    (0, 0, 0, 1),  # upper left
#    (0, 1, 1, 1),  # middle
# )

# Segments used for each digit; 0, 1 = off, on.
digits = b"\x7E\x30\x6D\x79\x33\x5B\x5F\x70\x7F\x7B\x77\x1F\x4E\x3D\x4F\x47\x63"
# digits = (
#    (1, 1, 1, 1, 1, 1, 0),  # 0
#    (0, 1, 1, 0, 0, 0, 0),  # 1
#    (1, 1, 0, 1, 1, 0, 1),  # 2
#    (1, 1, 1, 1, 0, 0, 1),  # 3
#    (0, 1, 1, 0, 0, 1, 1),  # 4
#    (1, 0, 1, 1, 0, 1, 1),  # 5
#    (1, 0, 1, 1, 1, 1, 1),  # 6
#    (1, 1, 1, 0, 0, 0, 0),  # 7
#    (1, 1, 1, 1, 1, 1, 1),  # 8
#    (1, 1, 1, 1, 0, 1, 1),  # 9
#    (1, 1, 1, 0, 1, 1, 1),  # 10=A
#    (0, 0, 1, 1, 1, 1, 1),  # 11=b
#    (1, 0, 0, 1, 1, 1, 0),  # 12=C
#    (0, 1, 1, 1, 1, 0, 1),  # 13=d
#    (1, 0, 0, 1, 1, 1, 1),  # 14=E
#    (1, 0, 0, 0, 1, 1, 1),  # 15=F
#    (1, 1, 0, 0, 0, 1, 1),  # 16=° (o)
# )

ord_0 = const(48)
ord_9 = const(57)
ord_a = const(97)
ord_g = const(103)
ord_space = const(32)
ord_colon = const(58)
ord_dot = const(46)
ord_oh = const(111)  # degree symbol


def draw_number(fbuf, num_str, x, y, w=24, h=32, color=1, thick=None):
    if not thick:
        thick = (w + 4) >> 3
    if thick > 3:
        thick = 3
    h = h >> 1
    for n in num_str.encode("utf-8"):
        if n == ord_oh:
            n = ord_g
        if n < ord_0 or n > ord_9 and n < ord_a or n > ord_g:
            # it's not a hex digit
            d0 = (thick - 1) >> 1
            if n == ord_dot:
                y0 = y + (h << 1)
                fbuf.fill_rect(x - d0, y0 - d0, thick, thick, color)
                x += 1 + (w >> 1)
            elif n == ord_colon:
                y0 = y + h - (h >> 2)
                y1 = y0 + (h >> 1)
                fbuf.fill_rect(x + 3 - d0 + 2, y0 - d0, thick, thick, color)
                fbuf.fill_rect(x + 3 - d0, y1 - d0, thick, thick, color)
                x += 3 + (w >> 1)
            elif n == ord_space:
                x += w + (w >> 1)
        else:
            # it's a hex digit
            if n <= ord_9:
                n = n - ord_0
            else:
                n = n + 10 - ord_a
            d0 = (thick - 1) >> 1  # minus offset due to thickness
            for seg in range(7):
                on = (digits[n] >> (6 - seg)) & 1
                if not on:
                    continue
                oo = offsets[seg]
                # x0:y0 top-left, x1:y1 bot right offsets for this segment
                x0 = (oo >> 6) & 3
                y0 = (oo >> 4) & 3
                x1 = (oo >> 2) & 3
                y1 = oo & 3
                # xa:ya top-left, xb:yb bot right coords for this segment
                xa = x + x0 * w + 3 * (2 - y0)  # +3*(2-y) creates slant
                ya = y + y0 * h
                xb = x + x1 * w + 3 * (2 - y1)
                yb = y + y1 * h
                for t in range(thick):
                    d = -d0 + t
                    fbuf.line(xa + d, ya + d, xb + d, yb + d, color)
            for i in range(2):
                for j in range(3):
                    (xc, yc) = (x + i * w + 3 * (2 - j), y + j * h)
                    fbuf.fill_rect(xc - 2, yc - 2, 5, 5, 1 - color)

            x += w + (w >> 1)
