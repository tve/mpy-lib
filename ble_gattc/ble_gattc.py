import bluetooth
import ubinascii as binascii
import uerrno as errno
import ustruct as struct
from micropython import const
from uasyncio import sleep_ms, Event, Loop
from ble_advertising import decode_services, decode_name

# This module provides a high-level interface to GATT characteristics of a remote device, such as
# a sensor. The way it works is that when BLEGATTC is instantiated a list of UUIDS for GATT
# Services of interest is passed in. These are the services the application will be using and
# BLEGATTC makes them available.
#
# Once BLEGATTC connects to a device, it queries the list of available services.
# For the services of interest it further queries all characteristics and their descriptors.
# The result is a hierarchy of BLEService, BLECharacteristic, and BLEDescriptor stored in
# BLEGATTC.services, indexed by UUID. This hierarchy of services/char's/descr's can then be
# used by the application to read/write/subscribe-to characteristics using the methods on
# BLECharacteristic.
#
# In order to establish a connection to a device there are two options. The first is to perform a
# scan, for which the application passes a filter callback, which is called for each device found
# and which needs to return True to select the current device or False to continue scanning. The
# second is to call connect with previously saved address (not tested, dunno whether this actually
# works!).
#
# Currently all char's and descr's are discovered and stored for all services of interest. In the
# future, it might be useful to further limit what gets stored to reduce memory consumption by
# enhancing the services parameter to the BLEGATTC constructor.
#
# BLEGATTC requires the use of asyncio. The scan and connect methods are async and block until
# scanning, connecting, and discovery have all completed. Reading a char is also an async method
# and a subscription on a char returns a queue getter, which is an async function that returns
# the next notified value when it is available.
#
# Errors are signaled by having (async) methods raise an OSError with an appropriate error number.
#
# Implementation notes:
# - The discovery process operates in rounds. First all services are discovered. Then all
# characteristics, then all descriptors. It is not possible to start discovering the chars of the
# first service at the same time as the service discovery continues. Same for discovering
# descriptors.

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)
_IRQ_PERIPHERAL_CONNECT = const(7)
_IRQ_PERIPHERAL_DISCONNECT = const(8)
_IRQ_GATTC_SERVICE_RESULT = const(9)
_IRQ_GATTC_SERVICE_DONE = const(10)
_IRQ_GATTC_CHARACTERISTIC_RESULT = const(11)
_IRQ_GATTC_CHARACTERISTIC_DONE = const(12)
_IRQ_GATTC_DESCRIPTOR_RESULT = const(13)
_IRQ_GATTC_DESCRIPTOR_DONE = const(14)
_IRQ_GATTC_READ_RESULT = const(15)
_IRQ_GATTC_READ_DONE = const(16)
_IRQ_GATTC_WRITE_DONE = const(17)
_IRQ_GATTC_NOTIFY = const(18)
_IRQ_GATTC_INDICATE = const(19)

_ADV_IND = const(0x00)
_ADV_DIRECT_IND = const(0x01)
_ADV_SCAN_IND = const(0x02)
_ADV_NONCONN_IND = const(0x03)


# BLEService describes a discovered service of a BLEGATTC.
class BLEService:
    def __init__(self, start_handle, end_handle):
        self._start_handle = start_handle
        self._end_handle = end_handle
        # public attributes
        self.chars = {}  # BLECharacteristics indexed by UUID


# BLECharacteristic describes a characteristic of a BLEService and provides methods to read/write
# the value as well as subscribe to notifications.
class BLECharacteristic:
    def __init__(self, gattc, def_handle, value_handle, properties):
        self._gattc = gattc  # parent BLEGATTC
        self._def_handle = def_handle  # ?
        self._value_handle = value_handle  # handle used to read/write value
        self._end_handle = None  # last handle for characteristic (crazy stuff!)
        # public attributes
        self.properties = properties  # ?
        self.descriptors = {}  # BLEDescriptors indexed by UUID

    # Read the value
    async def read(self):
        gattc = self._gattc
        e = gattc._add_pending(self._value_handle)
        gattc._ble.gattc_read(gattc._conn_handle, self._value_handle)
        return await e.get()

    # Write the value
    def write(self, v, response=False):
        if not self.is_connected():
            return
        gattc = self._gattc
        gattc._ble.gattc_write(gattc._conn_handle, self._value_handle, v, 1 if response else 0)

    CCC_UUID = bluetooth.UUID(0x2902)  # client characteristic configuration descriptor

    # Subscribe to notifications
    def subscribe(self, qlen=2):
        if self.CCC_UUID in self.descriptors:
            gattc = self._gattc
            e = gattc._add_pending(self._value_handle)
            vh = self.descriptors[self.CCC_UUID]._value_handle
            gattc._ble.gattc_write(gattc._conn_handle, vh, b'\x01\x00', 0)
            return e.get  # returning the method itself
        else:
            print("No CCC descriptor?", self.descriptors)
            raise OSError(errno.ENOENT)


