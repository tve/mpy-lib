# Copyright © 2020 by Thorsten von Eicken.
# Simple GUI with screens filled with widgets, some touchable.

# Colors:
# For best performance and lowest memory use, this GUI cean use a GS4_HSMB "4-bit greyscale"
# framebuffer. This is used to represent 16 colors and
# the display driver (it's display() method specifically) is expected to color-map from the 4 bits
# to however many bits the display has.
# The metrial theme takes up 11 colors, the remaining 5 can be used freely by the app, for example
# to draw charts.

# Thoughts about caching:
# Some caching is required in order to switch screens quickly. Many items, such as buttons, labels,
# headers can be rendered once into an "off-screen" framebuffer and then blitted into place.
# One difficulty is that buttons can change color when pressed or disabled, so just rendering each
# button once and blitting doesn't work. This also makes it not so great to pre-render each screen
# at start-up and then just render that and fill-in real-time data, because each widget really
# should be called with a "please render yourself if you look different than the way you got
# pre-rendered". Instead, the caching is pushed down into the widgets so each widget can cache its
# most recent state and either use that or re-render depending on current inputs/values.

import time
from u8g2_font import Font  # only used for timing purposes
import seg7  # seven segment number display

try:
    from micropython import const
except ImportError:

    def const(x):
        return x


# Screen holds a list of widgets that are displayed all together on the display.
class Screen:
    cur = None

    @classmethod
    def config(cls, framebuf, theme, width, height):
        cls.fb = framebuf  # expected to be a subclass of the built-in framebuf
        cls.theme = theme
        cls.width = width
        cls.height = height
        # init colormap
        c = 0

        def set_color(rgb):
            nonlocal c
            cls.fb.color(c, rgb >> 16, (rgb >> 8) & 0xFF, rgb & 0xFF)
            c += 1
            return c - 1

        theme.init(set_color)

    def __init__(self, bgcolor=None):
        self.bgcolor = bgcolor if bgcolor is not None else self.theme.grey
        #
        self.displaylist = []
        self.last_draw = 0

    # activate switches to this screen and renders it
    def activate(self, wid=None):
        Screen.cur = self
        Screen.fb.fill(self.bgcolor)
        Screen.fb.display()  # this provides immediate feedback that the screen is changing
        self.draw(fill=False)

    # draw clears the framebuffer and display, iterates through the display list and calls
    # each widget's draw() method, then pushes the framebuffer on the display
    def draw(self, display=True, fill=True):
        t0 = time.ticks_ms()
        Font.ticks = 0
        Font.ticks_hdr = 0
        if fill:
            Screen.fb.fill(self.bgcolor)
        t1 = time.ticks_ms()
        for wid in self.displaylist:
            wid.draw()
        t2 = time.ticks_ms()
        if display:
            Screen.fb.display()
        self.last_draw = time.ticks_ms()
        print(
            "Redraw: fill=%d draw=%d(text:%d=%d%%) disp=%d tot=%d"
            % (
                time.ticks_diff(t1, t0),
                time.ticks_diff(t2, t1),
                Font.ticks,
                Font.ticks * 100 // time.ticks_diff(t2, t1),
                time.ticks_diff(self.last_draw, t2),
                time.ticks_diff(self.last_draw, t0),
            )
        )

    # add a widget to the display list for this screen.
    def add(self, wid):
        self.displaylist.append(wid)
        wid.screen = self

    @classmethod
    def handle_touch(cls, ev):
        if cls.cur is None:
            return
        print("Touch %d %d" % (ev[1], ev[2]))
        for wid in cls.cur.displaylist:
            if wid.handle(ev[1], ev[2], ev[0]):
                print("Handled by", wid)
                return


class BlueOrangeTheme:
    @classmethod
    def init(cls, set_color):
        cls.primary = set_color(0x1E88E5)
        cls.pri_light = set_color(0x6AB7FF)
        cls.pri_dark = set_color(0x005CB2)
        cls.secondary = set_color(0xF4511E)
        cls.sec_light = set_color(0xFF844C)
        cls.sec_dark = set_color(0xB91400)
        cls.grey = set_color(0x9E9E9E)
        cls.grey_light = set_color(0xCFCFCF)
        cls.grey_dark = set_color(0x424242)
        cls.white = set_color(0xFFFFFF)
        cls.black = set_color(0x000000)


