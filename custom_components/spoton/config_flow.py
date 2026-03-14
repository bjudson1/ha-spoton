"""Config flow for SpotOn."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SpotOnApiClient, SpotOnApiError, SpotOnAuthenticationError
from .const import CONF_ACCOUNT_ID, CONF_BASE_URL, CONF_USER_ID, DEFAULT_BASE_URL, DOMAIN


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
    }
)


class SpotOnConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SpotOn."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            api = SpotOnApiClient(
                session,
                email=user_input[CONF_EMAIL],
                password=user_input[CONF_PASSWORD],
                base_url=user_input[CONF_BASE_URL],
            )

            try:
                user = await api.async_get_current_user()
            except SpotOnAuthenticationError:
                errors["base"] = "invalid_auth"
            except SpotOnApiError:
                errors["base"] = "cannot_connect"
            else:
                data = {
                    **user_input,
                    CONF_ACCOUNT_ID: user.get("account_id"),
                    CONF_USER_ID: user.get("id"),
                }
                return self.async_create_entry(
                    title="SpotOn",
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
