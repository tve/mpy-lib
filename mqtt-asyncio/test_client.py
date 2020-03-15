# Test MQTTClient in mqtt_as.py
# This test runs in cpython using pytest. It stubs/mocks MQTTProto so the test can focus exclusively
# on the client functionality, such as retransmissions.

import pytest

from mqtt_as import MQTTClient, MQTTConfig

broker = ('192.168.0.0', 1883)
cli_id = 'mqtt_as_tester'
prefix = 'esp32/tests/'

# stuff that exists in MP but not CPython
from time import monotonic_ns
def ticks_ms(): return monotonic_ns() // 1000000
def ticks_diff(a, b): return a-b
import asyncio
async def sleep_ms(ms): await asyncio.sleep(ms/1000)

# Fake MQTTProto
class FakeProto:
    def __init__(self, pub_cb, puback_cb, suback_cb, sock_cb=None):
        # Store init params
        self._pub_cb = pub_cb
        self._puback_cb = puback_cb
        self._suback_cb = suback_cb
        self._sock_cb = sock_cb
        # Init private instance vars
        self._connected = False
        self._q = []      # queue of pending incoming messages (as function closures)
        # Init public instance vars
        self.last_ack = 0 # last ACK received from broker
        self.last_req = 0 # last request sent to broker for which an ACK is expectedo
        self.rtt = 40     # milliseconds round-trip time for a broker response
        print("Using FakeProto")

    async def connect(self, addr, client_id, clean, user=None, pwd=None, ssl_params=None,
            response_ms=10*1000, keepalive=0, lw=None):
        await asyncio.sleep(0.1) # arbitrary time to simulate connection
        self._connected = True
        # simulate conn-connack round-trip
        self.last_req = ticks_ms()-10
        self.last_ack = ticks_ms()

    # _sleep_until calls sleep until the deadline is reached (approximately)
    async def _sleep_until(self, deadline):
        dt = ticks_diff(deadline, ticks_ms())
        if dt > 0: await asyncio.sleep_ms(dt)

    # _handle_ping_resp simulates receiving a ping response at time `when`
    async def _handle_ping_resp(self, when):
        await self._sleep_until(when)
        def f(): self.last_ack = ticks_ms()
        self._q.append(f)

    async def ping(self):
        asyncio.get_event_loop().create_task(self._handle_ping_resp(ticks_ms()+self.rtt))
        if ticks_diff(self.last_req, self.last_ack) <= 0: # last_req <= last_ack
            self.last_req = ticks_ms()

    async def disconnect(self):
        await asyncio.sleep_ms(2) # let something else run to simulate write
        self._connected = False

    # _handle_puback simulates receiving a puback
    async def _handle_puback(self, when, pid):
        await self._sleep_until(when)
        def f():
            self.last_ack = ticks_ms()
            self._puback_cb(pid)
        self._q.append(f)
        #print("suback now", len(self._q))

    # _handle_pub simulates receiving a pub message
    async def _handle_pub(self, when, msg):
        await self._sleep_until(when)
        def f(): self._pub_cb(msg)
        self._q.append(f)
        #print("pub now", when, len(self._q))

    async def publish(self, msg, dup=0):
        loop = asyncio.get_event_loop()
        dt = 0
        if msg.qos > 0:
            loop.create_task(self._handle_puback(ticks_ms()+self.rtt, msg.pid))
            dt = 2*(msg.pid&1)
        loop.create_task(self._handle_pub(ticks_ms()+self.rtt+1-dt, msg))
        if msg.qos > 0 and ticks_diff(self.last_req, self.last_ack) <= 0: # last_req <= last_ack
            self.last_req = ticks_ms()

    # _handle_suback simulates receiving a suback
    async def _handle_suback(self, when, pid, qos):
        await self._sleep_until(when)
        def f():
            self.last_ack = ticks_ms()
            self._suback_cb(pid, qos)
        self._q.append(f)
        #print("suback now", len(self._q))

    async def subscribe(self, topic, qos, pid):
        asyncio.get_event_loop().create_task(self._handle_suback(ticks_ms()+self.rtt, pid, qos))
        if ticks_diff(self.last_req, self.last_ack) <= 0: # last_req <= last_ack
            self.last_req = ticks_ms()

    async def check_msg(self):
        if len(self._q) > 0:
            #print("check_msg pop", len(self._q))
            self._q.pop(0)()
        elif self._connected:
            return None
        else:
            raise OSError(-1, "Connection closed")

    async def isconnected(self): return self._connected

# callbacks

msg_q = []
def subs_cb(msg):
    global msg_q
    msg_q.append(msg)

wifi_status = None
async def wifi_coro(status):
    global wifi_status
    wifi_status = status

conn_started = None
async def conn_start(cli):
    global conn_started
    conn_started = True

def reset_cb():
    global msg_q, wifi_status, conn_started
    msg_q = []
    wifi_status = None
    conn_started = None

def fresh_config():
    conf = MQTTConfig()
    conf.server = broker[0]
    conf.port = broker[1]
    conf.client_id = cli_id
    conf.wifi_coro = wifi_coro
    conf.subs_cb = subs_cb
    conf.connect_coro = conn_start
    return conf

#----- test cases using the real MQTTproto and connecting to a real broker

def test_instantiate():
    conf = fresh_config()
    mqc = MQTTClient(conf)
    mqc._MQTTProto = FakeProto
    assert mqc is not None

def test_dns_lookup():
    conf = fresh_config()
    mqc = MQTTClient(conf)
    mqc._MQTTProto = FakeProto
    mqc._dns_lookup()
    assert mqc._addr == broker

@pytest.mark.asyncio
async def test_connect_disconnect():
    conf = fresh_config()
    mqc = MQTTClient(conf)
    mqc._MQTTProto = FakeProto
    assert mqc._active is False
    assert mqc is not None
    await mqc.connect()
    assert mqc._proto is not None
    assert mqc._active is True
    await mqc.disconnect()
    assert mqc._proto is None
    assert mqc._active is False
    await asyncio.sleep_ms(100)
    assert mqc._conn_keeper is None

@pytest.mark.asyncio
async def test_pub_sub_qos0():
    conf = fresh_config()
    conf.debug = 1
    conf.interface.disconnect()
    #
    mqc = MQTTClient(conf)
    mqc._MQTTProto = FakeProto
    reset_cb()
    #
    await mqc.connect()
    await asyncio.sleep_ms(10) # give created tasks a chance to run
    print("wifi status is", wifi_status)
    assert wifi_status == True
    assert conn_started == True
    await mqc.subscribe(prefix+"qos0", 0)
    await mqc.publish(prefix+"qos0", "Hello0")
    await asyncio.sleep_ms(100)
    assert len(msg_q) == 1
    assert msg_q[0].message == b'Hello0'
    await mqc.disconnect()
    await asyncio.sleep_ms(100)
    assert mqc._conn_keeper is None


