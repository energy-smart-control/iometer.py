"""Asynchronous Python client for IOmeter."""

import asyncio
from dataclasses import dataclass
from typing import AsyncGenerator, Callable, Optional, Self

from aiohttp import ClientSession, ClientResponseError
from aiohttp_sse_client import client as sse_client
from aiohttp import ClientTimeout
from yarl import URL

from .exceptions import (
    IOmeterConnectionError,
    IOmeterTimeoutError,
    IOmeterNoReadingsError,
    IOmeterNoStatusError,
)
from .reading import Reading
from .status import Status


@dataclass
class IOmeterSSEClient:
    """Main IOmeter client class for handling SSE connections with the IOmeter bridge.

    Attributes:
        host: The hostname or IP address of the IOmeter bridge
        request_timeout: Number of seconds to wait for bridge response
        session: Optional aiohttp ClientSession for making requests
        reconnect_interval: Seconds to wait before reconnecting after an error

    Example using callbacks:
        async with IOmeterSSEClient("192.168.1.100") as client:
            cancel = client.subscribe_readings(
                on_reading=lambda r: print(r),
                on_error=lambda e: print("Error:", e),
            )
            await asyncio.sleep(60)
            cancel()
    """

    host: str
    request_timeout: int = 60
    session: Optional[ClientSession] = None
    reconnect_interval: int = 5

    async def _stream(self, uri: str) -> AsyncGenerator[str, None]:
        """Connect once to the SSE stream, yielding raw data strings.

        Translates network exceptions into IOmeter-specific exceptions.
        Does not reconnect — use _stream_loop for persistent streaming.
        """
        if not self.session:
            raise RuntimeError("Client session not initialized")

        url = f"http://{self.host}/{uri}"
        event_type = "readingEvent" if "reading" in uri else "statusEvent"

        try:
            async with sse_client.EventSource(
                url,
                session=self.session,
                timeout=ClientTimeout(
                    total=None,
                    sock_connect=self.request_timeout,
                    sock_read=self.request_timeout,
                ),

            ) as event_source:
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
            raise IOmeterConnectionError(
                f"Connection error: {err.status}"
            ) from err

        except (IOmeterTimeoutError, IOmeterNoReadingsError, IOmeterNoStatusError):
            raise

        except Exception as err:
            raise IOmeterConnectionError(f"Connection error: {err}") from err

    async def _stream_loop(
        self,
        uri: str,
        on_data: Callable,
        on_error: Optional[Callable[[Exception], None]],
    ) -> None:
        """Run the SSE stream in a loop, reconnecting after errors."""
        while True:
            try:
                async for raw in self._stream(uri):
                    if "reading" in uri:
                        on_data(Reading.from_json(raw))
                    else:
                        on_data(Status.from_json(raw))
            except asyncio.CancelledError:
                raise
            except Exception as err:
                if on_error is not None:
                    on_error(err)
                await asyncio.sleep(self.reconnect_interval)

    def subscribe_readings(
        self,
        on_reading: Callable[[Reading], None],
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> Callable[[], None]:
        """Start streaming readings and call on_reading for each one.

        Args:
            on_reading: Called with each new Reading.
            on_error: Called with each exception before reconnecting.

        Returns:
            A cancel callable that stops the stream.
        """
        task = asyncio.get_event_loop().create_task(
            self._stream_loop("v1/reading", on_reading, on_error)
        )
        return task.cancel

    def subscribe_status(
        self,
        on_status: Callable[[Status], None],
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> Callable[[], None]:
        """Start streaming status updates and call on_status for each one.

        Args:
            on_status: Called with each new Status.
            on_error: Called with each exception before reconnecting.

        Returns:
            A cancel callable that stops the stream.
        """
        task = asyncio.get_event_loop().create_task(
            self._stream_loop("v1/status", on_status, on_error)
        )
        return task.cancel

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