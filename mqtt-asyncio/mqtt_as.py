# mqtt_as.py MQTT implementation for MicroPython using asyncio
# Copyright © 2020 by Thorsten von Eicken.
#
# Loosely based on a version by Peter Hinch
# (which had various improvements contributed by Kevin Köck).
# (C) Copyright Peter Hinch 2017-2019.
#
# Released under the MIT licence.
# See the README.md in this directory for implementaion and usage details.

# The imports below are a little tricky in order to support operation under Micropython as well as
# Linux CPython. The latter is primarily used for tests.

import gc, socket, struct
from binascii import hexlify
from errno import EINPROGRESS, ETIMEDOUT, EAGAIN
from sys import platform

try:
    # imports used with Micropython
    from time import ticks_ms, ticks_diff
    import uasyncio as asyncio
    gc.collect()
    from machine import unique_id
    gc.collect()
    def warn(msg, cat=None, stacklevel=1):
        print("%s: %s" % ("Warning" if cat is None else cat.__name__, msg))
    import network
    STA_IF = network.WLAN(network.STA_IF)
    gc.collect()
except:
    # Imports used with CPython (moved to another file so they don't appear on MP HW)
    from cpy_fix import *

VERSION = (0, 6, 0)

# Timing parameters and constants

# Default short delay when waiting for something (expected chars to arrive, lock to free up, ...)
# Note that for good SynCom throughput need to avoid sleep(0).
_POLL_DELAY = 5  # 100ms added greatly to publish latency

# Response time of the broker to requests, such as pings, before MQTTClient deems the connection
# to be broken and tries to reconnect. MQTTClient issues an explicit ping if there is no outstanding
# request to the broker for half the response time. This means that if the connection breaks and
# there is no outstanding request it could take up to 1.5x the response time until MQTTClient
# notices.
# Specified in MQTTConfig.response_time, suggested to be in the range of 60s to a few minutes.

# Keepalive interval with broker per MQTT spec. Determines at what point the broker sends the last
# will message. Pretty much irrelevant if no last-will message is set. This interval must be greater
# than 1.5x the response time.
# Specified in MQTTConfig.keepalive

# Default long delay in seconds when waiting for a connection to be re-established.
# Can be overridden in tests to make things go faster
_CONN_DELAY = 1

# Legitimate errors while waiting on a socket. See uasyncio __init__.py open_connection().
# EHOSTUNREACH = 118
BUSY_ERRORS = [EINPROGRESS, ETIMEDOUT, EAGAIN, 118]
# Not using the following code 'cause it doesn't help, just adds bytecodes
#if platform == 'esp32' or platform == 'esp32_LoBo':
#    # https://forum.micropython.org/viewtopic.php?f=16&t=3608&p=20942#p20942
#    # Esp-idf error codes/names: esp-idf/components/newlib/include/sys/errno.h
#    EHOSTUNREACH = 118
#    BUSY_ERRORS = [EINPROGRESS, ETIMEDOUT, EAGAIN, EHOSTUNREACH]
#    # Note: orig mqtt_as had 118 = EHOSTUNREACH, which occurs when Wifi goes out of range, which may
#    # be transient, not clear whether to leave it in here or not.
#    # orig mqtt_as also had 119 which is esp-idf's value for EINPROGRESS, but mpy changes it to 115,
#    # maybe there was a fixup missing at the time.
#elif platform == 'linux':
#    BUSY_ERRORS = [EINPROGRESS, ETIMEDOUT, EAGAIN]
#else:
#    BUSY_ERRORS = [EINPROGRESS, ETIMEDOUT]
#
CONN_CLOSED = "Connection closed"
CONN_TIMEOUT = "Connection timed out"
PROTO_ERROR = "Protocol error"

# Default "do little" coro for optional user replacement
async def eliza(*_):
    await asyncio.sleep_ms(_POLL_DELAY)

