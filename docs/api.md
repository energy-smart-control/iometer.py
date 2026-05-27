# IOmeter Local API

## Introduction

### What is IOmeter?

IOmeter is an electronic product which makes electrical utility meter readings like power, energy consumption and energy production available via WIFI / LAN.

IOmeter consists of two devices:

- IOmeter Core: This device is attached to the utility meter and transmits the meter readings via a long range 868MHz RF link.
- IOmeter Bridge: This device receives the meter readings that have been sent by the IOmeter Core and makes them available to an IP network via 2.4GHz WIFI.

### Use Cases for IOmeter

IOmeter can be used to provide energy production and consumption data to other systems for display, billing and monitoring purposes.

The electrical power reading is in particular useful to control home battery storage systems and inverters so that those can control the charge and discharge power and most importantly prevent feeding electrical energy from a battery storage back to the grid.


## HTTP API

### Network Address

The API uses HTTP (not HTTPS) on port 80.
The address of the device can be found using [mDNS](https://en.wikipedia.org/wiki/Multicast_DNS). The fully qualified service type name is `_iometer._tcp.local.`

### Base URL

The current base URL is:
```
http://{device ip address}/v1
```

### Supported Protocols

The API can be polled.

The polling rate should be aligned with the configuration and the use case of IOmeter.

For example:

When IOmeter has been configured by the user to provide meter reading updates in a 1 second interval, then the polling interval of the reading endpoint should be one second too.

The status endpoint however can be polled in longer intervals because changes are not expected to happen very frequently. A good range is 10–30 s.

The API further supports SSE (Server-Sent Events). When using SSE, IOmeter will send an event whenever a value changes or a new reading arrives from the utility meter.

### Format

Responses are JSON encoded. Fields that are not available are omitted from the response. For example, if the electrical meter does not provide an energy production measurement then IOmeter will exclude that field from the JSON response.

The Simple Reading endpoint (`/v1/json`) is an exception: all fields are always present and default to `0` when the meter does not supply the underlying OBIS register.

### Endpoints

#### Meter Reading Endpoint

Request:

```http
GET /v1/reading
```

Response (Example):
```json
{
   "__typename": "iometer.reading.v1",
   "installationId": "22231002-eee7-41b3-ac68-6d90f4be5db0",
   "meter": {
      "number": "1ESY1161338362",
      "reading": {
         "time": "2026-03-13T14:20:24Z",
         "registers": [
            {
               "obis": "01-00:01.08.00*ff",
               "value": 6279091,
               "unit": "Wh"
            },
            {
               "obis": "01-00:10.07.00*ff",
               "value": 179.29,
               "unit": "W"
            },
            {
               "obis": "01-00:24.07.00*ff",
               "value": 179.29,
               "unit": "W"
            }
         ]
      }
   }
}
```

Fields

| Field | Type | Description |
| ----- | ---- | ----------- |
| __typename | string | Always `iometer.reading.v1` |
| installationId | string | Unique identifier of the IOmeter device setup |
| meter.number | string | Meter serial number |
| meter.reading.time | string | ISO 8601 timestamp of the reading |
| meter.reading.registers | array | List of registers provided by the utility meter, identified by OBIS code |

OBIS Codes

| OBIS Code | Description | Unit |
| ----------- | ----------- | ---- |
| 01-00:01.08.00*ff | Total energy consumption (all tariffs) | Wh |
| 01-00:01.08.01*ff | Energy consumption — tariff 1 | Wh |
| 01-00:01.08.02*ff | Energy consumption — tariff 2 | Wh |
| 01-00:02.08.00*ff | Total energy production (feed-in) | Wh |
| 01-00:10.07.00*ff | Current net power (positive = consumption, negative = feed-in) | W |
| 01-00:24.07.00*ff | Current power — phase L1 | W |
| 01-00:38.07.00*ff | Current power — phase L2 | W |
| 01-00:4C.07.00*ff | Current power — phase L3 | W |

#### Simple Reading Endpoint (EcoTracker format)

A compact, flat JSON format compatible with the [EcoTracker local API](https://everhome.cloud/en/developer/ecotracker). Designed for easy integration with home energy management systems and battery inverters that expect a simple numeric payload.

Request:

```http
GET /v1/json
```

Response (Example — 3-phase meter):
```json
{
   "power": 450.0,
   "powerAvg": 423.5,
   "powerPhase1": 180.0,
   "powerPhase2": 145.0,
   "powerPhase3": 125.0,
   "energyCounterIn": 6279091.0,
   "energyCounterInT1": 4100000.0,
   "energyCounterInT2": 2179091.0,
   "energyCounterOut": 312500.0
}
```

Response (Example — single-phase meter):
```json
{
   "power": 179.29,
   "powerAvg": 171.0,
   "powerPhase1": 179.29,
   "powerPhase2": 0.0,
   "powerPhase3": 0.0,
   "energyCounterIn": 6279091.0,
   "energyCounterInT1": 0.0,
   "energyCounterInT2": 0.0,
   "energyCounterOut": 0.0
}
```

Fields

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| power | number (W) | yes | Current net power. Positive = consumption, negative = feed-in |
| powerAvg | number (W) | yes | Average power over the last minute |
| powerPhase1 | number (W) | yes | Phase L1 power. Equals `power / 3` when no per-phase OBIS register is available |
| powerPhase2 | number (W) | yes | Phase L2 power. Equals `power / 3` when no per-phase OBIS register is available |
| powerPhase3 | number (W) | yes | Phase L3 power. Equals `power / 3` when no per-phase OBIS register is available |
| energyCounterIn | number (Wh) | yes | Cumulative energy consumption counter. `0` if not provided by the meter |
| energyCounterInT1 | number (Wh) | yes | Cumulative energy consumption — tariff 1. `0` if not provided |
| energyCounterInT2 | number (Wh) | yes | Cumulative energy consumption — tariff 2. `0` if not provided |
| energyCounterOut | number (Wh) | yes | Cumulative energy production (feed-in) counter. `0` if not provided |

OBIS-to-field mapping

| OBIS Code | JSON field |
| ----------- | ---------- |
| 01-00:10.07.00*ff | power |
| 01-00:24.07.00*ff | powerPhase1 |
| 01-00:38.07.00*ff | powerPhase2 |
| 01-00:4C.07.00*ff | powerPhase3 |
| 01-00:01.08.00*ff | energyCounterIn |
| 01-00:01.08.01*ff | energyCounterInT1 |
| 01-00:01.08.02*ff | energyCounterInT2 |
| 01-00:02.08.00*ff | energyCounterOut |

Phase power fallback behaviour

| Situation | powerPhase1 | powerPhase2 | powerPhase3 |
| --------- | ----------- | ----------- | ----------- |
| No phase OBIS codes available | power / 3 | power / 3 | power / 3 |
| All phase codes available | (meter value) | (meter value) | (meter value) |

`powerAvg` calculation

`powerAvg` is derived from the energy counter delta between consecutive readings:

```
powerAvg = (ΔenergyCounterIn − ΔenergyCounterOut) × 3600 / Δseconds
```

On the very first reading after device start, `powerAvg` equals the instantaneous `power` value because no previous reading is available yet.

#### IOmeter Status Endpoint

Get the current status of the IOmeter Bridge and IOmeter Core device.

Request

```http
GET /v1/status
```

Response Example

```json
{
   "__typename": "iometer.status.v1",
   "installationId": "22231002-eee7-41b3-ac68-6d90f4be5db0",
   "meter": {
      "number": "1ESY1161338362"
   },
   "device": {
      "bridge": {
         "rssi": -83,
         "version": "app:build-7, idf:v5.5.3"
      },
      "id": "f0f2d298-aa67-4b22-9d3d-f099eca3066f",
      "core": {
         "connectionStatus": "connected",
         "rssi": -75,
         "version": "build-76.8",
         "powerStatus": "battery",
         "batteryLevel": 100,
         "attachmentStatus": "attached",
         "pinStatus": "entered"
      }
   }
}
```

Fields

| Field | Type | Description |
| ----- | ---- | ----------- |
| __typename | string | Always `iometer.status.v1` |
| installationId | string | Unique identifier of the IOmeter device setup |
| meter.number | string | Meter serial number |
| device.bridge.rssi | integer? | WiFi signal strength in dBm (optional) |
| device.bridge.version | string? | IOmeter Bridge firmware version (optional) |
| device.id | string | Unique device identifier |
| device.core.connectionStatus | string | 868MHz RF link status (`connected`, `disconnected`) |
| device.core.rssi | integer? | 868MHz RF link signal strength in dBm (optional) |
| device.core.version | string? | IOmeter Core firmware version (optional) |
| device.core.powerStatus | string? | IOmeter Core power supply (`battery`, `wired`) (optional) |
| device.core.batteryLevel | integer? | Battery percentage 0–100, only present with battery power (optional) |
| device.core.attachmentStatus | string? | Whether IOmeter Core is attached to the optical port (`attached`, `detached`) (optional) |
| device.core.pinStatus | string? | Whether the utility meter PIN has been entered (`entered`, `pending`, `missing`) (optional) |

## UDP Multicast Transport

### Overview

In addition to the HTTP pull API, IOmeter can push meter readings and status updates to a **UDP multicast group**. This transport is useful when multiple consumers on the same LAN need to receive readings simultaneously without polling, or when a lightweight, connectionless receive loop is preferred.

The multicast transport is a pure push model: the device sends a datagram each time a new reading or status update is available. There is no request/response cycle, no delivery guarantee, and no ordering guarantee.

### Configuration

The multicast group address, port, TTL, and reading frequency are configured via **IOmeter provisioning** (the IOmeter cloud or local provisioning interface). A client cannot enable multicast by itself — it only needs to join the configured multicast group and listen.

Configuration parameters set on the device:

| Parameter | Description |
| --------- | ----------- |
| `ip_addr` | IPv4 multicast group address (e.g. `239.255.0.1`) |
| `port` | UDP destination port |
| `ttl` | IP multicast TTL — controls how many router hops the datagram may traverse (1 = link-local only) |
| `frequency` | Which reading frequency triggers a multicast send (matches the device's configured update rate) |

### Message Types

Two message types are sent via multicast. Both use the same JSON format as the corresponding HTTP endpoints:

| `__typename` | Equivalent HTTP endpoint | When sent |
| ------------ | ------------------------ | --------- |
| `iometer.reading.v1` | `GET /v1/reading` | On each meter reading at the configured frequency |
| `iometer.status.v1` | `GET /v1/status` | On every device status update |

The simple reading format (`/v1/json`) is **not** sent via multicast.

### Constraints

- Each message is a single UDP datagram. Maximum payload size is **1460 bytes**.
- UDP provides no delivery guarantee — datagrams may be lost or reordered.
- There is no keep-alive or heartbeat; silence on the socket does not indicate a device problem.
- The device must have WiFi connectivity; multicast is suspended when the device is disconnected.

### Receiving Multicast Messages

A receiver must join the multicast group on the relevant network interface before it will receive datagrams.

**Python example:**

```python
import socket
import struct
import json

MCAST_GRP = "239.255.0.1"   # must match device provisioning
MCAST_PORT = 5007            # must match device provisioning

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("", MCAST_PORT))

mreq = struct.pack("4sL", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

while True:
    data, addr = sock.recvfrom(2048)
    msg = json.loads(data.decode("utf-8"))
    typename = msg.get("__typename")
    if typename == "iometer.reading.v1":
        registers = msg.get("meter", {}).get("reading", {}).get("registers", [])
        print(f"Reading from {addr[0]}: {registers}")
    elif typename == "iometer.status.v1":
        print(f"Status from {addr[0]}: {msg}")
```

**socat one-liner (inspect raw datagrams):**

```bash
socat UDP4-RECVFROM:5007,ip-add-membership=239.255.0.1:0.0.0.0,fork -
```

### Message Examples

Reading message (same schema as `GET /v1/reading`):

```json
{
  "__typename": "iometer.reading.v1",
  "installationId": "22231002-eee7-41b3-ac68-6d90f4be5db0",
  "meter": {
    "number": "1ESY1161338362",
    "reading": {
      "time": "2026-03-13T14:20:24Z",
      "registers": [
        { "obis": "01-00:01.08.00*ff", "value": 6279091, "unit": "Wh" },
        { "obis": "01-00:10.07.00*ff", "value": 179.29, "unit": "W" }
      ]
    }
  }
}
```

Status message (same schema as `GET /v1/status`):

```json
{
  "__typename": "iometer.status.v1",
  "installationId": "22231002-eee7-41b3-ac68-6d90f4be5db0",
  "meter": { "number": "1ESY1161338362" },
  "device": {
    "bridge": { "rssi": -83, "version": "app:build-7, idf:v5.5.3" },
    "id": "f0f2d298-aa67-4b22-9d3d-f099eca3066f",
    "core": {
      "connectionStatus": "connected",
      "rssi": -75,
      "version": "build-76.8",
      "powerStatus": "battery",
      "batteryLevel": 100,
      "attachmentStatus": "attached",
      "pinStatus": "entered"
    }
  }
}
```

---

## CURL Example Requests

### Polling

```bash
# Get current reading (full OBIS format)
curl --url "http://192.168.1.100/v1/reading" \
  --header "Accept: application/json"

# Get current reading (EcoTracker simple format)
curl --url "http://192.168.1.100/v1/json" \
  --header "Accept: application/json"

# Get device status
curl --url "http://192.168.1.100/v1/status" \
  --header "Accept: application/json"
```

### SSE

```bash
# Subscribe to reading events (full OBIS format)
curl -N -H "Accept: text/event-stream" http://iometer-fc0804.local/v1/reading

# Subscribe to reading events (EcoTracker simple format)
curl -N -H "Accept: text/event-stream" http://iometer-fc0804.local/v1/json
```

SSE Response Example — full reading:

```
event: readingEvent
data: {"__typename":"iometer.reading.v1","installationId":"22231002-eee7-41b3-ac68-6d90f4be5db0","meter":{"number":"1ESY1161338362","reading":{"time":"2026-03-13T14:42:17Z","registers":[{"obis":"01-00:01.08.00*ff","value":6279149,"unit":"Wh"},{"obis":"01-00:10.07.00*ff","value":157.01,"unit":"W"},{"obis":"01-00:24.07.00*ff","value":157.01,"unit":"W"}]}}}

event: readingEvent
data: {"__typename":"iometer.reading.v1","installationId":"22231002-eee7-41b3-ac68-6d90f4be5db0","meter":{"number":"1ESY1161338362","reading":{"time":"2026-03-13T14:42:18Z","registers":[{"obis":"01-00:01.08.00*ff","value":6279150,"unit":"Wh"},{"obis":"01-00:10.07.00*ff","value":156.27,"unit":"W"},{"obis":"01-00:24.07.00*ff","value":156.27,"unit":"W"}]}}}
```

SSE Response Example — simple reading:

```
event: readingEvent
data: {"power":157.01,"powerAvg":155.0,"powerPhase1":157.01,"powerPhase2":0.0,"powerPhase3":0.0,"energyCounterIn":6279149.0,"energyCounterInT1":0.0,"energyCounterInT2":0.0,"energyCounterOut":0.0}

event: readingEvent
data: {"power":156.27,"powerAvg":154.8,"powerPhase1":156.27,"powerPhase2":0.0,"powerPhase3":0.0,"energyCounterIn":6279150.0,"energyCounterInT1":0.0,"energyCounterInT2":0.0,"energyCounterOut":0.0}
```