# BLEDescriptor describes a descriptor of a BLECharacteristic and provides methods to read and
# write the value.
class BLEDescriptor:
    def __init__(self, conn_handle, value_handle):
        self._conn_handle = conn_handle
        self._value_handle = value_handle  # handle used to read/write value

    # Read the value
    def read(self, callback):
        pass

    # Write the value
    def write(self, v, response=False):
        if not self.is_connected():
            return
        conn = self.parent.parent._conn_handle
        self._ble.gattc_write(conn, self._value_handle, v, 1 if response else 0)


# Pending ...
class Pending:
    def __init__(self):
        self._ev = Event()
        self._res = None

    async def get(self):
        await self._ev.wait()
        self._ev.clear()  # TODO: race condition?
        if isinstance(self._res, OSError):
            raise self._res
        else:
            return self._res

    def signal(self, result):
        self._res = result
        self._ev.set()


# BLEGATTC provides means to discover, read, write a simple BLE GATT device.
class BLEGATTC:
    EV_CONN = -1  # special event type representing connection to the device

    # init bluetooth and get it ready to scan or connect. services is the list of UUIDs for the
    # services that should be discovered, i.e., that the application will be using. Services of the
    # device that are not in this list will not be usable. (If the device doesn't implement one of
    # the listed services that's OK.)
    # Example: BLEGATTC(bluetooth.BLE(), [bluetooth.UUID(0x180F)])
    def __init__(self, ble, services):
        self._ble = ble
        self._ble.active(True)
        self._ble.irq(self._irq)
        self._svc_uuids = services

        self._reset()

    def _reset(self, error=None):
        # Info about sensor device
        self._name = None  # name of device/service we find
        self._addr_type = None  # address type of tgt device
        self._addr = None  # address of tgt device

        # Events.
        if error:
            for _, e in self._pending.items():
                e.signal(error)
        self._pending = {}  # pending async events
        self._filter_callback = None  # used during scanning to filter devices found

        # Connected device.
        self._conn_handle = None
        self._cur_svc = None  # current service during char discovery
        self._cur_char = None  # current char during dsc discovery
        self._prev_char = None  # previous char during char discovery
        self._char_list = []  # list of BLECharacteristic queued for descriptor discovery
        self._ready = False  # ready when discovery is complete and a connection is made

        # Public attributes
        self.services = {}  # services available on this device (filtered by _svc_uuids)

    # _discover_chars is a helper that kicks off the discovery of characteristics for the next
    # "undiscovered" service. Returns True iff discovery got kicked off.
    def _discover_chars(self):
        while len(self._svc_uuids) > 0:
            uuid = self._svc_uuids.pop(0)  # next service is the list of interest
            svc = self.services.get(uuid, None)  # see whether the device provides it
            if svc:
                sh = svc._start_handle
                eh = svc._end_handle
                self._cur_svc = uuid
                print("Discovering service", uuid)
                self._ble.gattc_discover_characteristics(self._conn_handle, sh, eh)
                return True

    # _discover_dscs is a helper that kicks off the discovery of descriptors for the next
    # "undiscovered" characteristic. Returns True iff discovery got kicked off.
    def _discover_dscs(self):
        while len(self._char_list) > 0:
            char = self._char_list.pop(0)
            vh = char._value_handle
            eh = char._end_handle
            if eh > vh:
                # Looks like this char has dscs, discover 'em.
                # print("disc_dsc:", vh, eh)
                self._ble.gattc_discover_descriptors(self._conn_handle, vh, eh)
                self._cur_char = char
                return True

    # _add_pending is a helper to register an awaited event / response.
    def _add_pending(self, match_handle):
        entry = Pending()
        self._pending[match_handle] = entry
        return entry

    # _connect is a helper to initiate a connection to the specified device.
    def _connect(self, addr_type=None, addr=None):
        self._addr_type = addr_type or self._addr_type
        self._addr = addr or self._addr
        print("Connecting to", binascii.hexlify(self._addr, ":").decode("ascii"))
        self._ble.gap_connect(self._addr_type, self._addr)

    # _irq is the callback invoked by BLE when a response comes in, it's a big switch statement to
    # process the information and possibly to kick off the next action.
    # It is invoked in MP schedule (softIRQ) context.
    # Note that the `data` tuple may contain references that point into a transient byte array and
    # thus anything that is not a primitive value has to be copied if it's saved away.
    def _irq(self, event, data):
        #print("IRQ", event)
        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data
            if adv_type in (_ADV_IND, _ADV_DIRECT_IND):  # magic??
                name = decode_name(adv_data)
                services = decode_services(adv_data)
                print("Scan found", name, services)
                # ask the filter callback whether this is our device
                if self._filter_callback(addr_type, addr, name, services):
                    # looks like we found something...
                    self._addr_type = addr_type  # 0=public, 1=randomized
                    self._addr = bytes(addr)  # addr buffer is owned by caller: need to copy it.
                    self._name = decode_name(adv_data) or "?"  # decode_name makes a copy
                    self._ble.gap_scan(None)  # stop scanning

        elif event == _IRQ_SCAN_DONE:
            if self._addr:
                # Found a device during the scan.
                print("Scan done, found device")
                self._connect()  # connect to the device found
            else:
                # Scan timed out.
                print("Scan done, timed-out")
                self._reset(OSError(errno.ETIMEDOUT))

        elif event == _IRQ_PERIPHERAL_CONNECT:
            # Connect successful.
            conn_handle, addr_type, addr = data
            if addr_type == self._addr_type and addr == self._addr:
                print("Connected", data)
                self._conn_handle = conn_handle
                self._ble.gattc_discover_services(self._conn_handle)  # start services discovery

        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            # Disconnect (either initiated by us or the remote end).
            conn_handle, _, _ = data
            if conn_handle == self._conn_handle:
                # Not reset by us.
                self._reset(OSError(errno.EV_CONNABORTED))

        elif event == _IRQ_GATTC_SERVICE_RESULT:
            # Connected device returned a service.
            conn_handle, start_handle, end_handle, uuid = data
            print("Found service:", data)
            if conn_handle == self._conn_handle and uuid in self._svc_uuids:
                # That's a service we need to pay attention to.
                self.services[bluetooth.UUID(uuid)] = BLEService(start_handle, end_handle)

        elif event == _IRQ_GATTC_SERVICE_DONE:
            # Service query complete, fetch characteristics of the services we're looking for.
            conn_handle, status = data
            if conn_handle != self._conn_handle:
                return
            # Start querying for characteristics.
            print("Found %d services, %d to discover" % (len(self.services), len(self._svc_uuids)))
            if not self._discover_chars():
                print("No services to discover?")
                self._reset(OSError(errno.ENOENT))

        elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
            # Connected device returned a characteristic.
            conn_handle, def_handle, value_handle, properties, uuid = data
            if conn_handle != self._conn_handle:
                return
            print("Found char:", data)
            uuid = bluetooth.UUID(uuid)  # make copy.
            char = BLECharacteristic(self, def_handle, value_handle, properties)
            svc = self.services[self._cur_svc]
            svc.chars[uuid] = char
            self._char_list.append(char)  # queue to discover descriptors
            # fix up end_handle of previous char (yuck!!)
            if self._prev_char:
                self._prev_char._end_handle = def_handle - 1
            self._prev_char = char

        elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
            # Characteristic query complete, see whether we need to query for more.
            conn_handle, status = data
            if conn_handle != self._conn_handle:
                return
            # fix up end_handle of last char (yuck!!)
            if self._prev_char:
                self._prev_char._end_handle = self.services[self._cur_svc]._end_handle
            self._prev_char = None
            # Query for char's of other services
            if not self._discover_chars():
                # Start querying for descriptors.
                print("Dicovering dscs for %d chars" % len(self._char_list))
                if not self._discover_dscs():
                    print("Done with discovery")
                    self._cur_svc = None
                    self._cur_char = None
                    self._ready = True
                    self._pending[self.EV_CONN].signal(status)  # TODO: what's status?

        elif event == _IRQ_GATTC_DESCRIPTOR_RESULT:
            # Connected device returned a descriptor.
            conn_handle, value_handle, uuid = data
            if conn_handle != self._conn_handle:
                return
            print("Descriptor:", data)
            uuid = bluetooth.UUID(uuid)  # make copy.
            dsc = BLEDescriptor(conn_handle, value_handle)
            self._cur_char.descriptors[uuid] = dsc

        elif event == _IRQ_GATTC_DESCRIPTOR_DONE:
            # Descriptor query complete, see whether we need to query for more.
            conn_handle, status = data
            if conn_handle != self._conn_handle:
                return
            # Continue querying for descriptors.
            if not self._discover_dscs():
                print("Done with discovery")
                self._cur_svc = None
                self._cur_char = None
                self._ready = True
                self._pending[self.EV_CONN].signal(status)  # TODO: what's status?

        elif event == _IRQ_GATTC_READ_RESULT:
            # A read completed successfully.
            conn_handle, value_handle, char_data = data
            if conn_handle == self._conn_handle:
                self._pending[value_handle].signal(char_data)
                del self._pending[value_handle]

        elif event == _IRQ_GATTC_WRITE_DONE:
            conn_handle, value_handle, status = data
            if conn_handle == self._conn_handle:
                self._pending[value_handle].signal(status)  # TODO: what's status?
                del self._pending[value_handle]

        elif event == _IRQ_GATTC_NOTIFY:
            conn_handle, value_handle, notify_data = data
            if conn_handle == self._conn_handle:
                self._pending[value_handle].signal(notify_data)

    # is_connected returns True iff there is an active connection to a device and the discovery
    # process has completed, i.e. the device is usable.
    def is_connected(self):
        return self._conn_handle is not None and self._ready

    async def connect(self, addr_type, addr):
        # TODO: raise error if we're already scanning, connected, etc...
        e = self._add_pending(self.EV_CONN)
        self._connect(addr_type, addr)
        await e.get()  # TODO: discard status?

    # scan is an async method that scans for a device and then connects to it.
    # The filter callback is invoked during scanning with name, addr_type, addr and services.
    # The services field of the tuple is an array of service UUIDs advertised by the device.
    # The callback should return True if the device is the one to use and False if scanning
    # should continue.
    # scan returns a (name, addr_type, addr) tuple for the connected device.
    async def scan(self, filter_cb):
        # TODO: raise error if we're already scanning, connected, etc...
        self._filter_callback = filter_cb
        e = self._add_pending(self.EV_CONN)
        self._addr_type = None
        self._addr = None
        self._ble.gap_scan(2000, 30000, 30000)
        await e.get()  # TODO: discard status?
        return (self._name, self._addr_type, self._addr)

    # Terminate disconnects from any device and terminates any pending operations.
    def terminate(self):
        if not self._conn_handle:
            return  # already terminated
        ch = self._conn_handle
        self._conn_handle = None
        self._ble.gap_disconnect(ch)
        self._reset(OSError(errno.ENOTCONN))

    # find a service, or characteristic, or descriptor based on a path of UUIDs.
    # Returns None if not found.
    def find(self, service, char=None, dsc=None):
        s = self.services.get(service, None)
        if s and char is not None:
            c = s.chars.get(char, None)
            if c and dsc is not None:
                return c.descriptors[dsc]
            return c
        return s