# MQTTConfig is a "dumb" struct-like class that holds config info for MQTTClient and MQTTProto.
class MQTTConfig:
    # __init__ sets default values
    def __init__(self):
        self.client_id       = hexlify(unique_id())
        self.server          = None
        self.port            = 0
        self.user            = None
        self.password        = b''
        self.response_time   = 60  # in seconds
        self.keepalive       = 600 # in seconds
        self.ssl_params      = None
        self.interface       = STA_IF
        self.clean           = False
        self.max_repubs      = 4
        self.will            = None             # last will message, must be MQTTMessage
        self.subs_cb         = lambda *_: None  # callback on subscription success?
        self.wifi_coro       = eliza            # notification when wifi connects/disconnects
        self.connect_coro    = eliza            # notification when an MQTT connection starts
        self.ssid            = None
        self.wifi_pw         = None
        self.listen_interval = 0                # Wifi listen interval for power save
        self.sock_cb         = None             # callback for esp32 socket to allow bg operation
        self.debug           = 0

    # support map-like access for backwards compatibility
    def __getitem__(self, key):
        return getattr(self, key)
    def __setitem__(self, key, value):
        if not hasattr(self, key):
            warn("MQTTConfig.{} ignored".format(key), DeprecationWarning)
        else:
            setattr(self, key, value)

    # set_last_will records the last will, it is actually transmitted to the broker on connect
    def set_last_will(self, topic, message, retain=False, qos=0):
        qos_check(qos)
        if not topic:
            raise ValueError('Empty topic.')
        self.will = MQTTMessage(topic, message, retain, qos)

#config = MQTTConfig()

def qos_check(qos):
    if not (qos == 0 or qos == 1):
        raise ValueError('unsupported qos')

class Lock():
    def __init__(self):
        self._locked = False

    async def __aenter__(self):
        while True:
            if self._locked:
                await asyncio.sleep_ms(_POLL_DELAY)
            else:
                self._locked = True
                break

    async def __aexit__(self, *args):
        self._locked = False
        await asyncio.sleep_ms(_POLL_DELAY)

class MQTTMessage:
    def __init__(self, topic, message, retain=False, qos=0, pid=None):
        #if qos and pid is None:
        #    raise ValueError('pid missing')
        qos_check(qos)
        if isinstance(topic, str): topic = topic.encode()
        if isinstance(message, str): message = message.encode()
        self.topic = topic
        self.message = message
        self.retain = retain
        self.qos = qos
        self.pid = pid

