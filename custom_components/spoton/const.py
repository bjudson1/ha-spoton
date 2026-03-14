"""Constants for the SpotOn integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "spoton"
PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER, Platform.SENSOR, Platform.BUTTON]

DEFAULT_BASE_URL = "https://www.spotonfenceapi.com"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)

CONF_ACCOUNT_ID = "account_id"
CONF_BASE_URL = "base_url"
CONF_USER_ID = "user_id"
