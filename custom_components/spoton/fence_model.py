"""Helpers for decoding SpotOn fence geometry into map-ready structures."""

from __future__ import annotations

import base64
import binascii
import struct
from typing import Any

SEGMENT_HEADER_FORMAT = "<IIIIIIII"
SEGMENT_HEADER_SIZE = struct.calcsize(SEGMENT_HEADER_FORMAT)
SEGMENT_MAGIC = 0x55555555
SEGMENT_SENTINEL = 0xAAAAAAAA


def build_fence_map_data(fence: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-serializable map model derived from a fence payload."""
    zones = fence.get("zones") if isinstance(fence.get("zones"), list) else []
    raw_segments = _decode_geometry_segments(fence.get("data"))

    segments: list[dict[str, Any]] = []
    features: list[dict[str, Any]] = []

    for index, raw_segment in enumerate(raw_segments):
        zone = zones[index - 1] if index > 0 and index - 1 < len(zones) else None
        role = "boundary" if index == 0 else "zone"

        points = [
            {
                "latitude": latitude,
                "longitude": longitude,
            }
            for latitude, longitude in _close_ring(raw_segment["points"])
        ]
        feature_coordinates = [
            [point["longitude"], point["latitude"]]
            for point in points
        ]

        segment = {
            "role": role,
            "segment_id": raw_segment["segment_id"],
            "point_count": len(points),
            "coordinates": points,
        }
        if zone is not None:
            segment["zone"] = {
                "id": zone.get("id"),
                "uid": zone.get("uid"),
                "name": zone.get("name"),
                "zone_type": zone.get("zone_type"),
                "creation_method": zone.get("creation_method"),
            }
        segments.append(segment)

        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [feature_coordinates],
                },
                "properties": {
                    "fence_id": fence.get("id"),
                    "fence_uid": fence.get("uid"),
                    "fence_name": fence.get("name"),
                    "segment_role": role,
                    "segment_id": raw_segment["segment_id"],
                    "zone_id": zone.get("id") if zone else None,
                    "zone_uid": zone.get("uid") if zone else None,
                    "zone_name": zone.get("name") if zone else None,
                    "zone_type": zone.get("zone_type") if zone else None,
                },
            }
        )

    return {
        "geometry_available": bool(segments),
        "segment_count": len(segments),
        "geojson": {
            "type": "FeatureCollection",
            "features": features,
        }
        if features
        else None,
        "segments": segments,
    }


def _decode_geometry_segments(data: Any) -> list[dict[str, Any]]:
    """Decode SpotOn fence geometry segments from the base64 data blob."""
    if not isinstance(data, str) or not data:
        return []

    try:
        raw = base64.b64decode(data)
    except (ValueError, binascii.Error):
        return []

    segments: list[dict[str, Any]] = []
    offset = 0
    while offset + SEGMENT_HEADER_SIZE <= len(raw):
        (
            magic,
            segment_id,
            segment_size,
            point_count,
            _reserved1,
            _reserved2,
            _reserved3,
            sentinel,
        ) = struct.unpack(
            SEGMENT_HEADER_FORMAT,
            raw[offset : offset + SEGMENT_HEADER_SIZE],
        )
        if magic != SEGMENT_MAGIC or sentinel != SEGMENT_SENTINEL:
            break
        if segment_size < SEGMENT_HEADER_SIZE or offset + segment_size > len(raw):
            break

        available_points = (segment_size - SEGMENT_HEADER_SIZE) // 16
        if point_count > available_points:
            break

        points: list[tuple[float, float]] = []
        points_offset = offset + SEGMENT_HEADER_SIZE
        for index in range(point_count):
            chunk_start = points_offset + index * 16
            latitude, longitude = struct.unpack(
                "<dd",
                raw[chunk_start : chunk_start + 16],
            )
            if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                points.append((latitude, longitude))

        if points:
            segments.append(
                {
                    "segment_id": str(segment_id),
                    "points": points,
                }
            )

        offset += segment_size

    return segments


def _close_ring(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Return a closed polygon ring when enough points are present."""
    if len(points) < 3:
        return points
    if points[0] == points[-1]:
        return points
    return [*points, points[0]]
