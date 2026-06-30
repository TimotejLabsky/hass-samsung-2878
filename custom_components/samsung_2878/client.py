"""Async client for Samsung 2878 AC protocol."""

from __future__ import annotations

import asyncio
import logging
import re
import ssl
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

CERT_PATH = Path(__file__).parent / "ac14k_m.pem"

CONNECT_TIMEOUT = 10
IO_TIMEOUT = 10

# Type of the callback the coordinator registers to receive real-time push
# <Update> attributes off the background reader loop.
PushCallback = Callable[[dict[str, str]], None]

# Placeholders the AC sends for registers it does not implement. Kept in sync
# with const.SENTINEL_VALUES, duplicated here so the CLI can load client.py
# standalone without pulling in Home Assistant. See const.py for rationale.
SENTINEL_VALUES = frozenset({65024, 65535, 32768})


def _int_or_none(raw: str | None, *, guard_sentinel: bool = True) -> int | None:
    """Parse an int register, returning None for missing/garbage/sentinel values."""
    if raw is None:
        return None
    try:
        value = int(raw)
    except (ValueError, TypeError):
        return None
    if guard_sentinel and value in SENTINEL_VALUES:
        return None
    return value


class Samsung2878Error(Exception):
    """Base exception for Samsung 2878 errors."""


class Samsung2878ConnectionError(Samsung2878Error):
    """Connection error."""


class Samsung2878AuthError(Samsung2878Error):
    """Authentication error."""


@dataclass
class Samsung2878State:
    """Parsed AC state."""

    power: bool = False
    mode: str = "Auto"
    current_temp: float = 0.0
    target_temp: int = 24
    fan_mode: str = "Auto"
    swing_mode: str = "Off"
    preset: str = "Off"
    outdoor_temp: float | None = None
    error: str = ""
    auto_clean: bool = False
    sleep_timer: int = 0
    used_watt: int | None = None  # instantaneous power draw, watts
    filter_use_time: int | None = None
    spi: bool = False
    used_power: float | None = None  # lifetime energy, kWh
    used_time: float | None = None  # lifetime operating time, hours
    cool_capability: float | None = None  # rated cooling output, kW
    warm_capability: float | None = None  # rated heating output, kW
    panel_version: str | None = None
    outdoor_version: str | None = None
    filter_time: int | None = None
    raw: dict[str, str] = field(default_factory=dict)


