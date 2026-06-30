"""DataUpdateCoordinator for Samsung 2878 AC."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import (
    Samsung2878Client,
    Samsung2878ConnectionError,
    Samsung2878AuthError,
    Samsung2878Error,
    Samsung2878State,
)
from .const import DEFAULT_POLL_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class Samsung2878Coordinator(DataUpdateCoordinator[Samsung2878State]):
    """Coordinator to poll Samsung 2878 AC state."""

    def __init__(self, hass: HomeAssistant, client: Samsung2878Client) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_POLL_INTERVAL),
        )
        self.client = client
        # Receive real-time push <Update> messages from the AC (remote/app
        # changes) instead of waiting for the next poll.
        client.set_push_callback(self._handle_push)

    @callback
    def _handle_push(self, attrs: dict[str, str]) -> None:
        """Apply a real-time push <Update> to local state.

        Invoked from the client's reader loop. Pushes carry only the changed
        registers, so they are merged over the current snapshot. Ignored until
        the first poll has populated ``self.data``.

        We update ``data`` and notify listeners directly rather than via
        ``async_set_updated_data``: the latter reschedules the poll, and since
        the poll doubles as the keepalive, a stream of pushes would keep
        delaying it and let the AC drop the idle socket.
        """
        if not attrs or self.data is None:
            return
        self.data = self.client.merge_push(self.data, attrs)
        self.async_update_listeners()

    async def _async_update_data(self) -> Samsung2878State:
        """Fetch data from the AC.

        The AC silently drops its idle TLS socket between our 30s polls, so the
        first read on a stale connection times out ("Read timeout"). That made
        the entity flap to ``unavailable`` for a poll on every reconnect. We now
        absorb the transient: on a connection error, drop the socket and retry
        once with a fresh connection before surfacing the failure.
        """
        try:
            return await self._poll_once()
        except Samsung2878AuthError as err:
            await self.client.disconnect()
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except Samsung2878ConnectionError as err:
            _LOGGER.debug("Poll failed (%s); reconnecting and retrying once", err)
            await self.client.disconnect()
            try:
                return await self._poll_once()
            except Samsung2878AuthError as err2:
                await self.client.disconnect()
                raise UpdateFailed(f"Authentication failed: {err2}") from err2
            except Samsung2878ConnectionError as err2:
                await self.client.disconnect()
                raise UpdateFailed(f"Connection failed: {err2}") from err2

    async def _poll_once(self) -> Samsung2878State:
        """Connect if needed and fetch one DeviceState snapshot."""
        await self.client.ensure_connected()
        # Firmware versions are parsed from DeviceState (see _parse_state).
        return await self.client.get_status()

    async def send_command(
        self,
        coro_func: Callable[..., Coroutine[Any, Any, None]],
        *args: Any,
        optimistic: dict[str, Any] | None = None,
    ) -> None:
        """Execute a client command with optimistic local state update.

        When optimistic is provided, the coordinator data is updated
        immediately so the UI reflects the change without waiting for
        the next poll. The regular 30s poll will reconcile with the
        actual AC state.

        Like the poll, this absorbs the AC's habit of dropping its idle
        socket between interactions: on a connection error we drop the
        socket and retry the command once on a fresh connection before
        surfacing the failure to the user.
        """
        try:
            await self.client.ensure_connected()
            await coro_func(*args)
        except Samsung2878AuthError as err:
            await self.client.disconnect()
            raise HomeAssistantError(f"Authentication failed: {err}") from err
        except Samsung2878ConnectionError as err:
            _LOGGER.debug("Command failed (%s); reconnecting and retrying once", err)
            await self.client.disconnect()
            try:
                await self.client.ensure_connected()
                await coro_func(*args)
            except Samsung2878Error as err2:
                await self.client.disconnect()
                raise HomeAssistantError(f"Command failed: {err2}") from err2

        if optimistic and self.data:
            for key, value in optimistic.items():
                setattr(self.data, key, value)
            self.async_set_updated_data(self.data)
