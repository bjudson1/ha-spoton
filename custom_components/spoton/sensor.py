"""SpotOn sensor entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import SpotOnDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SpotOn sensors."""
    coordinator: SpotOnDataUpdateCoordinator = entry.runtime_data.coordinator
    known_collar_uids: set[str] = set()
    known_fence_ids: set[str] = set()

    def _add_entities() -> None:
        new_entities: list[SensorEntity] = []
        for collar in coordinator.data.collars:
            collar_uid = str(collar.get("uid") or collar.get("id"))
            if collar_uid in known_collar_uids:
                continue
            known_collar_uids.add(collar_uid)
            new_entities.append(SpotOnLastLocationTimestampSensor(coordinator, collar_uid))

        for fence_id, fence in coordinator.data.fences.items():
            if fence_id in known_fence_ids:
                continue
            known_fence_ids.add(fence_id)
            new_entities.append(SpotOnFenceSensor(coordinator, fence_id))

        if new_entities:
            async_add_entities(new_entities)

    _add_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_entities))


class SpotOnLastLocationTimestampSensor(CoordinatorEntity[SpotOnDataUpdateCoordinator], SensorEntity):
    """Timestamp sensor for the latest collar summary location."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_has_entity_name = True
    _attr_name = "Last Location Update"

    def __init__(self, coordinator: SpotOnDataUpdateCoordinator, collar_uid: str) -> None:
        super().__init__(coordinator)
        self._collar_uid = collar_uid
        self._attr_unique_id = f"{collar_uid}_last_location_update"

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.coordinator.last_update_success and self._collar is not None

    @property
    def native_value(self):
        """Return the timestamp for the collar's current summary location."""
        collar = self._collar
        if collar is None:
            return None

        timestamp = collar.get("last_seen_at") or collar.get("last_status_message_at")
        if not timestamp:
            return None
        return dt_util.parse_datetime(timestamp)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return supporting timestamp fields from the live payload."""
        collar = self._collar
        if collar is None:
            return {}

        return {
            "last_seen_at": collar.get("last_seen_at"),
            "last_status_message_at": collar.get("last_status_message_at"),
            "timestamp_source": "last_seen_at_or_last_status_message_at",
        }

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the parent collar device."""
        collar = self._collar
        if collar is None:
            return None

        return DeviceInfo(
            identifiers={(DOMAIN, self._collar_uid)},
        )

    @property
    def _collar(self) -> dict[str, Any] | None:
        for collar in self.coordinator.data.collars:
            if str(collar.get("uid") or collar.get("id")) == self._collar_uid:
                return collar
        return None


class SpotOnFenceSensor(CoordinatorEntity[SpotOnDataUpdateCoordinator], SensorEntity):
    """Fence entity with map-ready geometry attributes."""

    _attr_has_entity_name = True
    _attr_name = "Fence"

    def __init__(self, coordinator: SpotOnDataUpdateCoordinator, fence_id: str) -> None:
        super().__init__(coordinator)
        self._fence_id = fence_id
        self._attr_unique_id = f"fence_{fence_id}"

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.coordinator.last_update_success and self._fence is not None

    @property
    def native_value(self) -> str | None:
        """Return the fence status."""
        fence = self._fence
        if fence is None:
            return None
        return "active" if fence.get("active") else "inactive"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return fence metadata and decoded geometry."""
        fence = self._fence
        if fence is None:
            return {}

        map_data = fence.get("map_data") or {}
        zones = fence.get("zones") or []
        versions = fence.get("versions") or []
        return {
            "fence_id": fence.get("id"),
            "fence_uid": fence.get("uid"),
            "fence_type": fence.get("fence_type"),
            "fence_area": fence.get("fence_area"),
            "created_at": fence.get("created_at"),
            "active": fence.get("active"),
            "parent_fence_id": fence.get("parent_fence_id"),
            "is_owner": fence.get("is_owner"),
            "zone_count": len(zones),
            "zones": zones,
            "version_count": len(versions),
            "versions": versions,
            "geometry_available": map_data.get("geometry_available"),
            "segment_count": map_data.get("segment_count"),
            "segments": map_data.get("segments"),
            "geojson": map_data.get("geojson"),
        }

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the fence as its own device."""
        fence = self._fence
        if fence is None:
            return None

        fence_uid = str(fence.get("uid") or self._fence_id)
        return DeviceInfo(
            identifiers={(DOMAIN, f"fence_{fence_uid}")},
            manufacturer="SpotOn",
            model="Virtual Fence",
            name=fence.get("name") or f"Fence {self._fence_id}",
            serial_number=fence_uid,
        )

    @property
    def _fence(self) -> dict[str, Any] | None:
        return self.coordinator.data.fences.get(self._fence_id)