def _parse_state(attrs: dict[str, str]) -> Samsung2878State:
    """Parse raw attribute dict into Samsung2878State."""
    state = Samsung2878State(raw=attrs)

    state.power = attrs.get("AC_FUN_POWER", "Off") == "On"
    state.mode = attrs.get("AC_FUN_OPMODE", "Auto")
    state.fan_mode = attrs.get("AC_FUN_WINDLEVEL", "Auto")
    state.swing_mode = attrs.get("AC_FUN_DIRECTION", "Off")

    comode = attrs.get("AC_FUN_COMODE", "Off")
    state.preset = comode if comode != "Off" else "Off"

    # Current temperature
    try:
        state.current_temp = float(attrs.get("AC_FUN_TEMPNOW", "0"))
    except (ValueError, TypeError):
        state.current_temp = 0.0

    # Target temperature - 0 defaults to 24, <8 and !=0 defaults to 16
    try:
        raw_target = int(attrs.get("AC_FUN_TEMPSET", "24"))
        if raw_target == 0:
            raw_target = 24
        elif raw_target < 8:
            raw_target = 16
        state.target_temp = raw_target
    except (ValueError, TypeError):
        state.target_temp = 24

    # Outdoor temperature (raw - 55)
    raw_outdoor = attrs.get("AC_OUTDOOR_TEMP")
    if raw_outdoor is not None:
        try:
            state.outdoor_temp = float(raw_outdoor) - 55
        except (ValueError, TypeError):
            state.outdoor_temp = None

    # Error
    error = attrs.get("AC_FUN_ERROR", "")
    if error in ("00000", "", "00", "0"):
        state.error = ""
    else:
        state.error = error

    # Auto clean
    state.auto_clean = attrs.get("AC_ADD_AUTOCLEAN", "Off") == "On"

    # Sleep timer (minutes)
    try:
        state.sleep_timer = int(attrs.get("AC_FUN_SLEEP", "0"))
    except (ValueError, TypeError):
        state.sleep_timer = 0

    # Instantaneous power draw (watts). Unsupported on some models, which report
    # a sentinel (e.g. 65024 on the AR12HSFS) -> dropped by _int_or_none.
    state.used_watt = _int_or_none(attrs.get("AC_ADD2_USEDWATT"))

    # Filter usage time (hours)
    state.filter_use_time = _int_or_none(attrs.get("AC_ADD2_FILTER_USE_TIME"))

    # SPI (ionizer)
    state.spi = attrs.get("AC_ADD_SPI", "Off") == "On"

    # Lifetime energy (kWh) and operating time (hours). Like the capability
    # registers below, these are fixed-point in tenths: AC_ADD2_USEDPOWER is
    # 0.1 kWh/count and AC_ADD2_USEDTIME is 0.1 h/count (matching the documented
    # "AC_ADD2_USEDWATT raw/10 = kWh" convention). Taking them raw over-reported
    # by 10x; e.g. 6404 -> 640.4 kWh, 10820 -> 1082.0 h. The 10x raw scale is
    # also physically impossible for time (the counter "gained" 330 h over a
    # 240 h wall-clock window) and implied a ~5.9 kW average draw on a 3.5 kW
    # unit; /10 yields a sane ~0.59 kW average. See PROTOCOL.md.
    raw_used_power = _int_or_none(attrs.get("AC_ADD2_USEDPOWER"))
    state.used_power = raw_used_power / 10.0 if raw_used_power is not None else None
    raw_used_time = _int_or_none(attrs.get("AC_ADD2_USEDTIME"))
    state.used_time = raw_used_time / 10.0 if raw_used_time is not None else None

    # Rated cool/warm capability, reported in tenths of a kW (35 -> 3.5 kW)
    raw_cool = _int_or_none(attrs.get("AC_COOL_CAPABILITY"))
    state.cool_capability = raw_cool / 10.0 if raw_cool is not None else None
    raw_warm = _int_or_none(attrs.get("AC_WARM_CAPABILITY"))
    state.warm_capability = raw_warm / 10.0 if raw_warm is not None else None

    # Filter time threshold (hours)
    state.filter_time = _int_or_none(attrs.get("AC_ADD2_FILTERTIME"))

    # Firmware versions are exposed directly in DeviceState; prefer these over
    # the GetSWInfo request, which returns malformed XML on this firmware.
    panel = attrs.get("AC_ADD2_PANEL_VERSION")
    state.panel_version = str(panel) if panel else None
    outdoor = attrs.get("AC_ADD2_OUT_VERSION")
    state.outdoor_version = str(outdoor) if outdoor else None

    return state


