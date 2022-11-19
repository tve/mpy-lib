# Copyright © 2021 by Thorsten von Eicken.
# Call closure periodically forever

import time
import logging
import uasyncio as asyncio

log = logging.getLogger(__name__)


async def forever(coro, seconds=0, milliseconds=0, name=None):
    ms = seconds * 1000 + milliseconds  # iteration time
    if ms < 100:
        ms = 100  # let's be realistic...
    ms10 = ms // 10  # minimum sleep
    pause = 10 * ms  # pause in case of error
    if not name:
        name = coro.__name__  # string for error printing
    log.info("forever %s every %dms", name, ms)
    while True:
        t0 = time.ticks_ms()
        try:
            await coro()
            # delay to make the iteration time correct
            dly = time.ticks_diff(time.ticks_ms(), t0)
            if dly < ms10:  # enforce minimum sleep time
                dly = ms10
            await asyncio.sleep_ms(ms)
            pause = 10 * ms  # reset error pause
        except Exception as e:
            try:
                log.exc(e, "forever(%s), pausing %dms", name, pause)
            except Exception:
                pass  # possibly print error?
            await asyncio.sleep_ms(pause)
            # exponential back-off for error pause
            pause = pause * 3 // 2  # 1.5x
            if pause > 100 * ms:
                pause = 100 * ms