# Widget is the superclass for all display elements that get enqueued on a Screen. I has some
# simple methods to handle boilerplate, such as keeping track of the bounding box and testing
# whether an x-y coordinate is inside or not. It also has support for caching and blitting the
# widget.
class Widget:
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.fb = None  # framebuffer for cached copy

    # inside tests whether the x-y coordinates are within the bounding box passed to __init__.
    def inside(self, x, y):
        return x >= self.x and x < self.x + self.w and y >= self.y and y < self.y + self.h

    # draw renders the widget from cache
    def draw(self):
        if self.fb:
            Screen.fb.blit(self.fb, self.x, self.y)

    # save copies the rendered widget (using its bounding box) to a cache framebuffer
    def save(self):
        if not self.fb:
            self.fb = Screen.fb.allocfb(self.w, self.h)
        self.fb.blit(Screen.fb, -self.x, -self.y)
        # show what got drawn and saved
        # Screen.fb.fill_rect(self.x + self.w // 2, self.y + self.h // 2, 4, 4, rgb565(0xFF0000))

    def handle(self, x, y, press):
        return False


# Drawing is an uncached widget that calls a call-back function when it needs to be rendered.
class Drawing(Widget):
    def __init__(self, draw_cb, handle_cb=None):
        super().__init__(0, 0, 0, 0)
        self.draw_cb = draw_cb
        self.handle_cb = handle_cb

    def draw(self):  # override super's method: no caching ever...
        self.draw_cb()

    def handle(self, x, y, press):
        return self.handle_cb and self.handle_cb(x, y, press)