# MQTTproto implements the MQTT protocol on the basis of a good connection on a single connection.
# A new class instance is required for each new connection.
# In general, connection failures cause an OSError exception to be raised.
class MQTTProto:
    DEBUG = False

    # __init__ creates a new connection based on the config.
    # The list of init params is lengthy but it clearly spells out the dependencies/inputs.
    # The _cb parameters are for publish, puback, and suback packets.
    def __init__(self, pub_cb, puback_cb, suback_cb, sock_cb=None):
        # Store init params
        self._pub_cb = pub_cb
        self._puback_cb = puback_cb
        self._suback_cb = suback_cb
        self._sock_cb = sock_cb
        # Init key instance vars
        self._sock = None
        self._lock = Lock()
        self.last_ack = 0 # last ACK received from broker
        self.last_req = 0 # last request sent to broker for which an ACK is expected

    # connect initiates a connection to the broker at addr.
    # Addr should be the result of a gethostbyname (typ. an ip-address and port tuple).
    # The clean parameter corresponds to the MQTT clean connection attribute.
    # Connect waits for the connection to get established and for the broker to ACK the connect packet.
    # It raises an OSError if the connection cannot be made.
    # Reusing an MQTTProto for a second connection is not recommended.
    async def connect(self, addr, client_id, clean, user=None, pwd=None, ssl_params=None,
            response_ms=10*1000, keepalive=0, lw=None):
        if lw is None:
            keepalive = 0
        ka_min = response_ms * 3 // 2000 # 1.5x in seconds
        if keepalive > 0 and keepalive < ka_min:
            keepalive = ka_min
        self._response_ms = response_ms
        self.dprint('Connecting to {} id={} clean={}'.format(addr, client_id, clean))
        self._sock = socket.socket()
        self._sock.setblocking(False)
        try:
            self._sock.connect(addr)
        except OSError as e:
            if e.args[0] not in BUSY_ERRORS:
                raise
        await asyncio.sleep_ms(_POLL_DELAY)
        #self._raw_sock = self._sock
        if self._sock_cb is not None:
            self._sock.setsockopt(socket.SOL_SOCKET, 20, self._sock_cb)
        if ssl_params is not None:
            self.dprint("Wrapping SSL")
            import ssl
            self._sock = ssl.wrap_socket(self._sock, **ssl_params)
        # Construct connect packet
        premsg = bytearray(b"\x10\0\0\0\0")   # Connect message header
        msg = bytearray(b"\0\x04MQTT\x04\0\0\0")  # Protocol 3.1.1
        if isinstance(client_id, str):
            client_id = client_id.encode()
        sz = 10 + 2 + len(client_id)
        msg[7] = (clean&1) << 1
        if user is not None:
            if isinstance(user, str): user = user.encode()
            if isinstance(pwd, str): pwd = pwd.encode()
            sz += 2 + len(user) + 2 + len(pwd)
            msg[7] |= 0xC0
        if keepalive:
            msg[8] |= (keepalive >> 8) & 0x00FF
            msg[9] |= keepalive & 0x00FF
        if lw is not None:
            sz += 2 + len(lw.topic) + 2 + len(lw.message)
            msg[7] |= 0x4 | (lw.qos & 0x1) << 3 | (lw.qos & 0x2) << 3
            msg[7] |= lw.retain << 5
        i = self._varint(premsg, 1, sz)
        # Write connect packet to socket
        if self._sock is None: await asyncio.sleep_ms(100) # esp32 glitch
        await self._as_write(premsg, i)
        await self._as_write(msg)
        await self._send_str(client_id)
        if lw is not None:
            print("send lw")
            await self._send_str(lw.topic)
            await self._send_str(lw.message)
        if user is not None:
            print("send up")
            await self._send_str(user)
            await self._send_str(pwd)
        self.last_req = ticks_ms()
        # Await CONNACK
        # read causes ECONNABORTED if broker is out
        resp = await self._as_read(4)
        if resp[3] != 0 or resp[0] != 0x20 or resp[1] != 0x02:
            raise OSError(-1)  # Bad CONNACK e.g. authentication fail.
        self.last_ack = ticks_ms()
        #self.dprint('Connected')  # Got CONNACK

    # ===== Helpers

    # dprint prints if self.DEBUG is True
    def dprint(self, *args):
        if self.DEBUG:
            print("MQTTProto:", *args)

    def _check_timeout(self, t):
        if ticks_diff(ticks_ms(), t) > self._response_ms:
            raise OSError(-1, CONN_TIMEOUT)

    # _varint writes 'value' into 'array' starting at offset 'index'. It returns the index after the
    # last byte placed into the array. Only positive values are handled.
    def _varint(self, array, index, value):
        while value > 0x7f:
            array[index] = (value & 0x7f) | 0x80
            value >>= 7
            index += 1
        array[index] = value
        return index+1

    # _as_read reads n bytes from the socket in a blocking manner using asyncio and returns them as
    # bytes. On error or time out it raises an OSError. It should only be used to read data that is
    # known to be "in the pipe" from the broker and not to check whether the broker maybe sent
    # something.
    async def _as_read(self, n):
        data = b''
        if n == 0: return data # behavior of sock.read(0) below is not obvious
        t = ticks_ms()
        while self._sock is not None:
            self._check_timeout(t)
            try:
                msg = self._sock.recv(n - len(data)) # note: sock is in non-blocking mode
            except OSError as e:  # ESP32 issues weird 119 errors here
                msg = None
                if e.args[0] not in BUSY_ERRORS:
                    #self.dprint("_as_read recv error {}".format(e.args[0]))
                    raise
            if msg == b'':  # Connection closed by host
                raise OSError(-1, CONN_CLOSED)
            if msg is not None:  # data received
                data = b''.join((data, msg))
                if len(data) >= n:
                    return data
                t = ticks_ms()
            await asyncio.sleep_ms(_POLL_DELAY)
        raise OSError(-1, CONN_CLOSED)

    # _as_write writes n bytes to the socket in a blocking manner using asyncio. On error or time
    # out it raises an OSError.
    async def _as_write(self, bytes_wr, length=0):
        if length:
            bytes_wr = bytes_wr[:length]
        if len(bytes_wr) == 0: return
        t = ticks_ms()
        while self._sock is not None:
            self._check_timeout(t)
            try:
                n = self._sock.send(bytes_wr)
                if n > 0:
                    t = ticks_ms()
                    bytes_wr = bytes_wr[n:]
                    if len(bytes_wr) == 0:
                        return
            except OSError as e:
                if e.args[0] not in BUSY_ERRORS:
                    #self.dprint("_as_write send error {}".format(e.args[0]))
                    raise
            await asyncio.sleep_ms(_POLL_DELAY)
        raise OSError(-1, CONN_CLOSED)

    # _send_str writes a variable-length string to the socket, prefixing the chars by a 16-bit
    # length
    async def _send_str(self, s):
        await self._as_write(struct.pack("!H", len(s)))
        await self._as_write(s)

    # _recv_len reads a varint length from the socket and returns it
    async def _recv_len(self):
        n = 0
        sh = 0
        while 1:
            res = await self._as_read(1)
            b = res[0]
            n |= (b & 0x7f) << sh
            if not b & 0x80:
                return n
            sh += 7

    # ===== Public functions

    # ping sends a ping packet
    async def ping(self):
        async with self._lock:
            await self._as_write(b"\xc0\0")
        if ticks_diff(self.last_req, self.last_ack) <= 0: # last_req <= last_ack
            self.last_req = ticks_ms()

    # disconnect tries to send a disconnect packet and then closes the socket
    # Trying to send a disconnect as opposed to just closing the socket is important because the
    # broker sends a last-will message if the socket is just closed.
    async def disconnect(self):
        if self._sock is None:
            return
        try:
            async with self._lock:
                self._sock.send(b"\xe0\0")
        except:
            pass
        if self._sock is not None:
            self._sock.close()
        self._sock = None

    def isconnected(self): self._sock is not None

    # publish writes a publish message onto the current socket. It raises an OSError on failure.
    # If qos==1 then a pid must be provided.
    async def publish(self, msg, dup=0):
        # calculate message length
        if type(msg.message) is list:
            mlen = sum(len(m) for m in msg.message)
        else:
            mlen = len(msg.message)
        sz = 2 + len(msg.topic) + mlen
        if msg.qos > 0:
            sz += 2 # account for pid
        if sz >= 2097152:
            raise ValueError('message too long')
        # construct packet header
        pkt = bytearray(4+2+len(msg.topic)+2)
        pkt[0] = 0x30 | msg.qos << 1 | msg.retain | dup << 3
        l = self._varint(pkt, 1, sz)
        struct.pack_into("!H", pkt, l, len(msg.topic))
        l += 2
        pkt[l:l+len(msg.topic)] = msg.topic
        l += len(msg.topic)
        if msg.qos > 0:
            struct.pack_into("!H", pkt, l, msg.pid)
            l += 2
        # send header and body
        async with self._lock:
            await self._as_write(pkt, l)
            if type(msg.message) is list:
                for m in msg.message:
                    if isinstance(m, str): m = m.encode()
                    await self._as_write(m)
            else:
                await self._as_write(msg.message)
        if msg.qos > 0 and ticks_diff(self.last_req, self.last_ack) <= 0: # last_req <= last_ack
            self.last_req = ticks_ms()


    # subscribe sends a subscription message.
    async def subscribe(self, topic, qos, pid):
        if (qos & 1) != qos:
            raise ValueError("invalid qos")
        pkt = bytearray(b"\x82\0\0\0")
        if isinstance(topic, str): topic = topic.encode()
        struct.pack_into("!BH", pkt, 1, 2 + 2 + len(topic) + 1, pid)
        async with self._lock:
            await self._as_write(pkt)
            await self._send_str(topic)
            await self._as_write(qos.to_bytes(1, "little"))
        if ticks_diff(self.last_req, self.last_ack) <= 0: # last_req <= last_ack
            self.last_req = ticks_ms()

    # Check whether a single MQTT message has arrived and process it.
    # Subscribed messages are delivered to a callback previously
    # set by .setup() method. Other (internal) MQTT
    # messages processed internally.
    # Immediate return if no data available. Called from ._handle_msg().
    async def check_msg(self):
        try:
            res = self._sock.recv(1)  # Throws OSError on WiFi fail
        except OSError as e:
            if e.args[0] not in BUSY_ERRORS:
                self.dprint("wait_msg recv error {}".format(e.args[0]))
                raise
            return None
        if res == b'':
            raise OSError(-1, CONN_CLOSED)
        # We got something, dispatch based on message type
        op = res[0]
        if op == 0xd0:  # PINGRESP
            self.dprint("Pong")
            await self._as_read(1)
            self.last_ack = ticks_ms()
        elif op == 0x40:  # PUBACK: remove pid from unacked_pids
            sz = await self._as_read(1)
            if sz != b"\x02":
                raise OSError(-1, PROTO_ERROR)
            rcv_pid = await self._as_read(2)
            pid = rcv_pid[0] << 8 | rcv_pid[1]
            self.last_ack = ticks_ms()
            self._puback_cb(pid)
        elif op == 0x90:  # SUBACK: flag pending subscribe to end
            resp = await self._as_read(4)
            pid = resp[2] | (resp[1] << 8)
            #print("suback", resp[3])
            self.last_ack = ticks_ms()
            self._suback_cb(pid, resp[3])
        elif (op & 0xf0) == 0x30:  # PUB: dispatch to user handler
            sz = await self._recv_len()
            topic_len = await self._as_read(2)
            topic_len = (topic_len[0] << 8) | topic_len[1]
            topic = await self._as_read(topic_len)
            sz -= topic_len + 2
            retained = op & 0x01
            qos = (op>>1) & 3
            pid = None
            if qos: # not QoS=0 -> got pid
                pid = await self._as_read(2)
                pid = pid[0] << 8 | pid[1]
                sz -= 2
            if sz < 0:
                raise OSError(-1, PROTO_ERROR)
            else:
                msg = await self._as_read(sz)
            # Dispatch to user's callback handler
            print("dispatch pub pid=", pid, "qos=", qos)
            self._pub_cb(MQTTMessage(topic, msg, bool(retained), qos, pid))
            # Send PUBACK for QoS 1 messages
            if qos == 1:
                pkt = bytearray(b"\x40\x02\0\0")
                struct.pack_into("!H", pkt, 2, pid)
                async with self._lock:
                    await self._as_write(pkt)
            elif qos == 2:
                raise OSError(-1, "QoS=2 not supported")
        else:
            raise OSError(-1, PROTO_ERROR)
        return op>>4

