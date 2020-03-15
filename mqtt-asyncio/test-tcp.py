# TCP test - This tests some basic TCP failure behavior to inform the measures that MQTTClient
# should take. This test should be run simultaneously on an esp32 and a linux (or other?) host. On
# the esp32 is will be a TCP client that connects and sends 1-byte ping packets and expects to read
# a response back. On the host it will be a TCP server that reads and echoes what comes in.
# The output is not self-explanatory and some manual intervention (such as breaking tcp connections
# using iptables) is required. Overall, this is not an automated unit test but rather something used
# to understand how micropython & lwip behave when things go south.

# Some observations gained from testing:
# - As of MPY 1.12 error codes are a bit of a mess on the esp32.s
#   The port uses the MPY default error codes, which do not exactly correspond with esp-idf's
#   error codes. For example, EINPROGRESS is defined as 115 in mperrno.c while esp-idf in newlib's
#   errno.h defines it as 119. This particular one is mapped from 119->115 in mpy, but that makes
#   ENETDOWN, which is 115 in esp-idf, essentially indinstiguishable from EINPROGRESS.
# - If connectivity on an open TCP connection breaks (without wifi going down) it takes esp-idf/lwip
#   many many minutes to detect the issue and error the socket. At that point send and recv get a
#   EHOSTUNREACH=118 once and then ENOTCONN=128 afterwards. It is thus not reasonable to rely on
#   TCP's max retransmission timeout to detect effectively dead connections.
# - When going out of Wifi range send/recv may return EHOSTUNREACH.
# - To break TCP connections use the following on the host:
#   sudo /sbin/iptables -A OUTPUT -p tcp --sport 23232 -j DROP
#   and to restore use
#   sudo /sbin/iptables -D OUTPUT -p tcp --sport 23232 -j DROP

SERVER = '192.168.0.2'
PORT = 23232

import socket

try:
    from time import ticks_ms, ticks_diff, sleep_ms
    gc.collect()
except:
    from time import monotonic_ns, sleep
    def ticks_ms(): return monotonic_ns() // 1000000
    def ticks_diff(a, b): return a-b
    def sleep_ms(ms): sleep(ms/1000)

def since(ms): return ticks_diff(ticks_ms(), ms)

ERRNOS = {
    23: "ENFILE",
    #115: "ENETDOWN", # that's esp-idf's meaning for 115, but MPY uses it for EINPROGRESS
    118: "EHOSTUNREACH",
    119: "EINPROGRESS", # should never come through as 119 but as 115
    128: "ENOTCONN",
}
def pe(e):
    if isinstance(e, OSError):
        try:
            return "{}: [Errno {}] {}".format(type(e).__name__, e.args[0], ERRNOS[e.args[0]])
        except:
            pass
    return "{}: {}".format(type(e).__name__, e)

import errno
BUSY_ERRORS = [errno.EINPROGRESS, errno.ETIMEDOUT, errno.EAGAIN]
def is_busy(e): return isinstance(e, OSError) and e.args[0] in BUSY_ERRORS

import sys
if sys.platform == 'esp32':
    import network, errno
    sta = network.WLAN(network.STA_IF)
    if not sta.isconnected():
        print("connecting wifi")
        sta.active(True)
        sta.connect("SSID", "PASSWORD")
        sleep_ms(2)
    # Loop over connections
    t0 = None
    while True:
        if t0 is not None: sleep_ms(1000)
        t0 = ticks_ms()
        # connection attempt
        try:
            sock = socket.socket()
            sock.setblocking(False)
            print("connecting to {}:{}".format(SERVER, PORT))
            sock.connect((SERVER, PORT))
            print("connected in {}ms".format(since(t0)))
        except OSError as e:
            if e.args[0] == errno.EINPROGRESS:
                print("connect in progress")
            else:
                print("connect exception in {}ms: {}".format(since(t0), pe(e)))
                if not is_busy(e):
                    sock.close()
                    continue
        # Loop over pings
        i = 0
        while True:
            # recv
            t0 = ticks_ms()
            try:
                buf = sock.recv(100)
                print("read in {}ms: {}".format(since(t0), None if buf is None else len(buf)))
            except Exception as e:
                print("read exception in {}ms: {}".format(since(t0), pe(e)))
                if not is_busy(e): break
            # send
            t0 = ticks_ms()
            try:
                n = sock.send(i.to_bytes(2, 'big'))
                if n == 2:
                    print("ping 2 OK in {}ms".format(since(t0)))
                else:
                    print("ping 2 err in {}ms: {}".format(since(t0), n))
            except Exception as e:
                print("ping 2 exception in {}ms: {}".format(since(t0), pe(e)))
                if not is_busy(e): break
            sleep_ms(2000)
            i += 1
        sock.close()
else:
    srv = socket.socket()
    srv.bind(('0.0.0.0', 23232))
    srv.listen()
    print("listening to port", PORT)
    # Loop over connections
    while True:
        sock = srv.accept()[0]
        print("accepted connection")
        # Loop over pings
        i = 0
        while True:
            # recv
            t0 = ticks_ms()
            try:
                buf = sock.recv(100)
                print("read in {}ms: {}".format(since(t0), len(buf)))
            except Exception as e:
                print("read exception in {}ms: {}".format(since(t0), pe(e)))
                sleep_ms(2000)
                continue
            # reply
            i += 1
            if i % 2 == 0: continue
            t0 = ticks_ms()
            try:
                n = sock.send(buf)
                if n == len(buf):
                    print("reply OK in {}ms".format(since(t0)))
                else:
                    print("reply err in {}ms: {}".format(since(t0), n))
            except Exception as e:
                print("reply exception in {}ms: {}".format(since(t0), pe(e)))







