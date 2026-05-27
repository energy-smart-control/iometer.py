"""Tests for the IOmeter package."""

import pytest
import json
from aiohttp import ClientSession

from iometer.client import IOmeterSSEClient
from iometer.exceptions import (
    IOmeterConnectionError,
    IOmeterNoReadingsError,
    IOmeterNoStatusError,
    IOmeterTimeoutError,
)
from iometer.reading import Reading
from iometer.status import NullMeter, Status

HOST = "192.168.188.104"
INSTALLATION_ID = "22231002-eee7-41b3-ac68-6d90f4be5db0"


@pytest.fixture(name="reading_json")
def reading_json_fixture():
    """Fixture reading response."""
    return {
        "__typename": "iometer.reading.v1",
        "installationId": INSTALLATION_ID,
        "meter": {
            "number": "1ISK0000000000",
            "reading": {
                "time": "2024-11-11T11:11:11Z",
                "registers": [
                    {"obis": "01-00:01.08.00*ff", "value": 1234.5, "unit": "Wh"},
                    {"obis": "01-00:02.08.00*ff", "value": 5432.1, "unit": "Wh"},
                    {"obis": "01-00:10.07.00*ff", "value": 100, "unit": "W"},
                ],
            },
        },
    }


@pytest.fixture(name="reading_alt_obis_json")
def reading_alt_obis_json_fixture():
    """Fixture reading response with alternate current power OBIS only."""
    return {
        "__typename": "iometer.reading.v1",
        "installationId": INSTALLATION_ID,
        "meter": {
            "number": "1ISK0000000000",
            "reading": {
                "time": "2024-11-11T11:11:11Z",
                "registers": [
                    {"obis": "01-00:01.08.00*ff", "value": 1234.5, "unit": "Wh"},
                    {"obis": "01-00:02.08.00*ff", "value": 5432.1, "unit": "Wh"},
                    {"obis": "01-00:24.07.00*ff", "value": 100, "unit": "W"},
                ],
            },
        },
    }


@pytest.fixture(name="reading_no_power_obis_json")
def reading_no_power_obis_json_fixture():
    """Fixture reading response without any current power OBIS registers."""
    return {
        "__typename": "iometer.reading.v1",
        "installationId": INSTALLATION_ID,
        "meter": {
            "number": "1ISK0000000000",
            "reading": {
                "time": "2024-11-11T11:11:11Z",
                "registers": [
                    {"obis": "01-00:01.08.00*ff", "value": 1234.5, "unit": "Wh"},
                    {"obis": "01-00:02.08.00*ff", "value": 5432.1, "unit": "Wh"},
                ],
            },
        },
    }


@pytest.fixture(name="reading_no_power_no_production_obis_json")
def reading_no_power_no_production_obis_json_fixture():
    """Fixture reading response without any current power OBIS
    and production OBIS register.
    """
    return {
        "__typename": "iometer.reading.v1",
        "installationId": INSTALLATION_ID,
        "meter": {
            "number": "1ISK0000000000",
            "reading": {
                "time": "2024-11-11T11:11:11Z",
                "registers": [
                    {"obis": "01-00:01.08.00*ff", "value": 1234.5, "unit": "Wh"}
                ],
            },
        },
    }


@pytest.fixture(name="status_json")
def status_json_fixture():
    """ "Fixture status response"""
    return {
        "__typename": "iometer.status.v1",
        "installationId": INSTALLATION_ID,
        "meter": {
            "number": "1ISK0000000000",
        },
        "device": {
            "bridge": {"rssi": -30, "version": "build-65"},
            "id": "658c2b34-2017-45f2-a12b-731235f8bb97",
            "core": {
                "connectionStatus": "connected",
                "rssi": -30,
                "version": "build-58",
                "powerStatus": "battery",
                "batteryLevel": 100,
                "attachmentStatus": "attached",
                "pinStatus": "entered",
            },
        },
    }


@pytest.fixture(name="status_wired_json")
def status_wired_json_fixture():
    """ "Fixture status response with wired power"""
    return {
        "__typename": "iometer.status.v1",
        "installationId": INSTALLATION_ID,
        "meter": {
            "number": "1ISK0000000000",
        },
        "device": {
            "bridge": {"rssi": -30, "version": "build-65"},
            "id": "658c2b34-2017-45f2-a12b-731235f8bb97",
            "core": {
                "connectionStatus": "connected",
                "rssi": -30,
                "version": "build-58",
                "powerStatus": "wired",
                "attachmentStatus": "attached",
                "pinStatus": "entered",
            },
        },
    }


@pytest.fixture(name="status_detached_json")
def status_detached_json_fixture():
    """ "Fixture status response with detached core"""
    return {
        "__typename": "iometer.status.v1",
        "installationId": INSTALLATION_ID,
        "meter": {
            "number": "1ISK0000000000",
        },
        "device": {
            "bridge": {"rssi": -30, "version": "build-65"},
            "id": "658c2b34-2017-45f2-a12b-731235f8bb97",
            "core": {
                "connectionStatus": "connected",
                "rssi": -30,
                "version": "build-58",
                "powerStatus": "wired",
                "attachmentStatus": "detached",
            },
        },
    }


