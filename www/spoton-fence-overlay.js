export default function (L, pluginBase, Logger) {
  return class SpotOnFenceOverlay extends pluginBase {
    constructor(map, name, options = {}) {
      super(map, name, options);
      this._layerGroup = L.layerGroup().addTo(this.map);
      this._geoJsonLayers = [];
    }

    async init() {
      Logger.debug(`[SpotOnFenceOverlay] Initialized plugin: ${this.name}`);
    }

    async renderMap() {
      await this._renderFences();
    }

    async update() {
      await this._renderFences();
    }

    destroy() {
      this._clearLayers();
      this._layerGroup.remove();
    }

    async _renderFences() {
      const hass = this._getHass();
      if (!hass) {
        Logger.warn("[SpotOnFenceOverlay] Unable to locate Home Assistant hass object.");
        return;
      }

      this._clearLayers();

      for (const entityId of this._entityIds()) {
        const stateObj = hass.states[entityId];
        if (!stateObj) {
          Logger.warn(`[SpotOnFenceOverlay] Fence entity not found: ${entityId}`);
          continue;
        }

        const geojson = stateObj.attributes?.geojson;
        if (!geojson?.features?.length) {
          continue;
        }

        const layer = L.geoJSON(geojson, {
          style: (feature) => this._styleForFeature(feature),
          onEachFeature: (feature, featureLayer) => {
            const label = feature?.properties?.zone_name || feature?.properties?.fence_name || entityId;
            featureLayer.bindTooltip(label, {
              sticky: true,
            });
          },
        });

        layer.addTo(this._layerGroup);
        this._geoJsonLayers.push(layer);
      }
    }

    _clearLayers() {
      for (const layer of this._geoJsonLayers) {
        layer.remove();
      }
      this._geoJsonLayers = [];
      this._layerGroup.clearLayers();
    }

    _entityIds() {
      if (Array.isArray(this.options.entity_ids)) {
        return this.options.entity_ids;
      }
      if (typeof this.options.entity_id === "string" && this.options.entity_id.length > 0) {
        return [this.options.entity_id];
      }
      return [];
    }

    _styleForFeature(feature) {
      const role = feature?.properties?.segment_role;
      const zoneType = feature?.properties?.zone_type;
      if (role === "zone" && zoneType === "home") {
        return {
          color: this.options.home_outline_color || "#3aa76d",
          fillColor: this.options.home_fill_color || "#5cd38c",
          fillOpacity: this.options.home_fill_opacity ?? 0.18,
          weight: this.options.home_weight || 2,
        };
      }

      return {
        color: this.options.boundary_outline_color || "#ff6b35",
        fillColor: this.options.boundary_fill_color || "#ff8c61",
        fillOpacity: this.options.boundary_fill_opacity ?? 0.12,
        weight: this.options.boundary_weight || 3,
      };
    }

    _getHass() {
      const root = document.querySelector("home-assistant");
      if (root?.hass) {
        return root.hass;
      }

      const main = root?.shadowRoot?.querySelector("home-assistant-main");
      if (main?.hass) {
        return main.hass;
      }

      const panel = main?.shadowRoot?.querySelector("ha-panel-lovelace");
      if (panel?.hass) {
        return panel.hass;
      }

      const huiRoot = panel?.shadowRoot?.querySelector("hui-root");
      return huiRoot?.hass;
    }
  };
}
