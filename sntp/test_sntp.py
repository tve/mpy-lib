# Test sntp.py using CPython
# Copyright (c) 2020 by Thorsten von Eicken

import pytest
import sntp
import time, os, socket, asyncio

pytestmark = pytest.mark.timeout(2)

UNIX_DELTA = 946684800
NTP_DELTA = 3155673600

os.environ["TZ"] = "UTC"
time.tzset()


def mktime(y, mo, d, h, m, s):
    return int(time.mktime((y, mo, d, h, m, s, 0, 0, 0)))


def test_deltas():
    assert UNIX_DELTA == mktime(2000, 1, 1, 0, 0, 0) - mktime(1970, 1, 1, 0, 0, 0)
    assert NTP_DELTA == mktime(2000, 1, 1, 0, 0, 0) - mktime(1900, 1, 1, 0, 0, 0)


def test_round_trip():
    for year in [ 2019, 2025 ]:
        mp1 = (mktime(year, 2, 24, 17, 59, 10) - UNIX_DELTA) * 1000000 + 238000
        ntp = sntp.mp2ntp(mp1)
        mp2 = sntp.ntp2mp(*ntp)
        assert abs(mp1 - mp2) < 2


def test_mp2ntp():
    mp1 = 1234 * 1000000 + 500000
    ntp1got = sntp.mp2ntp(mp1)
    ntp1exp = (1234 + NTP_DELTA, 0x80000000)
    assert ntp1got == ntp1exp
    # example from http://www.ntp.org/ntpfaq/NTP-s-algo.htm #5.1.2.3
    unix2 = (0x39AEA96E, 0x000B3A75)
    mp2 = (unix2[0] - UNIX_DELTA) * 1000000 + unix2[1]
    ntp2got = sntp.mp2ntp(mp2)
    ntp2exp = (0xBD5927EE, 0xBC616000)
    print("%x %x" % (ntp2got[1], ntp2exp[1]))
    assert ntp2got[0] == ntp2exp[0]
    assert abs(ntp2got[1] - ntp2exp[1]) < (2 ** 32) / 1000000


def test_ntp2mp():
    ntp1 = (NTP_DELTA, 0x80000000)
    mp1got = sntp.ntp2mp(*ntp1)
    mp1exp = 500000
    assert mp1got == mp1exp
    # example from http://www.ntp.org/ntpfaq/NTP-s-algo.htm #5.1.2.3
    ntp2 = (0xBD5927EE, 0xBC616000)
    mp2got = sntp.ntp2mp(*ntp2)
    unix2got = divmod(mp2got, 1000000)
    unix2got = (unix2got[0] + UNIX_DELTA, unix2got[1])
    unix2exp = (0x39AEA96E, 0x000B3A75)
    print("%x %x" % (unix2got[1], unix2exp[1]))
    assert unix2got[0] == unix2exp[0]
    assert abs(unix2got[1] - unix2exp[1]) < 2

@pytest.mark.asyncio
async def test_poll():
    sntpcli = sntp.SNTP()
    delay, step = await sntpcli._poll()
    assert delay < 200*1000
    assert abs(step) < 100*1000

@pytest.mark.asyncio
async def test_poll_dns_fail():
    sntpcli = sntp.SNTP(host="nonexistant.example.com")
    with pytest.raises(socket.gaierror):
        delay, step = await sntpcli._poll()

@pytest.mark.asyncio
async def test_poll_timeout():
    sntpcli = sntp.SNTP(host="1.1.1.1")
    with pytest.raises(asyncio.TimeoutError):
        delay, step = await sntpcli._poll()

@pytest.mark.asyncio
async def test_start_stop():
    sntpcli = sntp.SNTP()
    sntpcli.start()
    await asyncio.sleep(1)
    await sntpcli.stop()