class Samsung2878Client:
    """Async client for Samsung 2878 AC protocol."""

    def __init__(self, host: str, port: int, token: str, duid: str) -> None:
        self._host = host
        self._port = port
        self._token = token
        self._duid = duid
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._authenticated = False
        self._ssl_context: ssl.SSLContext | None = None
        # A single background task owns every read on the socket and dispatches
        # each line to either the in-flight command (via _pending_response) or
        # the push callback. This lets the AC's unsolicited <Update> messages be
        # applied in real time, and means reads are never issued concurrently.
        self._reader_task: asyncio.Task[None] | None = None
        self._pending_response: tuple[str | None, asyncio.Future[str]] | None = None
        self._push_callback: PushCallback | None = None
        # Serializes command submission so only one response is ever awaited at
        # a time (writes go out one-at-a-time; the reader loop fulfils them).
        self._io_lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        """Return True if connected, authenticated and the reader is alive."""
        return (
            self._writer is not None
            and self._authenticated
            and self._reader_task is not None
            and not self._reader_task.done()
        )

    def set_push_callback(self, callback: PushCallback | None) -> None:
        """Register a callback invoked with attrs from each push <Update>."""
        self._push_callback = callback

    @staticmethod
    def merge_push(
        current: Samsung2878State, attrs: dict[str, str]
    ) -> Samsung2878State:
        """Return a new state: ``current`` overlaid with push ``attrs``.

        Push <Update> messages carry only the registers that changed, so they
        are merged over the last full snapshot's raw attributes and re-parsed.
        """
        merged = dict(current.raw)
        merged.update(attrs)
        return _parse_state(merged)

    @staticmethod
    def _create_ssl_context() -> ssl.SSLContext:
        """Create SSL context (blocking I/O — must run in executor)."""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
        ctx.set_ciphers("HIGH:!DH:!aNULL:@SECLEVEL=0")
        ctx.load_verify_locations(str(CERT_PATH))
        ctx.load_cert_chain(str(CERT_PATH))
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    async def connect(self) -> None:
        """Establish TLS connection to the AC."""
        if self._ssl_context is None:
            self._ssl_context = await asyncio.to_thread(
                self._create_ssl_context
            )

        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self._host, self._port, ssl=self._ssl_context
                ),
                timeout=CONNECT_TIMEOUT,
            )
        except (OSError, asyncio.TimeoutError) as err:
            raise Samsung2878ConnectionError(
                f"Cannot connect to {self._host}:{self._port}: {err}"
            ) from err

        _LOGGER.debug("Connected to %s:%s", self._host, self._port)

    async def authenticate(self) -> None:
        """Authenticate with the AC using the saved token."""
        if self._reader is None or self._writer is None:
            raise Samsung2878ConnectionError("Not connected")

        try:
            # Read DPLUG-1.6 greeting
            line = await self._read_line()
            _LOGGER.debug("Greeting: %s", line)

            # Read InvalidateAccount update
            line = await self._read_line()
            _LOGGER.debug("InvalidateAccount: %s", line)

            # Send AuthToken request
            auth_xml = (
                f'<Request Type="AuthToken">'
                f'<User Token="{self._token}" />'
                f"</Request>\r\n"
            )
            self._writer.write(auth_xml.encode())
            await self._writer.drain()

            # Read AuthToken response
            line = await self._read_line()
            _LOGGER.debug("AuthToken response: %s", line)

            if 'Status="Okay"' not in line:
                raise Samsung2878AuthError(
                    f"Authentication failed: {line}"
                )

            self._authenticated = True
            # Hand the socket over to the background reader for the rest of the
            # session. All inline reads above happen before it starts.
            self._start_reader()
            _LOGGER.debug("Authenticated successfully")

        except Samsung2878Error:
            raise
        except Exception as err:
            raise Samsung2878ConnectionError(
                f"Authentication error: {err}"
            ) from err

    async def ensure_connected(self) -> None:
        """Connect and authenticate if not already, atomically.

        Idempotent and guarded by ``_io_lock`` so a reconnect can never
        interleave with an in-flight command on the shared socket. HA callers
        should use this rather than calling ``connect``/``authenticate``
        directly (the CLI, which is single-task, still uses those).
        """
        if self.connected:
            return
        async with self._io_lock:
            # Re-check under the lock: another task may have reconnected while
            # we waited.
            if self.connected:
                return
            # Tear down any half-dead connection (e.g. the reader loop exited on
            # EOF) before opening a fresh one.
            await self.disconnect()
            await self.connect()
            await self.authenticate()

    async def disconnect(self) -> None:
        """Close the connection and stop the reader loop."""
        self._authenticated = False

        task = self._reader_task
        self._reader_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001
                pass

        # Unblock any command still waiting on a response.
        self._fail_pending(Samsung2878ConnectionError("Disconnected"))

        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
            finally:
                self._writer = None
                self._reader = None
        _LOGGER.debug("Disconnected")

    async def get_status(self) -> Samsung2878State:
        """Request and parse the current AC state.

        Raises on an empty/garbage response rather than parsing it into a
        defaulted state: a missing register would otherwise read back as e.g.
        power Off / 24 °C and clobber the real state. Raising lets the
        coordinator keep the last good snapshot and retry/reconnect instead.
        """
        xml = f'<Request Type="DeviceState" DUID="{self._duid}"></Request>\r\n'
        response = await self._send_command(xml, "DeviceState")
        if not response:
            raise Samsung2878ConnectionError("No DeviceState response received")
        attrs = self._parse_attrs(response)
        if not attrs:
            raise Samsung2878ConnectionError("Unparseable DeviceState response")
        return _parse_state(attrs)

    async def set_power(self, on: bool) -> None:
        """Turn the AC on or off."""
        await self._set_control({"AC_FUN_POWER": "On" if on else "Off"})

    async def set_mode(self, mode: str) -> None:
        """Set the operation mode (Auto, Cool, Heat, Dry, Wind)."""
        await self._set_control({"AC_FUN_OPMODE": mode})

    async def set_temperature(self, temp: int) -> None:
        """Set the target temperature."""
        await self._set_control({"AC_FUN_TEMPSET": str(temp)})

    async def set_fan_mode(self, fan: str) -> None:
        """Set the fan speed (Auto, Low, Mid, High, Turbo)."""
        await self._set_control({"AC_FUN_WINDLEVEL": fan})

    async def set_swing_mode(self, swing: str) -> None:
        """Set the swing direction."""
        await self._set_control({"AC_FUN_DIRECTION": swing})

    async def set_preset(self, preset: str) -> None:
        """Set the convenient mode (Off, Quiet, Sleep, Smart, SoftCool)."""
        await self._set_control({"AC_FUN_COMODE": preset})

    async def set_auto_clean(self, on: bool) -> None:
        """Enable or disable auto clean."""
        await self._set_control({"AC_ADD_AUTOCLEAN": "On" if on else "Off"})

    async def set_sleep_timer(self, minutes: int) -> None:
        """Set the sleep timer (0 = off, 1-420 minutes)."""
        await self._set_control({"AC_FUN_SLEEP": str(minutes)})

    async def set_spi(self, on: bool) -> None:
        """Enable or disable SPI (ionizer)."""
        await self._set_control({"AC_ADD_SPI": "On" if on else "Off"})

    async def set_filter_time(self, hours: int) -> None:
        """Set filter replacement threshold (180, 300, 500, 700 hours)."""
        await self._set_control({"AC_ADD2_FILTERTIME": str(hours)})

    async def clear_filter_alarm(self) -> None:
        """Clear the filter cleaning alarm."""
        await self._set_control({"AC_ADD_CLEAR_FILTER_ALARM": "On"})

    async def get_sw_info(self) -> dict[str, str]:
        """Request software version information."""
        xml = '<Request Type="GetSWInfo"></Request>\r\n'
        response = await self._send_command(xml, "GetSWInfo")
        # The device returns malformed XML (unclosed <PannelInfo>/<OutDoorInfo>
        # tags), so ET.fromstring fails. Extract each Version attribute by regex
        # instead. Note the device's tag is "SWInfo", not "SwInfo".
        result: dict[str, str] = {}
        for tag, key in (
            ("SWInfo", "sw_version"),
            ("PannelInfo", "panel_version"),
            ("OutDoorInfo", "outdoor_version"),
        ):
            match = re.search(rf'<{tag}\b[^>]*\bVersion="([^"]*)"', response)
            if match:
                result[key] = match.group(1)
        if not result:
            _LOGGER.warning("Failed to parse GetSWInfo: %s", response)
        return result

    async def get_power_logging_mode(self) -> str:
        """Get current power logging mode."""
        xml = '<Request Type="GetPowerLoggingMode"></Request>\r\n'
        response = await self._send_command(xml, "GetPowerLoggingMode")
        try:
            root = ET.fromstring(response)
            return root.get("Mode", "Unknown")
        except ET.ParseError:
            return "Unknown"

    async def set_power_logging_mode(self, enable: bool) -> None:
        """Enable or disable power logging."""
        mode = "Enable" if enable else "Disable"
        xml = f'<Request Type="SetPowerLoggingMode" Mode="{mode}"></Request>\r\n'
        await self._send_command(xml, "SetPowerLoggingMode")

    async def reset_power_logging(self) -> None:
        """Reset power logging data."""
        xml = '<Request Type="ResetPowerLogging"></Request>\r\n'
        await self._send_command(xml, "ResetPowerLogging")

    async def get_power_usage(
        self, date_from: str, date_to: str, unit: str = "Day"
    ) -> list[dict[str, str]]:
        """Get power usage data for a date range.

        date_from/date_to format: yy-MM-dd HH:mm
        unit: Hour or Day
        """
        xml = (
            f'<Request Type="GetPowerUsage">'
            f'<PowerUsage from="{date_from}" to="{date_to}" Unit="{unit}" />'
            f"</Request>\r\n"
        )
        response = await self._send_command(xml, "GetPowerUsage")
        entries: list[dict[str, str]] = []
        try:
            root = ET.fromstring(response)
            # Device emits <PowerUsage Date=".." PowerUsage="kwh" UsageTime="min" />;
            # PowerUsage="-1" means no data was logged for that period.
            for usage in root.iter("PowerUsage"):
                usage_val = usage.get("PowerUsage")
                if usage_val is None or usage_val == "-1":
                    continue
                entries.append({
                    "date": usage.get("Date", ""),
                    "usage": usage_val,
                    "time": usage.get("UsageTime", ""),
                })
        except ET.ParseError:
            _LOGGER.warning("Failed to parse GetPowerUsage: %s", response)
        return entries

    async def send_raw_xml(self, xml: str) -> str:
        """Send raw XML command and return the response."""
        if not xml.endswith("\r\n"):
            xml += "\r\n"
        return await self._send_command(xml, None)

    async def _set_control(self, attrs: dict[str, str]) -> None:
        """Send a DeviceControl command."""
        attr_xml = "".join(
            f'<Attr ID="{k}" Value="{v}" />' for k, v in attrs.items()
        )
        xml = (
            f'<Request Type="DeviceControl">'
            f'<Control CommandID="cmd00000" DUID="{self._duid}">'
            f"{attr_xml}"
            f"</Control>"
            f"</Request>\r\n"
        )
        response = await self._send_command(xml, "DeviceControl")
        if response is not None and 'Status="Okay"' not in response:
            _LOGGER.warning("Control command may have failed: %s", response)

    async def _send_command(
        self, xml: str, response_type: str | None = None
    ) -> str:
        """Send an XML command and await its <Response>.

        The background reader owns the socket and resolves the future stored in
        ``_pending_response`` when the matching <Response> arrives; unsolicited
        <Update> pushes are dispatched to the callback instead. ``_io_lock``
        keeps commands one-at-a-time so only a single response is ever awaited.
        """
        async with self._io_lock:
            if not self.connected or self._writer is None:
                raise Samsung2878ConnectionError("Not connected")

            loop = asyncio.get_running_loop()
            future: asyncio.Future[str] = loop.create_future()
            self._pending_response = (response_type, future)
            try:
                self._writer.write(xml.encode())
                await self._writer.drain()
                return await asyncio.wait_for(future, IO_TIMEOUT)
            except asyncio.TimeoutError as err:
                raise Samsung2878ConnectionError("Response timeout") from err
            except Samsung2878Error:
                raise
            except OSError as err:
                raise Samsung2878ConnectionError(f"Write error: {err}") from err
            finally:
                self._pending_response = None

    def _start_reader(self) -> None:
        """Launch the background reader loop if not already running."""
        if self._reader_task is None or self._reader_task.done():
            self._reader_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        """Read every line from the socket and dispatch it.

        Runs for the life of the connection. <Response> lines fulfil the
        in-flight command; <Update> pushes are forwarded to the registered
        callback so remote/app changes reach HA without waiting for the poll.
        EOF or any read error ends the loop and marks us disconnected; the
        coordinator reconnects on its next poll or command.
        """
        reader = self._reader
        if reader is None:
            return
        try:
            while True:
                data = await reader.readline()
                if not data:
                    _LOGGER.debug("AC closed the connection")
                    break
                line = data.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                if "<Update " in line:
                    attrs = self._parse_attrs(line)
                    if attrs:
                        _LOGGER.debug("Push update: %s", attrs)
                        callback = self._push_callback
                        if callback is not None:
                            try:
                                callback(attrs)
                            except Exception:  # noqa: BLE001
                                _LOGGER.exception("Push callback raised")
                elif "<Response " in line:
                    self._deliver_response(line)
                else:
                    _LOGGER.debug("Ignoring line: %s", line)
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Reader loop stopped: %s", err)
        finally:
            self._authenticated = False
            self._fail_pending(Samsung2878ConnectionError("Connection lost"))

    def _deliver_response(self, line: str) -> None:
        """Fulfil the in-flight command future with a matching <Response>."""
        pending = self._pending_response
        if pending is None:
            _LOGGER.debug("Dropping unsolicited response: %s", line)
            return
        response_type, future = pending
        if response_type and f'Type="{response_type}"' not in line:
            _LOGGER.debug("Ignoring mismatched response: %s", line)
            return
        if not future.done():
            future.set_result(line)

    def _fail_pending(self, err: Exception) -> None:
        """Propagate a connection error to a command awaiting a response."""
        pending = self._pending_response
        if pending is not None:
            _, future = pending
            if not future.done():
                future.set_exception(err)
        self._pending_response = None

    async def _read_line(self) -> str:
        """Read a single line from the connection."""
        if self._reader is None:
            raise Samsung2878ConnectionError("Not connected")
        try:
            data = await asyncio.wait_for(
                self._reader.readline(), timeout=IO_TIMEOUT
            )
        except asyncio.TimeoutError as err:
            raise Samsung2878ConnectionError("Read timeout") from err

        if not data:
            raise Samsung2878ConnectionError("Connection closed by AC")

        return data.decode("utf-8", errors="replace").strip()

    @staticmethod
    def _parse_attrs(xml_str: str) -> dict[str, str]:
        """Parse Attr elements from an XML response string."""
        attrs: dict[str, str] = {}
        try:
            root = ET.fromstring(xml_str)
            for attr_elem in root.iter("Attr"):
                attr_id = attr_elem.get("ID")
                attr_val = attr_elem.get("Value")
                if attr_id is not None and attr_val is not None:
                    attrs[attr_id] = attr_val
        except ET.ParseError:
            _LOGGER.warning("Failed to parse XML: %s", xml_str)
        return attrs
