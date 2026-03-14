"""Data coordinator for SpotOn."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SpotOnApiClient, SpotOnApiError, SpotOnAuthenticationError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .fence_model import build_fence_map_data

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class SpotOnData:
    """Coordinator payload."""

    user: dict[str, Any]
    collars: list[dict[str, Any]]
    fences: dict[str, dict[str, Any]]


class SpotOnDataUpdateCoordinator(DataUpdateCoordinator[SpotOnData]):
    """Coordinate SpotOn polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: SpotOnApiClient,
    ) -> None:
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.config_entry = config_entry
        self.api = api
        self.user: dict[str, Any] | None = None
        self.last_refresh_results: dict[str, dict[str, Any]] = {}

    async def _async_setup(self) -> None:
        """Fetch account metadata once during first refresh."""
        try:
            self.user = await self.api.async_get_current_user()
        except SpotOnAuthenticationError as err:
            raise ConfigEntryAuthFailed("SpotOn authentication failed") from err
        except SpotOnApiError as err:
            raise UpdateFailed(f"Unable to initialize SpotOn account: {err}") from err

    async def _async_update_data(self) -> SpotOnData:
        """Fetch the latest SpotOn collars payload."""
        try:
            collars, fences = await asyncio.gather(
                self.api.async_list_collars(),
                self._async_fetch_fences(),
            )
        except SpotOnAuthenticationError as err:
            raise ConfigEntryAuthFailed("SpotOn authentication failed") from err
        except SpotOnApiError as err:
            raise UpdateFailed(f"Unable to fetch SpotOn account data: {err}") from err

        return SpotOnData(
            user=self.user or {},
            collars=collars,
            fences=fences,
        )

    async def async_refresh_collar_location(self, collar_uid: str) -> dict[str, Any]:
        """Trigger the app-equivalent collar refresh action, then refresh coordinator data."""
        collar = next(
            (
                item
                for item in self.data.collars
                if str(item.get("uid") or item.get("id")) == str(collar_uid)
            ),
            None,
        )
        if collar is None:
            raise UpdateFailed(f"Unknown SpotOn collar {collar_uid}")

        try:
            result = await self.api.async_refresh_collar_location(
                collar_uid=str(collar.get("uid") or collar_uid),
                collar_id=collar.get("id"),
                collar_name=collar.get("name"),
            )
        except SpotOnAuthenticationError as err:
            raise ConfigEntryAuthFailed("SpotOn authentication failed") from err
        except SpotOnApiError as err:
            raise UpdateFailed(f"Unable to refresh SpotOn collar {collar_uid}: {err}") from err

        self.last_refresh_results[str(collar_uid)] = result

        try:
            await self.async_request_refresh()
        except Exception:
            LOGGER.warning("SpotOn collar refresh succeeded but follow-up data refresh failed", exc_info=True)

        return result

    async def _async_fetch_fences(self) -> dict[str, dict[str, Any]]:
        """Fetch detailed fences and derive map-ready geometry."""
        fences = await self.api.async_list_fences()
        detailed_fences: dict[str, dict[str, Any]] = {}

        for fence in fences:
            fence_id = fence.get("id")
            if fence_id is None:
                continue

            try:
                detailed_fence = await self.api.async_get_fence(fence_id)
            except SpotOnApiError:
                LOGGER.warning(
                    "Falling back to summary fence payload for fence %s",
                    fence_id,
                    exc_info=True,
                )
                detailed_fence = dict(fence)
            else:
                detailed_fence = dict(detailed_fence)

            detailed_fence["map_data"] = build_fence_map_data(detailed_fence)
            detailed_fences[str(fence_id)] = detailed_fence

        return detailed_fences
