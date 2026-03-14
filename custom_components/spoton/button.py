"""SpotOn button entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SpotOnDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SpotOn buttons."""
    coordinator: SpotOnDataUpdateCoordinator = entry.runtime_data.coordinator
    known_collar_uids: set[str] = set()

    def _add_entities() -> None:
        new_entities: list[ButtonEntity] = []
        for collar in coordinator.data.collars:
            collar_uid = str(collar.get("uid") or collar.get("id"))
            if collar_uid in known_collar_uids:
                continue
            known_collar_uids.add(collar_uid)
            new_entities.append(SpotOnRefreshLocationButton(coordinator, collar_uid))

        if new_entities:
            async_add_entities(new_entities)

    _add_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_entities))


class SpotOnRefreshLocationButton(CoordinatorEntity[SpotOnDataUpdateCoordinator], ButtonEntity):
    """Button to trigger the SpotOn collar refresh WebSocket action."""

    _attr_has_entity_name = True
    _attr_name = "Refresh Location"

    def __init__(self, coordinator: SpotOnDataUpdateCoordinator, collar_uid: str) -> None:
        super().__init__(coordinator)
        self._collar_uid = collar_uid
        self._attr_unique_id = f"{collar_uid}_refresh_location"

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.coordinator.last_update_success and self._collar is not None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the parent collar device."""
        collar = self._collar
        if collar is None:
            return None
        return DeviceInfo(identifiers={(DOMAIN, self._collar_uid)})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the last known refresh result for debugging."""
        result = self.coordinator.last_refresh_results.get(self._collar_uid)
        if not result:
            return {}

        stat = result.get("stat") or {}
        return {
            "request_action": result.get("request_action"),
            "ack_messages": result.get("ack_messages"),
            "stat": stat,
            "stat_action": stat.get("action"),
            "stat_battery": stat.get("bat"),
            "stat_cellular": stat.get("cel"),
            "stat_gps": stat.get("sat"),
            "stat_tracking": stat.get("tk"),
            "stat_latitude": stat.get("lt"),
            "stat_longitude": stat.get("ln"),
        }

    async def async_press(self) -> None:
        """Trigger a SpotOn collar refresh."""
        await self.coordinator.async_refresh_collar_location(self._collar_uid)

    @property
    def _collar(self) -> dict[str, Any] | None:
        for collar in self.coordinator.data.collars:
            if str(collar.get("uid") or collar.get("id")) == self._collar_uid:
                return collar
        return None
