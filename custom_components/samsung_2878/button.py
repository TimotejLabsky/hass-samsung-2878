"""Button platform for Samsung 2878 AC."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DOMAIN
from .coordinator import Samsung2878Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Samsung 2878 buttons from a config entry."""
    coordinator: Samsung2878Coordinator = hass.data[DOMAIN][entry.entry_id]
    mac = entry.data[CONF_MAC]
    device_info = DeviceInfo(
        identifiers={(DOMAIN, mac)},
        name=entry.title,
        manufacturer="Samsung",
        model="AC 2878 (AR12HSFSAWKN)",
    )
    async_add_entities([
        ResetFilterAlarmButton(coordinator, mac, device_info),
        ResetPowerLoggingButton(coordinator, mac, device_info),
    ])


class ResetFilterAlarmButton(
    CoordinatorEntity[Samsung2878Coordinator], ButtonEntity
):
    """Button to reset the filter cleaning alarm."""

    _attr_has_entity_name = True
    _attr_name = "Reset filter alarm"
    _attr_icon = "mdi:air-filter"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: Samsung2878Coordinator,
        mac: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{mac}_reset_filter_alarm"
        self._attr_device_info = device_info

    async def async_press(self) -> None:
        """Press the button."""
        await self.coordinator.send_command(
            self.coordinator.client.clear_filter_alarm,
        )


class ResetPowerLoggingButton(
    CoordinatorEntity[Samsung2878Coordinator], ButtonEntity
):
    """Button to reset power logging data."""

    _attr_has_entity_name = True
    _attr_name = "Reset power logging"
    _attr_icon = "mdi:counter"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: Samsung2878Coordinator,
        mac: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{mac}_reset_power_logging"
        self._attr_device_info = device_info

    async def async_press(self) -> None:
        """Press the button."""
        await self.coordinator.send_command(
            self.coordinator.client.reset_power_logging,
        )
