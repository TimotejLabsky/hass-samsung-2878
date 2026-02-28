"""Sensor platform for Samsung 2878 AC."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfTemperature, UnitOfTime
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
    """Set up Samsung 2878 sensors from a config entry."""
    coordinator: Samsung2878Coordinator = hass.data[DOMAIN][entry.entry_id]
    mac = entry.data[CONF_MAC]
    device_info = DeviceInfo(
        identifiers={(DOMAIN, mac)},
        name=entry.title,
        manufacturer="Samsung",
        model="AC 2878 (AR12HSFSAWKN)",
    )
    async_add_entities([
        OutdoorTemperatureSensor(coordinator, mac, device_info),
        ErrorSensor(coordinator, mac, device_info),
        PowerUsageSensor(coordinator, mac, device_info),
        FilterUsageSensor(coordinator, mac, device_info),
        UsedPowerSensor(coordinator, mac, device_info),
        UsedTimeSensor(coordinator, mac, device_info),
        CoolCapabilitySensor(coordinator, mac, device_info),
        WarmCapabilitySensor(coordinator, mac, device_info),
        PanelVersionSensor(coordinator, mac, device_info),
        OutdoorVersionSensor(coordinator, mac, device_info),
    ])


class OutdoorTemperatureSensor(
    CoordinatorEntity[Samsung2878Coordinator], SensorEntity
):
    """Outdoor temperature sensor."""

    _attr_has_entity_name = True
    _attr_name = "Outdoor temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: Samsung2878Coordinator,
        mac: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{mac}_outdoor_temp"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> float | None:
        """Return outdoor temperature."""
        return self.coordinator.data.outdoor_temp


class ErrorSensor(CoordinatorEntity[Samsung2878Coordinator], SensorEntity):
    """AC error status sensor."""

    _attr_has_entity_name = True
    _attr_name = "Error status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(
        self,
        coordinator: Samsung2878Coordinator,
        mac: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{mac}_error"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> str:
        """Return error code or OK."""
        return self.coordinator.data.error or "OK"


class PowerUsageSensor(
    CoordinatorEntity[Samsung2878Coordinator], SensorEntity
):
    """Total power usage sensor."""

    _attr_has_entity_name = True
    _attr_name = "Energy usage"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(
        self,
        coordinator: Samsung2878Coordinator,
        mac: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{mac}_energy"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> float | None:
        """Return energy usage in kWh."""
        return self.coordinator.data.used_watt


class FilterUsageSensor(
    CoordinatorEntity[Samsung2878Coordinator], SensorEntity
):
    """Filter usage time sensor."""

    _attr_has_entity_name = True
    _attr_name = "Filter usage"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_icon = "mdi:air-filter"

    def __init__(
        self,
        coordinator: Samsung2878Coordinator,
        mac: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{mac}_filter_usage"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        """Return filter usage in hours."""
        return self.coordinator.data.filter_use_time


class UsedPowerSensor(CoordinatorEntity[Samsung2878Coordinator], SensorEntity):
    """Lifetime power usage sensor."""

    _attr_has_entity_name = True
    _attr_name = "Lifetime energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: Samsung2878Coordinator,
        mac: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{mac}_used_power"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        """Return lifetime energy usage in kWh."""
        return self.coordinator.data.used_power


class UsedTimeSensor(CoordinatorEntity[Samsung2878Coordinator], SensorEntity):
    """Lifetime operating time sensor."""

    _attr_has_entity_name = True
    _attr_name = "Operating time"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: Samsung2878Coordinator,
        mac: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{mac}_used_time"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        """Return operating time in hours."""
        return self.coordinator.data.used_time


class CoolCapabilitySensor(
    CoordinatorEntity[Samsung2878Coordinator], SensorEntity
):
    """Cooling capability sensor."""

    _attr_has_entity_name = True
    _attr_name = "Cooling capability"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:snowflake"

    def __init__(
        self,
        coordinator: Samsung2878Coordinator,
        mac: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{mac}_cool_capability"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        """Return cooling capability."""
        return self.coordinator.data.cool_capability


class WarmCapabilitySensor(
    CoordinatorEntity[Samsung2878Coordinator], SensorEntity
):
    """Heating capability sensor."""

    _attr_has_entity_name = True
    _attr_name = "Heating capability"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:fire"

    def __init__(
        self,
        coordinator: Samsung2878Coordinator,
        mac: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{mac}_warm_capability"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        """Return heating capability."""
        return self.coordinator.data.warm_capability


class PanelVersionSensor(
    CoordinatorEntity[Samsung2878Coordinator], SensorEntity
):
    """Panel firmware version sensor."""

    _attr_has_entity_name = True
    _attr_name = "Panel version"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:chip"

    def __init__(
        self,
        coordinator: Samsung2878Coordinator,
        mac: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{mac}_panel_version"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> str | None:
        """Return panel firmware version."""
        return self.coordinator.data.panel_version


class OutdoorVersionSensor(
    CoordinatorEntity[Samsung2878Coordinator], SensorEntity
):
    """Outdoor unit firmware version sensor."""

    _attr_has_entity_name = True
    _attr_name = "Outdoor unit version"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:chip"

    def __init__(
        self,
        coordinator: Samsung2878Coordinator,
        mac: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{mac}_outdoor_version"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> str | None:
        """Return outdoor unit firmware version."""
        return self.coordinator.data.outdoor_version