#-----------------------------------------------------------------------------------------

# MQTTClient class.
class MQTTClient():
    def __init__(self, config):
        # handle config
        self._c = config
        self._response_ms = self._c.response_time*1000
        # config last will and keepalive
        if self._c.will is None:
            self._c.keepalive = 0 # no point setting MQTT keepalive if there's no lw
        elif not isinstance(self._c.will, MQTTMessage):
            raise ValueError('will must be MQTTMessage')
        if self._c.keepalive >= 65536:
            raise ValueError('invalid keepalive time')
        if self._c.keepalive > 0 and self._c.keepalive < self._c.response_time * 1.5:
            raise ValueError("keepalive not >1.5x response_time")
        # config server and port
        if config.port == 0:
            self._c.port = 8883 if config.ssl_params else 1883
        if config.server is None:
            raise ValueError('no server specified')
        # init instance vars
        self._proto = None
        self._MQTTProto = MQTTProto # reference to class, override for testing
        self._addr = None
        self._lastpid = 0
        self._unacked_pids = {}     # PUBACK and SUBACK pids awaiting ACK response
        self._state = 0             # 0=init, 1=has-connected, 2=disconnected=dead
        self._conn_keeper = None    # handle to persistent keep-connection coro
        self._prev_pub = None       # as yet unacked async pub
        self._prev_pub_proto = None # _proto used for as yet unacked async pub
        self.DEBUG = self._c.debug > 0
        # misc
        if platform == "esp8266":
            import esp
            esp.sleep_type(0)  # Improve connection integrity at cost of power consumption.

    # dprint prints if self.DEBUG is True
    def dprint(self, *args):
        if self.DEBUG:
            print("MQTTClient:", *args)

    async def wifi_connect(self):
        self.dprint("connecting wifi")
        s = self._c.interface
        if platform == 'esp8266':
            if s.isconnected():  # 1st attempt, already connected.
                return
            s.active(True)
            s.connect()  # ESP8266 remembers connection.
            for _ in range(60):
                if s.status() != network.STAT_CONNECTING:  # Break out on fail or success. Check once per sec.
                    break
                await asyncio.sleep(_CONN_DELAY)
            if s.status() == network.STAT_CONNECTING:  # might hang forever awaiting dhcp lease renewal or something else
                s.disconnect()
                await asyncio.sleep(_CONN_DELAY)
            if not s.isconnected() and self._c.ssid is not None and self._c.wifi_pw is not None:
                s.connect(self._c.ssid, self._c.wifi_pw)
                while s.status() == network.STAT_CONNECTING:  # Break out on fail or success. Check once per sec.
                    await asyncio.sleep(_CONN_DELAY)
        else:
            s.active(True)
            #self.dprint("Connecting, li=", self._c.listen_interval)
            s.connect(self._c.ssid, self._c.wifi_pw, listen_interval=self._c.listen_interval)
