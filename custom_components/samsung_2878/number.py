"""Number platform for Samsung 2878 AC."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
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
    """Set up Samsung 2878 number entities from a config entry."""
    coordinator: Samsung2878Coordinator = hass.data[DOMAIN][entry.entry_id]
    mac = entry.data[CONF_MAC]
    device_info = DeviceInfo(
        identifiers={(DOMAIN, mac)},
        name=entry.title,
        manufacturer="Samsung",
        model="AC 2878 (AR12HSFSAWKN)",
    )
    async_add_entities([SleepTimerNumber(coordinator, mac, device_info)])


class SleepTimerNumber(
    CoordinatorEntity[Samsung2878Coordinator], NumberEntity
):
    """Sleep timer number entity."""

    _attr_has_entity_name = True
    _attr_name = "Sleep timer"
    _attr_icon = "mdi:sleep"
    _attr_native_min_value = 0
    _attr_native_max_value = 420
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: Samsung2878Coordinator,
        mac: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{mac}_sleep_timer"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int:
        """Return current sleep timer value in minutes."""
        return self.coordinator.data.sleep_timer

    async def async_set_native_value(self, value: float) -> None:
        """Set sleep timer."""
        await self.coordinator.send_command(
            self.coordinator.client.set_sleep_timer, int(value),
            optimistic={"sleep_timer": int(value)},
        )
