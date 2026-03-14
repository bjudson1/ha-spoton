"""The SpotOn integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SpotOnApiClient
from .const import CONF_BASE_URL, DEFAULT_BASE_URL, DOMAIN, PLATFORMS
from .coordinator import SpotOnDataUpdateCoordinator


@dataclass(slots=True)
class SpotOnRuntimeData:
    """Runtime state for a SpotOn config entry."""

    api: SpotOnApiClient
    coordinator: SpotOnDataUpdateCoordinator

SpotOnConfigEntry = ConfigEntry[SpotOnRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: SpotOnConfigEntry) -> bool:
    """Set up SpotOn from a config entry."""
    session = async_get_clientsession(hass)
    api = SpotOnApiClient(
        session,
        email=entry.data["email"],
        password=entry.data["password"],
        base_url=entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL),
    )
    coordinator = SpotOnDataUpdateCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = SpotOnRuntimeData(api=api, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SpotOnConfigEntry) -> bool:
    """Unload a SpotOn config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: SpotOnConfigEntry) -> None:
    """Reload SpotOn on config entry update."""
    await hass.config_entries.async_reload(entry.entry_id)
