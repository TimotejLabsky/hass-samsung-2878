"""Async client for Samsung 2878 AC protocol."""

from __future__ import annotations

import asyncio
import logging
import ssl
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

CERT_PATH = Path(__file__).parent / "ac14k_m.pem"

CONNECT_TIMEOUT = 10
IO_TIMEOUT = 10
MAX_RESPONSE_LINES = 10


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
    used_watt: float | None = None
    filter_use_time: int | None = None
    spi: bool = False
    used_power: int | None = None
    used_time: int | None = None
    cool_capability: int | None = None
    warm_capability: int | None = None
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

    # Power usage (raw / 10.0 = kWh)
    raw_watt = attrs.get("AC_ADD2_USEDWATT")
    if raw_watt is not None:
        try:
            state.used_watt = float(raw_watt) / 10.0
        except (ValueError, TypeError):
            state.used_watt = None

    # Filter usage time (hours)
    raw_filter = attrs.get("AC_ADD2_FILTER_USE_TIME")
    if raw_filter is not None:
        try:
            state.filter_use_time = int(raw_filter)
        except (ValueError, TypeError):
            state.filter_use_time = None

    # SPI (ionizer)
    state.spi = attrs.get("AC_ADD_SPI", "Off") == "On"

    # Used power (lifetime kWh)
    raw_used_power = attrs.get("AC_ADD2_USEDPOWER")
    if raw_used_power is not None:
        try:
            state.used_power = int(raw_used_power)
        except (ValueError, TypeError):
            state.used_power = None

    # Used time (operating hours)
    raw_used_time = attrs.get("AC_ADD2_USEDTIME")
    if raw_used_time is not None:
        try:
            state.used_time = int(raw_used_time)
        except (ValueError, TypeError):
            state.used_time = None

    # Cool/warm capability
    raw_cool = attrs.get("AC_COOL_CAPABILITY")
    if raw_cool is not None:
        try:
            state.cool_capability = int(raw_cool)
        except (ValueError, TypeError):
            state.cool_capability = None

    raw_warm = attrs.get("AC_WARM_CAPABILITY")
    if raw_warm is not None:
        try:
            state.warm_capability = int(raw_warm)
        except (ValueError, TypeError):
            state.warm_capability = None

    # Filter time threshold (hours)
    raw_filter_time = attrs.get("AC_ADD2_FILTERTIME")
    if raw_filter_time is not None:
        try:
            state.filter_time = int(raw_filter_time)
        except (ValueError, TypeError):
            state.filter_time = None

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
        self._last_push_attrs: dict[str, str] = {}
        self._ssl_context: ssl.SSLContext | None = None

    @property
    def connected(self) -> bool:
        """Return True if connected and authenticated."""
        return self._writer is not None and self._authenticated

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
            _LOGGER.debug("Authenticated successfully")

        except Samsung2878Error:
            raise
        except Exception as err:
            raise Samsung2878ConnectionError(
                f"Authentication error: {err}"
            ) from err

    async def disconnect(self) -> None:
        """Close the connection."""
        self._authenticated = False
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
        """Request and parse the current AC state."""
        xml = f'<Request Type="DeviceState" DUID="{self._duid}"></Request>\r\n'
        response = await self._send_command(xml, "DeviceState")
        attrs = self._parse_attrs(response)
        # Merge any push updates received since last poll
        if self._last_push_attrs:
            attrs.update(self._last_push_attrs)
            self._last_push_attrs.clear()
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
        result: dict[str, str] = {}
        try:
            root = ET.fromstring(response)
            sw = root.find("SwInfo")
            if sw is not None:
                result["sw_version"] = sw.get("Version", "")
            panel = root.find("PannelInfo")
            if panel is not None:
                result["panel_version"] = panel.get("Version", "")
            outdoor = root.find("OutDoorInfo")
            if outdoor is not None:
                result["outdoor_version"] = outdoor.get("Version", "")
        except ET.ParseError:
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
            for usage in root.iter("Usage"):
                entry = {}
                for attr_name in ("Date", "Usage", "Time"):
                    val = usage.get(attr_name)
                    if val is not None:
                        entry[attr_name.lower()] = val
                if entry:
                    entries.append(entry)
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
        """Send XML command and read the matching response.

        The AC can send unsolicited <Update> push messages at any time.
        This method skips those and returns the first <Response> line
        (optionally matching response_type). Skipped Update messages
        with state data are stored for the next get_status() call.
        """
        if self._writer is None or self._reader is None:
            raise Samsung2878ConnectionError("Not connected")
        if not self._authenticated:
            raise Samsung2878ConnectionError("Not authenticated")

        self._writer.write(xml.encode())
        await self._writer.drain()

        for _ in range(MAX_RESPONSE_LINES):
            line = await self._read_line()

            if "<Update " in line:
                # Capture state from push updates
                update_attrs = self._parse_attrs(line)
                if update_attrs:
                    self._last_push_attrs.update(update_attrs)
                    _LOGGER.debug("Captured push update: %s", update_attrs)
                continue

            if "<Response " in line:
                if response_type and f'Type="{response_type}"' not in line:
                    _LOGGER.debug(
                        "Skipping mismatched response: %s", line
                    )
                    continue
                return line

            # Unknown line (e.g. DPLUG greeting), skip
            _LOGGER.debug("Skipping unexpected line: %s", line)

        _LOGGER.warning(
            "No matching response after %d lines", MAX_RESPONSE_LINES
        )
        return ""

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
