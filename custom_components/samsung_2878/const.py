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
# The AC drops its TLS socket after a short idle period. The poll doubles as a
# keepalive: a shorter interval keeps the connection warm so real-time push
# <Update> messages (remote/app changes) keep flowing between polls. Raise it
# to reduce traffic if your unit tolerates longer idles.
DEFAULT_POLL_INTERVAL = 20
TEMP_MIN = 16
TEMP_MAX = 30

# Values a register returns to mean "not supported / no data" on this firmware.
# 0xFE00, 0xFFFF and 0x8000 are the placeholders Samsung ACs use for unimplemented
# numeric registers (e.g. AC_ADD2_USEDWATT reports 65024 == AC_ADD2_VERSION on the
# AR12HSFS, which has no instantaneous-power meter). All are far outside any real
# reading, so guarding them never drops a genuine value.
SENTINEL_VALUES = frozenset({65024, 65535, 32768})

CONF_HOST = "host"
CONF_PORT = "port"
CONF_TOKEN = "token"
CONF_MAC = "mac"
CONF_DUID = "duid"
CONF_SWING_MODES = "swing_modes"

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

# The value the AC parks AC_FUN_DIRECTION at when it is written a token the
# firmware does not implement. It is sticky: the register stays here until a
# valid token is written, so it must not be mistaken for a real direction.
DIRECTION_NOT_SUPPORTED = "NotSupported"

# Samsung direction values -> HA swing mode
SWING_MODE_MAP: dict[str, str] = {
    "Off": SWING_OFF,
    "Fixed": SWING_OFF,
    "SwingUD": SWING_VERTICAL,
    "SwingLR": SWING_HORIZONTAL,
    "Rotation": SWING_BOTH,
}
# HA swing mode -> Samsung direction value.
#
# "off" must be sent as "Fixed", NOT "Off". Verified against the AR12HSFS:
# writing AC_FUN_DIRECTION="Off" is answered Status="Okay" but leaves the
# register at "NotSupported", where it stays until a valid token is written.
# Because SWING_MODE_MAP has no entry for "NotSupported", that used to read
# back as "off" — so turning swing off looked like it worked while the unit
# was actually left with no valid airflow direction at all, and the next
# swing command had to recover from that state. "Fixed" is the token the
# firmware accepts for "no swing" and it reads back cleanly.
#
# Accepted tokens on this firmware: Fixed, SwingUD, SwingLR, Rotation.
# Everything else (Off, Direct, Indirect, Up_And_Low, All, ...) -> NotSupported.
SWING_MODE_REVERSE: dict[str, str] = {
    SWING_OFF: "Fixed",
    SWING_VERTICAL: "SwingUD",
    SWING_HORIZONTAL: "SwingLR",
    SWING_BOTH: "Rotation",
}
# All HA swing modes this protocol can express, in display order.
ALL_SWING_MODES: list[str] = list(SWING_MODE_REVERSE.keys())
# Human-readable labels for the options flow multi-select.
SWING_MODE_LABELS: dict[str, str] = {
    SWING_OFF: "Off",
    SWING_VERTICAL: "Vertical (up / down)",
    SWING_HORIZONTAL: "Horizontal (left / right)",
    SWING_BOTH: "Both (rotation)",
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
