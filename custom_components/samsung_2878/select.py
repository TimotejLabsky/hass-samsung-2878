"""Select platform for Samsung 2878 AC."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DOMAIN
from .coordinator import Samsung2878Coordinator

FILTER_TIME_OPTIONS = ["180", "300", "500", "700"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Samsung 2878 selects from a config entry."""
    coordinator: Samsung2878Coordinator = hass.data[DOMAIN][entry.entry_id]
    mac = entry.data[CONF_MAC]
    device_info = DeviceInfo(
        identifiers={(DOMAIN, mac)},
        name=entry.title,
        manufacturer="Samsung",
        model="AC 2878 (AR12HSFSAWKN)",
    )
    async_add_entities([FilterTimeSelect(coordinator, mac, device_info)])


class FilterTimeSelect(
    CoordinatorEntity[Samsung2878Coordinator], SelectEntity
):
    """Filter replacement threshold select."""

    _attr_has_entity_name = True
    _attr_name = "Filter threshold"
    _attr_icon = "mdi:air-filter"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = FILTER_TIME_OPTIONS

    def __init__(
        self,
        coordinator: Samsung2878Coordinator,
        mac: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{mac}_filter_time"
        self._attr_device_info = device_info

    @property
    def current_option(self) -> str | None:
        """Return the current filter time threshold."""
        val = self.coordinator.data.filter_time
        if val is not None:
            return str(val)
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the filter time threshold."""
        await self.coordinator.send_command(
            self.coordinator.client.set_filter_time, int(option),
            optimistic={"filter_time": int(option)},
        )
