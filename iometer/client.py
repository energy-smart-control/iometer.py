"""Asynchronous Python client for IOmeter."""

import asyncio
import codecs
import re
from dataclasses import dataclass
from typing import AsyncGenerator, Callable, Optional, Self

from aiohttp import ClientSession, ClientResponseError, ClientTimeout, StreamReader
from yarl import URL

from .exceptions import (
    IOmeterConnectionError,
    IOmeterTimeoutError,
    IOmeterNoReadingsError,
    IOmeterNoStatusError,
)
from .reading import Reading
from .status import Status

# The event-stream format ends a line with CRLF, LF or a lone CR. The bridge sends
# runs of lone CRs between events, so splitting on LF alone is not enough.
_LINE_END = re.compile(r"\r\n|\r|\n")


async def _iter_sse_events(content: StreamReader) -> AsyncGenerator[tuple[str, str], None]:
    """Parse an SSE byte stream into (event type, data) pairs.

    Implements the parsing rules of the WHATWG event-stream format: fields
    `event` and `data`, comments starting with `:`, an empty line dispatches
    the event, and any of CRLF, LF or CR ends a line.
    """
    decoder = codecs.getincrementaldecoder("utf-8")()
    buffer = ""
    event_type = ""
    data: list[str] = []
    # Set when a chunk ended with CR: a LF at the start of the next chunk is
    # the second half of that CRLF, not an empty line of its own.
    skip_lf = False
    async for chunk in content.iter_any():
        text = decoder.decode(chunk)
        if not text:
            continue
        if skip_lf and text.startswith("\n"):
            text = text[1:]
        skip_lf = False
        buffer += text
        while match := _LINE_END.search(buffer):
            line = buffer[: match.start()]
            buffer = buffer[match.end() :]
            skip_lf = match.group() == "\r" and not buffer
            if line == "":
                if data:
                    yield event_type or "message", "\n".join(data)
                event_type = ""
                data = []
                continue
            if line.startswith(":"):
                continue
            name, _, value = line.partition(":")
            value = value.removeprefix(" ")
            if name == "event":
                event_type = value
            elif name == "data":
                data.append(value)


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
            async with self.session.get(
                url,
                headers={"Accept": "text/event-stream", "Cache-Control": "no-cache"},
                timeout=ClientTimeout(
                    total=None,
                    sock_connect=self.request_timeout,
                    sock_read=self.request_timeout,
                ),
                raise_for_status=True,
            ) as response:
                async for event, data in _iter_sse_events(response.content):
                    if event == event_type and data:
                        yield data

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
