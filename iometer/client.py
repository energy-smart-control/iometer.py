"""Asynchronous Python client for IOmeter."""

from dataclasses import dataclass
from typing import AsyncGenerator, Optional, Self

from aiohttp import ClientSession, ClientResponseError
from aiohttp_sse_client import client as sse_client
from yarl import URL

from .exceptions import (
    IOmeterConnectionError,
    IOmeterTimeoutError,
    IOmeterNoReadingsError,
    IOmeterNoStatusError,
)
from .reading import Reading
from .status import Status

import asyncio

@dataclass
class IOmeterSSEClient:
    """Main IOmeter client class for handling SSE connections with the IOmeter bridge.

    Attributes:
        host: The hostname or IP address of the IOmeter bridge
        request_timeout: Number of seconds to wait for bridge response
        session: Optional aiohttp ClientSession for making requests

    Example:
        async with ClientSession() as session:
            client = IOmeterSSEClient("192.168.1.100", session)
            async for reading in client.watch_readings():
                print("New reading:", reading)
    """

    host: str
    request_timeout: int = 60
    session: Optional[ClientSession] = None

    async def _stream(self, uri: str) -> AsyncGenerator[str, None]:
        if not self.session:
            raise RuntimeError("Client session not initialized")

        url = f"http://{self.host}/{uri}"
        event_type = "readingEvent" if "reading" in uri else "statusEvent"
        backoff = 1

        while True:
            try:
                async with sse_client.EventSource(
                    url,
                    session=self.session,
                    timeout=self.request_timeout,
                ) as event_source:
                    backoff = 1
                    async for event in event_source:
                        if event.type == event_type and event.data:
                            yield event.data

            except asyncio.TimeoutError as err:
                raise IOmeterTimeoutError("Timeout while communicating") from err

            except ClientResponseError as err:
                if err.status == 404:
                    if "reading" in uri:
                        raise IOmeterNoReadingsError("No readings found") from err
                    raise IOmeterNoStatusError("No status found") from err
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

            except Exception:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)


    async def watch_readings(self) -> AsyncGenerator[Reading, None]:
        """Yield readings as they arrive from the SSE stream.

        Yields:
            Reading objects
        """
        async for data in self._stream("v1/reading"):
            yield Reading.from_json(data)

    async def watch_status(self) -> AsyncGenerator[Status, None]:
        """Yield status updates as they arrive from the SSE stream.

        Yields:
            Status objects
        """
        async for data in self._stream("v1/status"):
            yield Status.from_json(data)

    async def close(self) -> None:
        """Close the client session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def __aenter__(self) -> Self:
        """Set up the client session.

        Returns:
            The configured client instance
        """
        self.session = self.session or ClientSession()
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Clean up the client session."""
        await self.close()


@dataclass
class IOmeterClient:
    """Main IOmeter client class for handling HTTP connections with the IOmeter bridge.

    Attributes:
        host: The hostname or IP address of the IOmeter bridge
        request_timeout: Number of seconds to wait for bridge response
        session: Optional aiohttp ClientSession for making requests

    Example:
        async with IOmeterClient("192.168.1.100") as client:
            reading = await client.get_current_reading()
            status = await client.get_current_status()
    """

    host: str
    request_timeout: int = 60
    session: Optional[ClientSession] = None

    async def _request(self, uri: str) -> str:
        if not self.session:
            raise RuntimeError("Client session not initialized")

        url = URL.build(scheme="http", host=self.host) / uri
        headers = {
            "User-Agent": "PythonIOmeter/0.1",
            "Accept": "application/json",
        }

        try:
            async with asyncio.timeout(self.request_timeout):
                response = await self.session.get(url, headers=headers)
                response.raise_for_status()
                return await response.text()

        except asyncio.TimeoutError as error:
            raise IOmeterTimeoutError(
                "Timeout while communicating with IOmeter bridge"
            ) from error

        except ClientResponseError as error:
            if error.status == 404:
                if "reading" in uri:
                    raise IOmeterNoReadingsError(
                        "No readings available from IOmeter bridge"
                    ) from error
                if "status" in uri:
                    raise IOmeterNoStatusError(
                        "No status available from IOmeter bridge"
                    ) from error
            raise IOmeterConnectionError(
                f"Bridge returned error {error.status}: {error.message}"
            ) from error

        except Exception as error:
            raise IOmeterConnectionError(
                f"Error communicating with IOmeter bridge: {str(error)}"
            ) from error

    async def get_current_reading(self) -> Reading:
        """Get current reading from IOmeter bridge."""
        response = await self._request("v1/reading")
        return Reading.from_json(response)

    async def get_current_status(self) -> Status:
        """Get device status from IOmeter bridge."""
        response = await self._request("v1/status")
        return Status.from_json(response)

    async def close(self) -> None:
        """Close the client session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def __aenter__(self) -> Self:
        self.session = self.session or ClientSession()
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.close()