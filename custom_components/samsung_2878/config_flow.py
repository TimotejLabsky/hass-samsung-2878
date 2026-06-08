"""Config flow for Samsung 2878 AC."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .client import (
    Samsung2878AuthError,
    Samsung2878Client,
    Samsung2878ConnectionError,
)
from .const import (
    ALL_SWING_MODES,
    CONF_DUID,
    CONF_MAC,
    CONF_SWING_MODES,
    CONF_TOKEN,
    DEFAULT_PORT,
    DOMAIN,
    SWING_MODE_LABELS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_TOKEN): str,
        vol.Required(CONF_MAC): str,
    }
)


class Samsung2878ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Samsung 2878 AC."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> Samsung2878OptionsFlow:
        """Return the options flow handler."""
        return Samsung2878OptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mac = user_input[CONF_MAC].upper()
            duid = mac.replace(":", "").replace("-", "")

            await self.async_set_unique_id(mac)
            self._abort_if_unique_id_configured()

            client = Samsung2878Client(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                token=user_input[CONF_TOKEN],
                duid=duid,
            )

            try:
                await client.connect()
                await client.authenticate()
            except Samsung2878ConnectionError:
                errors["base"] = "cannot_connect"
            except Samsung2878AuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during config flow")
                errors["base"] = "unknown"
            else:
                await client.disconnect()
                return self.async_create_entry(
                    title=f"Samsung AC ({user_input[CONF_HOST]})",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_TOKEN: user_input[CONF_TOKEN],
                        CONF_MAC: mac,
                        CONF_DUID: duid,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class Samsung2878OptionsFlow(OptionsFlow):
    """Handle options for a Samsung 2878 AC entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick which swing modes the AC physically supports."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_SWING_MODES, ALL_SWING_MODES
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SWING_MODES, default=current
                ): cv.multi_select(SWING_MODE_LABELS),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
