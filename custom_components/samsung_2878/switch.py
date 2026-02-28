"""Switch platform for Samsung 2878 AC."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DOMAIN
from .coordinator import Samsung2878Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Samsung 2878 switches from a config entry."""
    coordinator: Samsung2878Coordinator = hass.data[DOMAIN][entry.entry_id]
    mac = entry.data[CONF_MAC]
    device_info = DeviceInfo(
        identifiers={(DOMAIN, mac)},
        name=entry.title,
        manufacturer="Samsung",
        model="AC 2878 (AR12HSFSAWKN)",
    )
    async_add_entities([AutoCleanSwitch(coordinator, mac, device_info)])


class AutoCleanSwitch(
    CoordinatorEntity[Samsung2878Coordinator], SwitchEntity
):
    """Auto clean switch."""

    _attr_has_entity_name = True
    _attr_name = "Auto clean"
    _attr_icon = "mdi:shimmer"

    def __init__(
        self,
        coordinator: Samsung2878Coordinator,
        mac: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{mac}_auto_clean"
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool:
        """Return True if auto clean is on."""
        return self.coordinator.data.auto_clean

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on auto clean."""
        await self.coordinator.send_command(
            self.coordinator.client.set_auto_clean, True,
            optimistic={"auto_clean": True},
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off auto clean."""
        await self.coordinator.send_command(
            self.coordinator.client.set_auto_clean, False,
            optimistic={"auto_clean": False},
        )
