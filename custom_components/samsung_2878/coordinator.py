"""DataUpdateCoordinator for Samsung 2878 AC."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import (
    Samsung2878Client,
    Samsung2878ConnectionError,
    Samsung2878AuthError,
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

    async def _async_update_data(self) -> Samsung2878State:
        """Fetch data from the AC."""
        try:
            if not self.client.connected:
                await self.client.connect()
                await self.client.authenticate()
            return await self.client.get_status()
        except Samsung2878AuthError as err:
            await self.client.disconnect()
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except Samsung2878ConnectionError as err:
            await self.client.disconnect()
            raise UpdateFailed(f"Connection failed: {err}") from err

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
        """
        try:
            await coro_func(*args)
        except Samsung2878ConnectionError as err:
            await self.client.disconnect()
            raise UpdateFailed(f"Command failed: {err}") from err

        if optimistic and self.data:
            for key, value in optimistic.items():
                setattr(self.data, key, value)
            self.async_set_updated_data(self.data)
