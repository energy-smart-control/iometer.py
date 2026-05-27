# IOmeter Python Client — Integration Reference

This document describes the `iometer` Python package. Use it as context when building or adapting a project that reads live energy data from an IOmeter bridge via Server-Sent Events (SSE).

---

## What this client does

The `IOmeterSSEClient` connects to an IOmeter bridge over HTTP and receives a continuous stream of energy meter readings via SSE. The bridge exposes two SSE endpoints:

- `GET /v1/reading` — live meter readings (energy counters, current power, per-phase power)
- `GET /v1/status` — device status (bridge, core module, battery, connectivity)

The client does **not** poll. It holds a persistent HTTP connection and yields events as they arrive. On connection loss it reconnects automatically with exponential backoff (1 s → 2 s → 4 s … capped at 30 s).

---

## Installation

```
pip install iometer
```

**Runtime dependency:** `aiohttp >=3.9`. No other dependencies required.

---

## Client lifecycle

The client is an async context manager. Always use it with `async with` so the underlying `aiohttp.ClientSession` is created and closed correctly.

```python
from iometer import IOmeterClient

async with IOmeterClient("192.168.1.100") as client:
    async for reading in client.watch_readings():
        ...
```

**Constructor parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `host` | `str` | required | IP or hostname of the IOmeter bridge |
| `request_timeout` | `int` | `60` | Seconds before the HTTP connection times out |
| `session` | `ClientSession \| None` | `None` | Inject an existing aiohttp session (optional) |

---

## Reading stream — `watch_readings()`

Returns an `AsyncGenerator[Reading, None]`. Yields one `Reading` object per SSE event of type `readingEvent`.

### Reading object

```python
reading.installation_id    # str  — UUID of the installation
reading.meter.number       # str  — meter serial number
reading.meter.reading.time # datetime (UTC, timezone-aware)
reading.meter.reading.registers  # List[Register]
```

Each `Register` has:
```python
register.obis   # str   — OBIS code
register.value  # float — measured value
register.unit   # str   — "Wh" or "W"
```

### Convenience methods on `Reading`

All return `float | None`. `None` means the OBIS code is absent in this meter's data.

| Method | OBIS | Unit | Notes |
|---|---|---|---|
| `get_total_consumption()` | `01-00:01.08.00*ff` | Wh | Cumulative consumption |
| `get_total_production()` | `01-00:02.08.00*ff` | Wh | Cumulative feed-in; `None` if meter does not support it |
| `get_current_power()` | `01-00:10.07.00*ff` | W | Falls back to `01-00:24.07.00*ff` if primary OBIS missing |
| `get_consumption_tariff_T1()` | `01-00:01.08.01*ff` | Wh | HT tariff; not all meters |
| `get_consumption_tariff_T2()` | `01-00:01.08.02*ff` | Wh | NT tariff; not all meters |
| `get_power_phase_L1()` | `01-00:24.07.00*ff` | W | 3-phase meters only |
| `get_power_phase_L2()` | `01-00:38.07.00*ff` | W | 3-phase meters only |
| `get_power_phase_L3()` | `01-00:4c.07.00*ff` | W | 3-phase meters only |

**Important:** `get_power_phase_L1()` and `get_current_power()` share the fallback OBIS `01-00:24.07.00*ff`. On single-phase meters that only report this code, both methods return the same value. On 3-phase meters that report `01-00:10.07.00*ff` (total) as well as the three phase codes, `get_current_power()` returns the total and `get_power_phase_L1/L2/L3()` return per-phase values.

---

## Status stream — `watch_status()`

Returns an `AsyncGenerator[Status, None]`. Yields one `Status` object per SSE event of type `statusEvent`.

### Status object

```python
status.installation_id          # str
status.meter.number             # str | None  (NullMeter if bridge has no meter yet)
status.device.id                # str  — bridge UUID
status.device.bridge.rssi       # int | None  — bridge WiFi signal strength (dBm)
status.device.bridge.version    # str | None  — bridge firmware version
status.device.core.connection_status   # str  — "connected" | "disconnected"
status.device.core.rssi                # int | None
status.device.core.version             # str | None  — core firmware version
status.device.core.power_status        # str | None  — "battery" | "wired"
status.device.core.battery_level       # int | None  — 0–100, only when power_status == "battery"
status.device.core.attachment_status   # str | None  — "attached" | "detached"
status.device.core.pin_status          # str | None  — "entered" | None
```

`status.meter` is a `NullMeter` (falsy, `number` is `None`) when the bridge has not yet paired with a meter. Always guard with `if status.meter:` before accessing meter data.

---

## Error handling

| Exception | When raised |
|---|---|
| `IOmeterTimeoutError` | `asyncio.TimeoutError` from the HTTP connection |
| `IOmeterNoReadingsError` | Bridge returns HTTP 404 on `/v1/reading` |
| `IOmeterNoStatusError` | Bridge returns HTTP 404 on `/v1/status` |
| `IOmeterConnectionError` | Generic connection failure |

Other HTTP errors and transient exceptions trigger silent reconnection with backoff — they are not raised to the caller.

```python
from iometer import IOmeterClient
from iometer.exceptions import IOmeterTimeoutError, IOmeterNoReadingsError

async with IOmeterClient(host) as client:
    try:
        async for reading in client.watch_readings():
            process(reading)
    except IOmeterTimeoutError:
        ...  # bridge unreachable
    except IOmeterNoReadingsError:
        ...  # bridge online but no meter paired
```

---

## Full usage example

```python
import asyncio
from iometer import IOmeterClient

async def main():
    async with IOmeterClient("192.168.1.100") as client:
        async for reading in client.watch_readings():
            print(f"Power:        {reading.get_current_power()} W")
            print(f"Consumption:  {reading.get_total_consumption()} Wh")
            print(f"Production:   {reading.get_total_production()} Wh")

            # 3-phase values (None on single-phase meters)
            l1 = reading.get_power_phase_L1()
            l2 = reading.get_power_phase_L2()
            l3 = reading.get_power_phase_L3()
            if l1 is not None:
                print(f"L1/L2/L3: {l1} W / {l2} W / {l3} W")

asyncio.run(main())
```

### Watching both streams concurrently

```python
import asyncio
from iometer import IOmeterClient

async def main():
    async with IOmeterClient("192.168.1.100") as client:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(watch_readings(client))
            tg.create_task(watch_status(client))

async def watch_readings(client):
    async for reading in client.watch_readings():
        ...

async def watch_status(client):
    async for status in client.watch_status():
        ...

asyncio.run(main())
```

---

## SSE wire format

The bridge sends standard SSE. Each event looks like:

```
event: readingEvent
data: {"__typename":"iometer.reading.v1","installationId":"...","meter":{...}}

event: statusEvent
data: {"__typename":"iometer.status.v1","installationId":"...","device":{...}}
```

The client filters by event type and passes only the `data` field to the parser. Unknown event types are silently ignored.

---

## Design constraints to keep in mind

- The client is **push-based**: your code must consume events as they arrive. Do not run blocking code inside the `async for` loop.
- `request_timeout` applies to the HTTP connection setup, not to the lifetime of the stream. The stream itself runs indefinitely.
- All data model classes (`Reading`, `Status`, `Register`, …) are frozen `dataclass` instances — treat them as immutable.
- The `iometer` package uses only `aiohttp` as a runtime dependency. Do not add `aiohttp-sse-client` or any other SSE library.
