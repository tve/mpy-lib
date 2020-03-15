# Test MQTTProto in mqtt_as.py
# This test runs under cpython (`python ./test-clean.py`) and micropython (`./pyb test-clean.py`)
# Failures are printed explcitly ("Error: ...")

from mqtt_as import MQTTProto, MQTTMessage

broker = ('192.168.0.14', 1883)
cli_id = 'mqtt_as_tester'
prefix = 'esp32/tests/'

try:
    from time import ticks_ms, ticks_diff
except:
    from time import monotonic_ns
    def ticks_ms(): return monotonic_ns() // 1000000
    def ticks_diff(a, b): return a-b

try:
    import uasyncio as asyncio
    from uasyncio import sleep_ms
except:
    import asyncio
    def sleep_ms(ms): asyncio.sleep(ms/1000)

# callback handlers

pub_q = []
def got_pub(msg):
    pub_q.append(msg)

puback_set = set()
def got_puback(pid):
    puback_set.add(pid)
suback_map = {}
def got_suback(pid, resp):
    suback_map[pid] = resp

async def wait_msg(mqc, op):
    t0 = ticks_ms()
    while ticks_diff(ticks_ms(), t0) < 1000:
        if await mqc.check_msg() == op: return

# Quick simple connection
async def test_simple():
    global pub_q, puback_set, suback_map
    print("=== test_simple starting")
    mqc = MQTTProto(got_pub, got_puback, got_suback)
    mqc.DEBUG=1
    # connect
    await mqc.connect(broker, cli_id, True)
    t0 = mqc.last_ack
    # try a ping
    await mqc.ping()
    await wait_msg(mqc, 0xd)
    if mqc.last_ack == t0:
        print("Error: did not receive ping response", mqc.last_req, mqc.last_ack)
    # subscribe at QoS=0
    topic = prefix + 'mirror'
    await mqc.subscribe(topic, 0, 123)
    await wait_msg(mqc, 9)
    if not 123 in suback_map:
        print("Error: did not receive suback @qos=0")
    elif not suback_map[123]:
        print("Error: subscribe rejected @qos=0")
    # publish to above topic using QoS=0
    await mqc.publish(MQTTMessage(topic, "hello"))
    await wait_msg(mqc, 3)
    if len(pub_q) != 1:
        print("Error: did not receive mirror pub @qos=0")
    elif pub_q[0].topic != topic.encode() or pub_q[0].message != "hello".encode() or \
            pub_q[0].retain != 0 or pub_q[0].qos != 0:
        print("Error: incorrect mirror topic @qos=0")
    pub_q = []
    # subscribe at QoS=1
    topic = prefix + 'mirror1'
    await mqc.subscribe(topic, 1, 124)
    await wait_msg(mqc, 9)
    if not 124 in suback_map:
        print("Error: did not receive suback @qos=1")
    elif not suback_map[124]:
        print("Error: subscribe rejected @qos=1")
    # publish to above topic using QoS=1
    await mqc.publish(MQTTMessage(topic, "hello", qos=1, pid=125))
    await wait_msg(mqc, 3)
    if len(pub_q) != 1:
        print("Error: did not receive mirror pub @qos=1")
    elif pub_q[0].topic != topic.encode() or pub_q[0].message != "hello".encode() or \
            pub_q[0].retain != 0 or pub_q[0].qos != 1:
        print("Error: incorrect mirror msg @qos=1", pub_q[0])
    if not 125 in puback_set:
        print("Error: did not receive puback @qos=1")
    # disconnect
    await mqc.disconnect()
    #
    print("test_simple done")

loop = asyncio.get_event_loop()
loop.run_until_complete(test_simple())

async def test_read_closed():
    global pub_q, puback_set, suback_map
    print("=== test_write_closed starting")
    mqc = MQTTProto(got_pub, got_puback, got_suback)
    mqc.DEBUG=1
    # connect
    await mqc.connect(broker, cli_id, True)
    # send garbage to cause the broker to close socket
    mqc._sock.send(b'\xf0\0')
    # see whether we get a reasonable error
    try:
        r = await mqc._as_read(2)
        print("Error: read on closed socket returned", r)
    except OSError as e:
        if e.args[0] != -1:
            print("Error: read on closed socket raised", e)
    #
    print("test_read_closed done")

loop.run_until_complete(test_read_closed())

async def test_write_closed():
    global pub_q, puback_set, suback_map
    print("=== test_write_closed starting")
    mqc = MQTTProto(got_pub, got_puback, got_suback)
    mqc.DEBUG=1
    # connect
    await mqc.connect(broker, cli_id, True)
    # explicitly close the socket
    mqc._sock.close()
    # see whether we get a reasonable error
    try:
        w = await mqc._as_write(b'\xf0Hello')
        print("Error: write on closed socket returned", w)
    except OSError as e:
        if e.args[0] != 9:
            print("Error: write on closed socket raised", e)
    #
    print("test_write_closed done")

loop.run_until_complete(test_write_closed())


