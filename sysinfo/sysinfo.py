import micropython, gc, time, uasyncio as asyncio, logging

log = logging.getLogger(__name__)

_upticks = None  # milliseconds of uptime
_lastticks = None
_mqttconn = 0


async def info_sender(mqclient, topic, interval):
    global _upticks, _lastticks
    while True:
        try:
            f = gc.mem_free()
            mf = gc.mem_maxfree()
            t = time.ticks_ms()
            if _upticks is None:
                _upticks = t  # we hope is hasn't rolled-over yet...
            else:
                _upticks += time.ticks_diff(t, _lastticks)
            _lastticks = t
            # compose json message with data
            msg = '{"up":%d,"free":%d,"cont_free":%d,"mqtt_conn":%d}' % (
                _upticks // 1000,
                f,
                mf,
                _mqttconn,
            )
            log.info(msg)
            mqclient.publish(topic, msg, qos=0)
            # micropython.mem_info()
        except Exception as e:
            log.exc(e)
        await asyncio.sleep(interval)


async def _on_mqtt(conn):
    global _mqttconn
    if conn:
        _mqttconn += 1


def start(mqtt, config):
    topic = config["topic"]
    interval = config.get("interval", 60)  # interval in seconds

    async def on_connect(mqclient):
        asyncio.sleep(1)  # skip initial flurry of activity
        asyncio.get_event_loop().create_task(info_sender(mqclient, topic, interval))

    mqtt.on_connect(on_connect)
    mqtt.on_wifi(_on_mqtt)