@pytest.fixture(name="status_disconnected_json")
def status_disconnected_json_fixture():
    """ "Fixture status response with disconnected core"""
    return {
        "__typename": "iometer.status.v1",
        "installationId": INSTALLATION_ID,
        "meter": {
            "number": "1ISK0000000000",
        },
        "device": {
            "bridge": {"rssi": -30, "version": "build-65"},
            "id": "658c2b34-2017-45f2-a12b-731235f8bb97",
            "core": {"connectionStatus": "disconnected"},
        },
    }


@pytest.fixture(name="status_no_meter_json")
def status_no_meter_json_fixture():
    """ "Fixture status response without meter"""
    return {
        "__typename": "iometer.status.v1",
        "installationId": INSTALLATION_ID,
        "device": {
            "bridge": {"rssi": -30, "version": "build-65"},
            "id": "658c2b34-2017-45f2-a12b-731235f8bb97",
            "core": {
                "connectionStatus": "connected",
                "rssi": -30,
                "version": "build-58",
                "powerStatus": "battery",
                "batteryLevel": 100,
                "attachmentStatus": "attached",
            },
        },
    }


@pytest.fixture(name="client_iometer")
async def client_iometer_fixture():
    """Fixture IOmeter client"""
    async with IOmeterSSEClient(HOST) as client:
        yield client


@pytest.mark.asyncio
async def test_client_initialization():
    """Test client initialization."""
    client = IOmeterSSEClient("test-host")
    assert client.host == "test-host"
    assert client.request_timeout == 60
    assert client.session is None


@pytest.mark.asyncio
async def test_client_context_manager():
    """Test client as context manager."""
    async with IOmeterSSEClient("test-host") as client:
        assert isinstance(client.session, ClientSession)
        assert not client.session.closed

    assert client.session is None


@pytest.mark.asyncio
async def test_watch_readings(client_iometer, reading_json):
    """Test watching readings."""
    async def mock_stream(*args, **kwargs):
        yield json.dumps(reading_json)

    client_iometer._stream = mock_stream

    async for reading in client_iometer.watch_readings():
        assert isinstance(reading, Reading)
        assert reading.installation_id == INSTALLATION_ID
        assert reading.meter.number == "1ISK0000000000"
        assert reading.get_total_consumption() == 1234.5
        assert reading.get_total_production() == 5432.1
        assert reading.get_current_power() == 100
        break

@pytest.mark.asyncio
async def test_watch_readings_alt_obis(client_iometer, reading_alt_obis_json):
    """Test current power using alternate OBIS when primary is missing."""
    async def mock_stream(*args, **kwargs):
        yield json.dumps(reading_alt_obis_json)

    client_iometer._stream = mock_stream
    async for reading in client_iometer.watch_readings():
        assert isinstance(reading, Reading)
        assert reading.get_current_power() == 100
        break


@pytest.mark.asyncio
async def test_watch_readings_no_power_obis(client_iometer, reading_no_power_obis_json):
    """Test current power returns None when no power OBIS registers are present."""
    async def mock_stream(*args, **kwargs):
        yield json.dumps(reading_no_power_obis_json)

    client_iometer._stream = mock_stream
    async for reading in client_iometer.watch_readings():
        assert isinstance(reading, Reading)
        assert reading.get_current_power() is None
        assert reading.get_total_production() == 5432.1
        assert reading.get_total_consumption() == 1234.5
        break


@pytest.mark.asyncio
async def test_watch_readings_no_power_no_production_obis(client_iometer, reading_no_power_no_production_obis_json):
    """Test current power returns None when no power OBIS registers are present."""
    async def mock_stream(*args, **kwargs):
        yield json.dumps(reading_no_power_no_production_obis_json)

    client_iometer._stream = mock_stream
    async for reading in client_iometer.watch_readings():
        assert isinstance(reading, Reading)
        assert reading.get_current_power() is None
        assert reading.get_total_production() is None
        assert reading.get_total_consumption() == 1234.5
        break


@pytest.mark.asyncio
async def test_watch_status(client_iometer, status_json):
    """Test watching status updates."""

    async def mock_stream(*args, **kwargs):
        yield json.dumps(status_json)

    client_iometer._stream = mock_stream
    async for status in client_iometer.watch_status():
        assert isinstance(status, Status)
        assert status.installation_id == INSTALLATION_ID
        assert status.meter.number == "1ISK0000000000"
        assert status.device.bridge.rssi == -30
        assert status.device.bridge.version == "build-65"
        assert status.device.core.power_status == "battery"
        assert status.device.core.battery_level == 100
        assert status.device.core.attachment_status == "attached"
        assert status.device.core.pin_status == "entered"
        break


