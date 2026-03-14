"""SpotOn device tracker entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
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
    """Set up SpotOn device trackers."""
    config_entry = entry
    runtime = config_entry.runtime_data
    coordinator = runtime.coordinator
    known_uids: set[str] = set()

    def _add_entities() -> None:
        new_entities: list[SpotOnCollarTracker] = []
        for collar in coordinator.data.collars:
            collar_uid = str(collar.get("uid") or collar.get("id"))
            if collar_uid in known_uids:
                continue
            known_uids.add(collar_uid)
            new_entities.append(SpotOnCollarTracker(coordinator, collar_uid))

        if new_entities:
            async_add_entities(new_entities)

    _add_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_entities))


class SpotOnCollarTracker(CoordinatorEntity[SpotOnDataUpdateCoordinator], TrackerEntity):
    """Represents a SpotOn collar as a GPS tracker."""

    _attr_has_entity_name = True
    _attr_name = "Location"
    _attr_source_type = SourceType.GPS

    def __init__(self, coordinator: SpotOnDataUpdateCoordinator, collar_uid: str) -> None:
        super().__init__(coordinator)
        self._collar_uid = collar_uid
        self._attr_unique_id = collar_uid

    @property
    def battery_level(self) -> int | None:
        """Return the battery level."""
        collar = self._collar
        if collar is None:
            return None
        return collar.get("battery_level")

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device metadata for the collar."""
        collar = self._collar
        if collar is None:
            return None

        return DeviceInfo(
            identifiers={(DOMAIN, self._collar_uid)},
            manufacturer="SpotOn",
            model=collar.get("hardware_version") or "GPS Fence Collar",
            name=collar.get("name") or f"Collar {collar.get('id')}",
            serial_number=self._collar_uid,
            sw_version=collar.get("firmware_version"),
            hw_version=collar.get("hardware_version"),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional current-state attributes."""
        collar = self._collar
        if collar is None:
            return {}

        fence = collar.get("fence") or {}
        detailed_fence = self.coordinator.data.fences.get(str(fence.get("id"))) if fence.get("id") is not None else None
        map_data = detailed_fence.get("map_data") if detailed_fence else None
        return {
            "location_collected_at": collar.get("last_seen_at") or collar.get("last_status_message_at"),
            "last_seen_at": collar.get("last_seen_at"),
            "last_status_message_at": collar.get("last_status_message_at"),
            "tracking": collar.get("tracking"),
            "tracking_reason": collar.get("tracking_reason"),
            "power_status": collar.get("power_status"),
            "signal_level": collar.get("signal_level"),
            "gps_level": collar.get("gps_level"),
            "cellular_available": collar.get("cellular_available"),
            "fence_id": fence.get("id"),
            "fence_uid": fence.get("uid") or (detailed_fence.get("uid") if detailed_fence else None),
            "fence_name": fence.get("name"),
            "fence_active": fence.get("active"),
            "fence_type": fence.get("fence_type") or (detailed_fence.get("fence_type") if detailed_fence else None),
            "fence_area": fence.get("fence_area") or (detailed_fence.get("fence_area") if detailed_fence else None),
            "fence_zone_count": len(detailed_fence.get("zones") or []) if detailed_fence else 0,
            "fence_version_count": len(detailed_fence.get("versions") or []) if detailed_fence else 0,
            "fence_geometry_available": map_data.get("geometry_available") if map_data else False,
            "fence_segment_count": map_data.get("segment_count") if map_data else 0,
            "fence_segments": map_data.get("segments") if map_data else None,
            "fence_geojson": map_data.get("geojson") if map_data else None,
        }

    @property
    def latitude(self) -> float | None:
        """Return latitude from the collar summary payload."""
        collar = self._collar
        if collar is None:
            return None
        return _safe_float(collar.get("last_location_lat"))

    @property
    def longitude(self) -> float | None:
        """Return longitude from the collar summary payload."""
        collar = self._collar
        if collar is None:
            return None
        return _safe_float(collar.get("last_location_lng"))

    @property
    def available(self) -> bool:
        """Return entity availability."""
        collar = self._collar
        return self.coordinator.last_update_success and collar is not None

    @property
    def _collar(self) -> dict[str, Any] | None:
        for collar in self.coordinator.data.collars:
            if str(collar.get("uid") or collar.get("id")) == self._collar_uid:
                return collar
        return None


def _safe_float(value: Any) -> float | None:
    """Best-effort conversion to float."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
