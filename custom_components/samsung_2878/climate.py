"""Climate platform for Samsung 2878 AC."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_MAC,
    DOMAIN,
    FAN_MODES,
    HVAC_MODE_MAP,
    HVAC_MODE_REVERSE,
    PRESET_MODES,
    PRESET_REVERSE,
    SWING_MODE_MAP,
    SWING_MODE_REVERSE,
    TEMP_MAX,
    TEMP_MIN,
)
from .coordinator import Samsung2878Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Samsung 2878 climate from a config entry."""
    coordinator: Samsung2878Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([Samsung2878Climate(coordinator, entry)])


class Samsung2878Climate(CoordinatorEntity[Samsung2878Coordinator], ClimateEntity):
    """Samsung 2878 AC climate entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = TEMP_MIN
    _attr_max_temp = TEMP_MAX
    _attr_target_temperature_step = 1
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes = [HVACMode.OFF, *HVAC_MODE_MAP.values()]
    _attr_fan_modes = FAN_MODES
    _attr_swing_modes = list(SWING_MODE_REVERSE.keys())
    _attr_preset_modes = PRESET_MODES
    _enable_turn_on_off_backwards_compat = False

    def __init__(
        self, coordinator: Samsung2878Coordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = entry.data[CONF_MAC]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_MAC])},
            name=entry.title,
            manufacturer="Samsung",
            model="AC 2878 (AR12HSFSAWKN)",
        )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        if not self.coordinator.data.power:
            return HVACMode.OFF
        return HVAC_MODE_MAP.get(self.coordinator.data.mode, HVACMode.AUTO)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return current HVAC action."""
        if not self.coordinator.data.power:
            return HVACAction.OFF
        mode = HVAC_MODE_MAP.get(self.coordinator.data.mode)
        if mode == HVACMode.COOL:
            return HVACAction.COOLING
        if mode == HVACMode.HEAT:
            return HVACAction.HEATING
        if mode == HVACMode.DRY:
            return HVACAction.DRYING
        if mode == HVACMode.FAN_ONLY:
            return HVACAction.FAN
        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.coordinator.data.current_temp or None

    @property
    def target_temperature(self) -> int | None:
        """Return the target temperature."""
        if not self.coordinator.data.power:
            return None
        return self.coordinator.data.target_temp

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        return self.coordinator.data.fan_mode

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode."""
        return SWING_MODE_MAP.get(
            self.coordinator.data.swing_mode, "Off"
        )

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        preset = self.coordinator.data.preset
        if preset == "Off":
            return None
        return preset

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.send_command(
                self.coordinator.client.set_power, False,
                optimistic={"power": False},
            )
            return

        ac_mode = HVAC_MODE_REVERSE.get(hvac_mode)
        if ac_mode is None:
            return

        if not self.coordinator.data.power:
            await self.coordinator.client.set_power(True)
        await self.coordinator.send_command(
            self.coordinator.client.set_mode, ac_mode,
            optimistic={"power": True, "mode": ac_mode},
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        await self.coordinator.send_command(
            self.coordinator.client.set_temperature, int(temp),
            optimistic={"target_temp": int(temp)},
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        await self.coordinator.send_command(
            self.coordinator.client.set_fan_mode, fan_mode,
            optimistic={"fan_mode": fan_mode},
        )

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode."""
        ac_swing = SWING_MODE_REVERSE.get(swing_mode, "Off")
        await self.coordinator.send_command(
            self.coordinator.client.set_swing_mode, ac_swing,
            optimistic={"swing_mode": ac_swing},
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        ac_preset = PRESET_REVERSE.get(preset_mode, "Off")
        await self.coordinator.send_command(
            self.coordinator.client.set_preset, ac_preset,
            optimistic={"preset": ac_preset},
        )

    async def async_turn_on(self) -> None:
        """Turn the AC on."""
        await self.coordinator.send_command(
            self.coordinator.client.set_power, True,
            optimistic={"power": True},
        )

    async def async_turn_off(self) -> None:
        """Turn the AC off."""
        await self.coordinator.send_command(
            self.coordinator.client.set_power, False,
            optimistic={"power": False},
        )
