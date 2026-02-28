"""Constants for the Samsung 2878 AC integration."""

from homeassistant.components.climate import (
    HVACMode,
    SWING_OFF,
    SWING_VERTICAL,
    SWING_HORIZONTAL,
    SWING_BOTH,
)

DOMAIN = "samsung_2878"

DEFAULT_PORT = 2878
DEFAULT_POLL_INTERVAL = 30
TEMP_MIN = 16
TEMP_MAX = 30

CONF_HOST = "host"
CONF_PORT = "port"
CONF_TOKEN = "token"
CONF_MAC = "mac"
CONF_DUID = "duid"

# Samsung protocol mode values -> HA HVACMode
HVAC_MODE_MAP: dict[str, HVACMode] = {
    "Auto": HVACMode.AUTO,
    "Cool": HVACMode.COOL,
    "Heat": HVACMode.HEAT,
    "Dry": HVACMode.DRY,
    "Wind": HVACMode.FAN_ONLY,
}
HVAC_MODE_REVERSE: dict[HVACMode, str] = {v: k for k, v in HVAC_MODE_MAP.items()}

# Fan modes (sent as-is to the AC)
FAN_MODES = ["Auto", "Low", "Mid", "High", "Turbo"]

# Samsung direction values -> HA swing mode
SWING_MODE_MAP: dict[str, str] = {
    "Off": SWING_OFF,
    "Fixed": SWING_OFF,
    "SwingUD": SWING_VERTICAL,
    "SwingLR": SWING_HORIZONTAL,
    "Rotation": SWING_BOTH,
}
SWING_MODE_REVERSE: dict[str, str] = {
    SWING_OFF: "Off",
    SWING_VERTICAL: "SwingUD",
    SWING_HORIZONTAL: "SwingLR",
    SWING_BOTH: "Rotation",
}

# Preset modes
PRESET_MODES = ["Quiet", "Sleep", "Smart", "SoftCool"]
# Samsung COMODE values -> preset name
PRESET_MAP: dict[str, str] = {
    "Quiet": "Quiet",
    "Sleep": "Sleep",
    "Smart": "Smart",
    "SoftCool": "SoftCool",
}
PRESET_REVERSE: dict[str, str] = {v: k for k, v in PRESET_MAP.items()}
