# Home Assistant SpotOn Integration

<p align="center">
  <img src="https://spotonfence.com/cdn/shop/files/spoton-logo-3.png?v=1756224096&width=600" alt="SpotOn logo" width="240">
</p>

Home Assistant custom integration for SpotOn dog collars.

## Current scope

- Collar location as `device_tracker` entities
- Last-seen timestamp exposure
- Fence retrieval and map-ready fence modeling
- Per-collar `Refresh Location` buttons using the same WebSocket refresh path as the mobile app
- Optional `ha-map-card` fence overlay plugin

## Installation

### Manual

1. Copy `custom_components/spoton` into your Home Assistant config directory under `custom_components/spoton`.
2. Restart Home Assistant.
3. Go to `Settings -> Devices & Services -> Add Integration`.
4. Search for `SpotOn`.
5. Enter your SpotOn account credentials.

### HACS

This repo includes `hacs.json` and is structured for HACS, but manual installation is the simplest first setup path.

## Optional map fence overlay

The repo includes `www/spoton-fence-overlay.js`, which can be copied to your HA `www` directory and used with `ha-map-card` to render SpotOn fence polygons on the map.

High-level flow:

1. Copy `www/spoton-fence-overlay.js` to `/config/www/spoton-fence-overlay.js`.
2. Install `ha-map-card`.
3. Add the plugin to your map card config and point it at a fence entity such as `sensor.green_lake_fence`.

## Notes

- The integration currently polls SpotOn summary state every 5 minutes.
- There is a refresh button per collar to refresh location immediately.
- Fence rendering in Home Assistant is optional and separate from the core integration.