async def demo():
    BLE_HR_UUID = bluetooth.UUID(0x180D)
    BLE_HR_LOC_UUID = bluetooth.UUID(0x2A38)
    BLE_HR_MEAS_UUID = bluetooth.UUID(0x2A37)
    BLE_BATTERY_UUID = bluetooth.UUID(0x180F)
    BLE_BATTERY_LEVEL_UUID = bluetooth.UUID(0x2A19)

    ble = bluetooth.BLE()
    hr_sensor = BLEGATTC(ble, [BLE_HR_UUID, BLE_BATTERY_UUID])

    def scan_filter(addr_type, addr, name, services):
        return BLE_HR_UUID in services

    while True:
        print("Scanning...")
        try:
            name, addr_type, addr = await hr_sensor.scan(scan_filter)
        except OSError as e:
            print("Scanning failed (%s), retrying!" % e)
            await sleep_ms(500)
            continue
        addr = binascii.hexlify(addr, ":").decode("ascii")
        print("Found '%s' at %s" % (name, addr))

        try:
            # read battery level
            batt = hr_sensor.find(BLE_BATTERY_UUID, BLE_BATTERY_LEVEL_UUID)
            if batt:
                print("Connected, reading battery level")
                val = await batt.read()
                val = struct.unpack("<b", val)[0]
                print("Battery level: %d%%" % val)
            else:
                print("Connected, cannot read battery level")

            # read heart rate sensor type
            hr_loc = hr_sensor.find(BLE_HR_UUID, BLE_HR_LOC_UUID)
            if hr_loc:
                val = await hr_loc.read()
                val = struct.unpack("<b", val)[0]  # TODO: not meaningful...
                print("HR sensor location:", val)
            else:
                print("HR sensor location unavailable")

            # subscribe to HR measurements
            hr_meas = hr_sensor.find(BLE_HR_UUID, BLE_HR_MEAS_UUID)
            if hr_meas:
                hrm_q = hr_meas.subscribe()
                print("Subscribed to HR measurements")
            else:
                print("HR sensor measurements unavailable")
                hr_sensor.terminate()
                await sleep_ms(5000)
                continue  # try our luck yet again?

            while True:
                val = await hrm_q()
                print(val)
                if val[0] & 1:
                    hr = struct.unpack("<H", val[1:3])[0]
                else:
                    hr = struct.unpack("<B", val[1:2])[0]
                print("HR measurement: %dbpm (0x%02x)" % (hr, val[0]))

        except OSError as e:
            print("Sensor connection failed:", e, "- reconnecting...")
            hr_sensor.terminate()
            sleep_ms(500)


# Dummy task needed to keep the asyncio loop going in v1.13!?
async def ticker():
    while True:
        await sleep_ms(100)


if __name__ == "__main__":
    Loop.create_task(ticker())
    Loop.run_until_complete(demo())