#            if PYBOARD:  # Doesn't yet have STAT_CONNECTING constant
#                while s.status() in (1, 2):
#                    await asyncio.sleep(_CONN_DELAY)
#            elif LOBO:
#                i = 0
#                while not s.isconnected():
#                    await asyncio.sleep(_CONN_DELAY)
#                    i += 1
#                    if i >= 10:
#                        break
#            else:
            while s.status() == network.STAT_CONNECTING:  # Break out on fail or success.
                await asyncio.sleep_ms(200)

        if not s.isconnected():
            self.dprint("Wifi failed to connect")
            raise OSError(-1, "Wifi failed to connect")

    def _dns_lookup(self):
        new_addr = socket.getaddrinfo(self._c.server, self._c.port)
        if len(new_addr) > 0 and len(new_addr[0]) > 1:
            self._addr = new_addr[0][-1]

    async def connect(self):
        if self._state > 1:
            raise ValueError("cannot connect, please create a new instance")
        self.dprint("connecting")
        # deal with wifi and dns
        if not self._c.interface.isconnected():
            await self.wifi_connect()
            # Note the following blocks if DNS lookup occurs. Do it once to prevent
            # blocking during later internet outage:
            if self._state == 0:
                self._dns_lookup()
        # actually open a socket and connect
        proto = self._MQTTProto(self._c.subs_cb, self._got_puback, self._got_suback, self._c.sock_cb)
        proto.DEBUG = self._c.debug > 2
        await proto.connect(self._addr, self._c.client_id, self._c.clean,
                user=self._c.user, pwd=self._c.password, ssl_params=self._c.ssl_params,
                response_ms=self._response_ms, keepalive=self._c.keepalive,
                lw=self._c.will) # raises on error
        self._proto = proto
        # update state
        if self._state == 0:
            self._state = 1
        elif self._state > 1:
            await self.disconnect() # whoops, someone called disconnect() while we were connecting
            raise OSError(-1, "disconnect while connecting")
        # If we get here without error broker/LAN must be up.
        loop = asyncio.get_event_loop()
        # Notify app that Wifi is up
        loop.create_task(self._c.wifi_coro(True))  # Notify app that Wifi is up
        # Start background coroutines that run until the user calls disconnect
        if self._conn_keeper is None:
            self._conn_keeper = loop.create_task(self._keep_connected())
        # Start background coroutines that quit on connection fail
        loop.create_task(self._handle_msgs(self._proto))
        loop.create_task(self._keep_alive(self._proto))
        # Notify app that we're connceted and ready to roll
        loop.create_task(self._c.connect_coro(self))
        self.dprint("connected")

    async def disconnect(self):
        self.dprint("Disconnecting")
        self._state = 2 # dead - do not reconnect
        if self._proto is not None:
            self.dprint("disconnecting")
            await self._proto.disconnect()
        self._proto = None
        print("_state <- 2")

    #===== Manage PIDs and ACKs

    def _newpid(self):
        self._lastpid += 1
        if self._lastpid > 65535: self._lastpid = 1
        return self._lastpid

    # _got_puback handles a puback by removing the pid from those we're waiting for
    def _got_puback(self, pid):
        self.dprint("puback pid=", pid)
        if pid in self._unacked_pids:
            del self._unacked_pids[pid]

    # _got_suback handles a suback by checking that the desired qos level was acked and
    # either removing the pid from the unacked set or flagging it with an OSError.
    def _got_suback(self, pid, qos):
        if pid in self._unacked_pids:
            if self._unacked_pids[pid] == qos:
                del self._unacked_pids[pid]
            elif qos == 0x80:
                print("suback w/refused")
                self._unacked_pids[pid] = OSError(-2, "refused")
            else:
                self._unacked_pids[pid] = OSError(-2, "qos mismatch")

    # _await_pid waits until the broker ACKs a pub or sub message, or it times out.
    # For suback the qos field allows verification that the desired level was met.
    async def _await_pid(self, pid):
        t = ticks_ms()
        while pid in self._unacked_pids:
            if isinstance(self._unacked_pids[pid], OSError):
                raise self._unacked_pids[pid]
            if ticks_diff(ticks_ms(), t) > self._response_ms:
                raise OSError(-1, CONN_TIMEOUT)
            await asyncio.sleep_ms(4*_POLL_DELAY)
        #print("_await_pid unacked:", self._unacked_pids)
        return

    #===== Background coroutines

    # Launched by connect. Runs until connectivity fails. Checks for and
    # handles incoming messages.
    async def _handle_msgs(self, proto):
        try:
            while True:
                op = await proto.check_msg()  # Immediate None return if no message
                if op == None:
                    await asyncio.sleep_ms(_POLL_DELAY)  # Let other tasks get lock
        except OSError as e:
            print(e)
            await self._reconnect(proto, 'read')

    # Keep connection alive MQTT spec 3.1.2.10 Keep Alive.
    # Runs until ping failure or no response in keepalive period.
    async def _keep_alive(self, proto):
        rt_ms = self._c.response_time*1000
        try:
            while proto.isconnected():
                dt = ticks_diff(ticks_ms(), proto.last_ack)
                #print("<dt={},".format(dt), end='')
                if ticks_diff(proto.last_req, proto.last_ack) > 0: # proto.last_req > proto.last_ack
                    # we have a request out there, see whether it timed out
                    if dt >= rt_ms:
                        print(dt, rt_ms, proto.last_req, proto.last_ack)
                        raise OSError(-1)
                    sleep_time = rt_ms - dt
                else:
                    # we're all-ACKed, see whether it's time for the next ping
                    if dt >= rt_ms/2:
                        await proto.ping() # raises on error
                        dt = 0
                    sleep_time = rt_ms/2 - dt
                #print("s{}>".format(sleep_time))
                await asyncio.sleep_ms(sleep_time)
        except Exception as e:
            print("_keep_alive failed:", e)
            await self._reconnect(proto, 'keepalive')

    # _reconnect schedules a reconnection if not underway.
    # the proto passed in must be the one that caused the error in order to avoid closing a newly
    # connected proto when _reconnect gets called multiple times for one failure.
    async def _reconnect(self, proto, why):
        if self._state == 1 and self._proto == proto:
            self.dprint("dead socket:", why, "failed")
            await self._proto.disconnect()
            self._proto = None
            loop = asyncio.get_event_loop()
            loop.create_task(self._c.wifi_coro(False))  # Notify application

    # _keep_connected runs until disconnect() and ensures that there's always a connection.
    # It's strategy is to wait for the current connection to die and then to first reconnect at the
    # MQTT/TCP level. If that fails then it disconnects and reconnects wifi.
    # TODO:
    # - collect stats about which measures lead to success
    # - check whether first connection after wifi reconnect has to be delayed
    # - as an additional step, try to re-resolve dns
    async def _keep_connected(self):
        count = 0
        while self._state == 1:
            print("#", end='')
            if self._proto is not None:
                # We're connected, print debug info and pause for 1 second
                count += 1
                if count >= 20 and self._c.debug:
                    gc.collect()
                    print('RAM free {} alloc {}'.format(gc.mem_free(), gc.mem_alloc()))
                    count = 0
                await asyncio.sleep(_CONN_DELAY)
                continue
            # we have a problem, need some form of reconnection
            if self._c.interface.isconnected():
                self.dprint("reconnecting")
                # wifi thinks it's connected, be optimistic and reconnect to broker
                try:
                    await self.connect()
                    self.dprint('Reconnect OK!')
                    continue
                except OSError as e:
                    self.dprint('Error in MQTT reconnect.', e)
                    # Can get ECONNABORTED or -1. The latter signifies no or bad CONNACK received.
                # connecting to broker didn't work, disconnect Wifi
                if self._proto is not None: # defensive coding -- not sure this can be triggered
                    await self._reconnect(self._proto, "reconnect failed")
                self._c.interface.disconnect()
                await asyncio.sleep(_CONN_DELAY)
                continue # not falling through to force recheck of while condition
            # reconnect to Wifi
            try:
                self.dprint("Wifi reconnecting")
                await self.wifi_connect()
            except OSError as e:
                self.dprint('Error in Wifi reconnect.', e)
                await asyncio.sleep(_CONN_DELAY)
        self.dprint('Disconnected, exited _keep_connected')
        self._conn_keeper = None

    async def subscribe(self, topic, qos=0):
        qos_check(qos)
        pid = self._newpid()
        self._unacked_pids[pid] = qos
        while True:
            while self._proto is None:
                await asyncio.sleep(_CONN_DELAY)
            try:
                proto = self._proto
                await self._proto.subscribe(topic, qos, pid)
                await self._await_pid(pid)
                return
            except OSError as e:
                if e.errno == -2:
                    raise OSError(-1, "subscribe failed:" + e.strerror)
                self.dprint("Subscribe:", e)
            await self._reconnect(proto, 'sub')

    # publish - simple version that doesn't support overlapping/streaming, i.e., immediately blocks
    # waiting for an ack.
