# IOmeter Python Client

A Python client for interacting with [IOmeter](https://iometer.de/) devices over HTTP. This client provides an async interface for reading energy consumption/production data and monitoring device status.

## Features

- 🔌 Asynchronous communication with IOmeter bridge over HTTP
- 📊 Read energy consumption and energy production data
- 🔋 Monitor device status including battery level and signal strength
- 🔄 Two transport modes: polling (`IOmeterClient`) and Server-Sent Events (`IOmeterSSEClient`)

## Quick Start

### Installation

```bash
pip install iometer
```

### Polling

Use `IOmeterClient` to fetch readings on demand:

```python
from iometer import IOmeterClient

async def check_meter_reading():
    async with IOmeterClient("192.168.1.100") as client:
        reading = await client.get_current_reading()
        print(f"Consumption: {reading.get_total_consumption()} Wh")
        print(f"Production: {reading.get_total_production()} Wh")
        print(f"Current Power: {reading.get_current_power()} W")
```

### Server-Sent Events (SSE)

Use `IOmeterSSEClient` to receive readings as they arrive (push-based):

```python
from iometer import IOmeterSSEClient
from aiohttp import ClientSession

async def stream_readings():
    async with ClientSession() as session:
        client = IOmeterSSEClient("192.168.1.100", session=session)
        async for reading in client.watch_readings():
            print(f"Consumption: {reading.get_total_consumption()} Wh")
            print(f"Current Power: {reading.get_current_power()} W")
```
### Device Status Information

```python
from iometer import IOmeterClient

async def check_device_status():
    async with IOmeterClient("192.168.1.100") as client:
        # Get current status
        status = await client.get_current_status()
        
        # Bridge information
        print(f"Bridge Version: {status.device.bridge.version}")
        print(f"Bridge Signal: {status.device.bridge.rssi} dBm")
        
        # Core information
        core = status.device.core
        print(f"Connection: {core.connection_status}")
        print(f"Power Mode: {core.power_status}")
        
        if core.power_status.value == "battery":
            print(f"Battery Level: {core.battery_level}%")
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Setting up a dev environment
We use [Poetry](https://python-poetry.org/) for dependency management and testing. Install everything with:
```bash
poetry install
```

To run the Python tests use:
```bash
poetry run pytest tests/test.py
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