# TextField is a cached widget that displays a text label. It is basically a wrapper around a Label
# that enables caching.
class TextField(Widget):
    def __init__(self, x, y, w, h, label, pre_cb=None, bgcolor=None):
        super().__init__(x, y, w, h)
        self.label = label
        self.bgcolor = bgcolor
        self.pre_cb = pre_cb
        self.hash = None  # hash for caching

    def draw(self):
        if self.pre_cb:
            self.pre_cb(self)
        # see whether we can render from cache
        hash = (self.bgcolor, self.label.cache_hash())
        if hash == self.hash:
            super().draw()
            return
        # Nope, gotta do the full work
        if self.bgcolor is not None:
            Screen.fb.fill_rect(self.x, self.y, self.w, self.h, self.bgcolor)
        dy = (self.h + self.label.height + 1) // 2
        align = self.label.align
        if align == "center":
            self.label.draw(self.x + self.w // 2, self.y + dy)
        elif align == "left":
            self.label.draw(self.x, self.y + dy)
        elif align == "right":
            self.label.draw(self.x + self.w - 1, self.y + dy)
        # Save to cache
        super().save()
        self.hash = hash


class Button(Widget):
    def __init__(self, x, y, w, h, label, cb, pri=True):
        super().__init__(x, y, w, h)
        self.label = label
        self.state = "enabled"
        self.cb = cb  # call-back to handle button press
        self.pri = pri  # use primary color (else secondary)
        self.hash = None  # hash for caching

    def draw(self):
        # figure out colors given button state
        theme = self.screen.theme
        txtcol = theme.black
        if self.state == "disabled":
            color = theme.grey_light
        elif self.state == "pressed":
            color = theme.pri_dark if self.pri else theme.sec_dark
            txtcol = theme.white
        else:
            color = theme.primary if self.pri else theme.secondary
        # see whether we can render from cache
        hash = (self.state, self.pri, self.label.cache_hash())
        if hash == self.hash:
            super().draw()
            return
        # Nope, gotta do the full work
        Screen.fb.fill_round_rect(self.x, self.y, self.w, self.h, self.h // 4, color)
        dy = (self.h + self.label.height + 1) // 2
        self.label.draw(self.x + self.w // 2, self.y + dy, txtcol)
        # Save to cache
        super().save()
        self.hash = hash

    def handle(self, x, y, press):
        if not self.cb or not self.inside(x, y):
            return False
        if press:
            self.state = "pressed"
            self.draw()
            Screen.fb.display()
        else:
            self.state = "enabled"
            self.draw()
            Screen.fb.display()
            self.cb(self)
        return True


# Label is a text label that can be drawn at an arbitrary x-y coordinate. It is NOT a Widget but
# provides a cache_hash method so a widget that incorporates a Label can compute a hash to detect
# when something changed and the cached version is out of date.
class Label:
    @classmethod
    def default_font(cls, f):
        cls.font = f

    def __init__(self, text, font=None, align="center", color=0):
        self.font = font if font else Label.font
        self.color = color
        self.align = align
        self.text = None
        self.set_text(text)

    def draw(self, x, y, color=None):
        if color is None:
            color = self.color
        # draw from bottom up
        i = len(self.text) - 1
        while i >= 0:
            if self.align == "center":
                self.font.text(self.text[i], x - self.widths[i] // 2, y, color)
            elif self.align == "right":
                self.font.text(self.text[i], x - self.widths[i], y, color)
            else:
                self.font.text(self.text[i], x, y, color)
            y -= self.font.height
            i -= 1

    def cache_hash(self):
        return (self.font, self.color, self.align, self.text)

    def set_text(self, text):
        if text == self.text:
            return
        if "\n" in text:
            # multi-line label
            self.text = text.split("\n")
            self.widths = [self.font.dim(t)[0] for t in self.text]
            self.height = len(self.text) * self.font.height - (self.font.height - self.font.ascend)
            self.width = max(self.widths)
        else:
            self.text = [text]
            self.width, _, self.height = self.font.dim(text)
            self.widths = [self.width]


# NumField displays a numeric field with a tag and a measurement unit, typical of what might be
# found in a sports activity tracker. The tag is small in the upper left, the unit in the upper
# right, and the center mid/bottom contains the number.
# A format string fmt is provided for the number, and value may actually be a tuple, this enables a
# display lke HH:MM:SS by passing a 3-tuple as value.
# The format string must be of fixed width and it cannot be changed without messing up the
# formatting.
class NumField:
    # the fmt must be a printf format that is fixed-width
    def __init__(
        self,
        tag,  # tag to display in the upper left, e.g. "speed", "distance", ...
        fmt,  # format string for the numeric value, must be fixed width
        value=0,  # initial value(s), may be a tuple if fmt contains multiple % formats
        w=None,  # width in pixels for the field
        h=None,  # height in pixels
        font=None,  # font for the number, None to use seven-segment display
        tag_font=None,  # font for the tag and unit
        color=0,  # color for the number
        tag_color=0,  # color for the tag
        unit=None,  # unit to display in the upper right, None to omit, e.g. "mph", "m", ...
        unit_color=0,  # color for the unit
    ):
        self.tag = tag
        self.unit = unit
        self.fmt = fmt
        self.value = value
        self.width = w
        self.height = h
        self.font = font
        self.tag_font = tag_font
        self.color = color
        self.tag_color = tag_color
        self.unit_color = unit_color
        if font is None:
            # calculate positioning using seg7
            # tw, th, thb = tag_font.dim(tag)  # tag width, height, height above baseline
            tw, _, _ = tag_font.dim("0")
            self.txo = tw * 2 // 3
            self.tyo = tag_font.height
            if unit is not None:
                uw, _, _ = tag_font.dim(unit)
                self.uxo = w - uw - tw * 2 // 3
            # assume seg7 is height constrained
            self.sh = h - 10 - tag_font.height  # seg7 digit height
            self.sw = self.sh * 3 // 7  # seg7 digit width
            width = seg7.width(fmt % value, self.sw)
            maxw = w * 9 // 10
            print("SH %s: sh=%d sw=%d w=%d maxw=%d" % (tag, self.sh, self.sw, width, maxw))
            if width > maxw:
                # width-constrained
                self.sw = self.sw * maxw // width
                self.sh = self.sw * 7 // 3
                width = seg7.width(fmt % value, self.sw)
                print("S* %s: sh=%d sw=%d width=%d maxw=%d" % (tag, self.sh, self.sw, width, maxw))
            self.sxo = (w - width) // 2  # seg7 tot width, centered
            self.syo = h - 5 - self.sh
        else:
            # calculate positioning using regular fonts
            nw, nh, nhb = font.dim(fmt % value)  # number width, height, height above baseline
            tw, th, thb = tag_font.dim(tag)  # tag width, height, height above baseline
            if w is not None:
                self.nxo = (w - nw) // 2  # number X offset
                self.txo = self.nxo  # tag X offset
                xtra = h - tag_font.height - font.ascend
                self.tyo = xtra // 2 + tag_font.ascend  # tag Y offset (to baseline)
                self.nyo = xtra // 2 + tag_font.height + font.ascend  # number Y off (to baseline)
            else:
                assert "not supported" == ""

    def set(self, value=None):
        self.value = value

    def draw(self, x, y):
        yt = y + self.tyo
        # draw tag
        self.tag_font.text(self.tag, x + self.txo, yt, self.tag_color)
        # draw unit, if provided
        if self.unit is not None:
            self.tag_font.text(self.unit, x + self.uxo, yt, self.unit_color)
        # draw number
        txt = self.fmt % self.value
        if self.font is None:
            # no font -> draw seven degment digits using lines
            seg7.draw_number(
                Screen.fb, txt, x + self.sxo, y + self.syo, self.sw, self.sh, self.color, 3
            )
        else:
            self.font.text(txt, x + self.nxo, y + self.nyo, self.color)