#    async def publish1(self, topic, msg, retain=False, qos=0, sync=True):
#        dup = 0
#        pid = self._newpid() if qos else None
#        message = MQTTMessage(topic, msg, retain, qos, pid)
#        if qos:
#            self._unacked_pids[pid] = message
#            print("message:", message)
#        while True:
#            while self._proto is None:
#                await asyncio.sleep(_CONN_DELAY)
#            try:
#                proto = self._proto
#                self.dprint("pub->{} qos={} pid={}".format(topic, qos, pid))
#                await proto.publish(message, dup)
#                await self._await_pid(pid)
#                return
#            except OSError as e:
#                self.dprint("Publish: {}", e)
#            dup = 1
#            await self._reconnect(proto, 'pub')  # Broker or WiFi fail.

    # publish with support for async, meaning that the packet is published but an ack (if qos 1) is
    # not awaited. Instead the ack is awaited after the next packet is published.
    # Algorithm:
    # 1. If prev packet was async:
    #   a. if got ACK go to step 2
    #   b. if still on same socket, go to step 2
    #   c. (no ACK and new socket) retransmit prev packet
    # 2. Transmit new packet
    # 3. If prev packet was async:
    #   a. wait for ACK with timeout, if got ACK go to step 4
    #   b. reconnect, retransmit prev packet, go to step 2
    # 3. If new packet is QoS=0 or async, return success
    # 4. (new packet is QoS=1 and sync) wait for ACK
    async def publish(self, topic, msg, retain=False, qos=0, sync=True):
        dup = 0
        pid = self._newpid() if qos else None
        message = MQTTMessage(topic, msg, retain, qos, pid)
        if qos:
            self._unacked_pids[pid] = message
        while True:
            print("pub begin for pid=", pid)
            # first we need a connection
            while self._proto is None:
                await asyncio.sleep(_CONN_DELAY)
            # if there is an async packet outstanding and it has not been acked, and a new connection
            # has been established then begin by retransmitting that packet.
            proto = self._proto
            if self._prev_pub is not None and pid in self._unacked_pids and \
                    self._prev_pub_proto != proto:
                m = self._prev_pub
                self.dprint("repub->{} qos={} pid={}".format(m.topic, m.qos, m.pid))
                self._prev_pub_proto = proto
                try:
                    await proto.publish(m, 1)
                except OSError as e:
                    self.dprint("Publish: {}", e)
                    await self._reconnect(proto, 'pub')
                    continue
            # now publish the new packet on the same connection
            self.dprint("pub->{} qos={} pid={}".format(message.topic, message.qos, message.pid))
            try:
                await proto.publish(message, dup)
            except OSError as e:
                self.dprint("Publish: {}", e)
                await self._reconnect(proto, 'pub')
                continue
            # if there is an async packet outstanding wait for an ack
            if self._prev_pub is not None:
                try:
                    self.dprint("awaiting prev", self._prev_pub.pid)
                    await self._await_pid(self._prev_pub.pid)
                except OSError as e:
                    self.dprint("Publish: {}", e)
                    await self._reconnect(proto, 'pub')
                    continue
            # got ACK! prev packet is done and new one becomes prev if qos>0 and async, or
            # goota wait for new one's ack if sync
            self._prev_pub = None
            self._prev_pub_proto = None
            if qos == 0:
                return
            if not sync:
                self._prev_pub = message
                self._prev_pub_proto = proto
                return
            try:
                await self._await_pid(message.pid)
                return
            except OSError as e:
                self.dprint("Publish: {}", e)
                await self._reconnect(proto, 'pub')