@pytest.mark.asyncio
async def test_watch_status_wired(client_iometer, status_wired_json):
    """Test watching status updates."""

    async def mock_stream(*args, **kwargs):
        yield json.dumps(status_wired_json)

    client_iometer._stream = mock_stream
    async for status in client_iometer.watch_status():
        assert isinstance(status, Status)
        assert status.meter.number == "1ISK0000000000"
        assert status.device.bridge.rssi == -30
        assert status.device.bridge.version == "build-65"
        assert status.device.id == "658c2b34-2017-45f2-a12b-731235f8bb97"
        assert status.device.core.connection_status == "connected"
        assert status.device.core.rssi == -30
        assert status.device.core.version == "build-58"
        assert status.device.core.power_status == "wired"
        assert status.device.core.battery_level is None
        assert status.device.core.attachment_status == "attached"
        assert status.device.core.pin_status == "entered"
        break


@pytest.mark.asyncio
async def test_get_watch_status_detached(client_iometer, status_detached_json):
    """Test getting device status."""

    async def mock_stream(*args, **kwargs):
        yield json.dumps(status_detached_json)

    client_iometer._stream = mock_stream
    async for status in client_iometer.watch_status():
        assert isinstance(status, Status)
        assert status.device.id == "658c2b34-2017-45f2-a12b-731235f8bb97"
        assert status.device.core.connection_status == "connected"
        assert status.device.core.rssi == -30
        assert status.device.core.version == "build-58"
        assert status.device.core.power_status == "wired"
        assert status.device.core.battery_level is None
        assert status.device.core.attachment_status == "detached"
        assert status.device.core.pin_status is None
        break


@pytest.mark.asyncio
async def test_get_watch_status_disconnected(client_iometer, status_disconnected_json):
    """Test getting device status."""

    async def mock_stream(*args, **kwargs):
        yield json.dumps(status_disconnected_json)

    client_iometer._stream = mock_stream
    async for status in client_iometer.watch_status():
        assert isinstance(status, Status)
        assert status.device.bridge.rssi == -30
        assert status.device.bridge.version == "build-65"
        assert status.device.id == "658c2b34-2017-45f2-a12b-731235f8bb97"
        assert status.device.core.connection_status == "disconnected"
        assert status.device.core.rssi is None
        assert status.device.core.version is None
        assert status.device.core.power_status is None
        assert status.device.core.battery_level is None
        assert status.device.core.attachment_status is None
        assert status.device.core.pin_status is None
        break


@pytest.mark.asyncio
async def test_get_watch_status_no_meter(client_iometer, status_no_meter_json):
    """Test getting device status."""

    async def mock_stream(*args, **kwargs):
        yield json.dumps(status_no_meter_json)

    client_iometer._stream = mock_stream
    async for status in client_iometer.watch_status():
        assert isinstance(status, Status)
        assert isinstance(status.meter, NullMeter)
        assert status.meter.number is None
        assert status.device.bridge.rssi == -30
        assert status.device.bridge.version == "build-65"
        assert status.device.id == "658c2b34-2017-45f2-a12b-731235f8bb97"
        assert status.device.core.connection_status == "connected"
        assert status.device.core.rssi == -30
        assert status.device.core.version == "build-58"
        assert status.device.core.power_status == "battery"
        assert status.device.core.battery_level == 100
        assert status.device.core.attachment_status == "attached"
        assert status.device.core.pin_status is None
        break


@pytest.mark.asyncio
async def test_timeout_error(client_iometer):
    """Test handling of timeout errors."""

    async def mock_stream(*args, **kwargs):
        raise IOmeterTimeoutError("Timeout while communicating")
        yield

    client_iometer._stream = mock_stream

    with pytest.raises(IOmeterTimeoutError, match="Timeout while communicating"):
        async for status in client_iometer.watch_status():
            break


@pytest.mark.asyncio
async def test_client_error(client_iometer):
    """Test handling of client errors."""

    async def mock_stream(*args, **kwargs):
        raise IOmeterConnectionError("Error communicating")
        yield

    client_iometer._stream = mock_stream

    with pytest.raises(IOmeterConnectionError, match="Error communicating"):
        async for status in client_iometer.watch_status():
            break

@pytest.mark.asyncio
async def test_reading_not_found(client_iometer):
    """Test that a 404 on the reading endpoint raises IOmeterNoReadingsError."""

    async def mock_stream(*args, **kwargs):
        raise IOmeterNoReadingsError("No readings found")
        yield

    client_iometer._stream = mock_stream

    with pytest.raises(IOmeterNoReadingsError, match="No readings found"):
        async for reading in client_iometer.watch_readings():
            break


@pytest.mark.asyncio
async def test_status_not_found(client_iometer):
    """Test that a 404 on the status endpoint raises IOmeterNoStatusError."""

    async def mock_stream(*args, **kwargs):
        raise IOmeterNoStatusError("No status found")
        yield

    client_iometer._stream = mock_stream

    with pytest.raises(IOmeterNoStatusError, match="No status found"):
        async for status in client_iometer.watch_status():
            break