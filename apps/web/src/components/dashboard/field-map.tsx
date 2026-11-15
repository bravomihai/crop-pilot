"use client";

import { useEffect, useRef, useState } from "react";
import type { Location } from "@croppilot/contracts";
import type { Map as LeafletMap } from "leaflet";
import Icon from "./icon";
import RegionalMapContext from "../regional-map-context";

// Avoid imagery levels where the basemap can return unavailable-data tiles.
const MAX_MAP_ZOOM = 17;
// Street level for a chosen place; the default view shows the whole country.
const FIELD_ZOOM = 13;

type Props = {
  view: Location;
  /** Map zoom for `view`; a found place or chosen field uses street level. */
  zoom?: number;
  selection: Location | null;
  onSelect: (selection: Location | null) => void;
};

export default function FieldMap(props: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<LeafletMap | null>(null);
  const latest = useRef(props);
  latest.current = props;
  const renderSelection = useRef<(() => void) | null>(null);
  const revealPin = useRef<(() => void) | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [tileError, setTileError] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);

  useEffect(() => {
    let disposed = false;
    let cleanup = () => {};
    void import("leaflet").then(L => {
      if (disposed || !container.current) return;
      const location = latest.current.view;
      const instance = L.map(container.current, { zoomControl: false, preferCanvas: true, maxZoom: MAX_MAP_ZOOM }).setView([location.latitude, location.longitude], latest.current.zoom ?? FIELD_ZOOM);
      map.current = instance;
      L.control.zoom({ position: "bottomright" }).addTo(instance);
      const imagery = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: MAX_MAP_ZOOM,
        attribution: 'Imagery &copy; <a href="https://www.esri.com/">Esri</a>, Maxar, Earthstar Geographics',
      });
      const labels = L.tileLayer("https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: MAX_MAP_ZOOM, attribution: "Labels &copy; Esri", pane: "overlayPane",
      });
      const satellite = L.layerGroup([imagery, labels]).addTo(instance);
      const streets = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: MAX_MAP_ZOOM, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      });
      L.control.layers({ Satellite: satellite, "Street map": streets }, {}, { position: "bottomright" }).addTo(instance);
      imagery.on("tileerror", () => { if (!disposed) setTileError(true); });
      const pin = L.divIcon({ className: "field-map-marker", html: '<span class="field-pin"><span></span></span>', iconSize: [38, 48], iconAnchor: [19, 46], tooltipAnchor: [0, -48] });
      let marker: ReturnType<typeof L.marker> | null = null;
      function select(latitude: number, longitude: number) {
        latest.current.onSelect({ name: "Your field", latitude, longitude });
      }
      renderSelection.current = () => {
        const selected = latest.current.selection;
        if (!selected) { marker?.remove(); marker = null; return; }
        const position: [number, number] = [selected.latitude, selected.longitude];
        if (marker) marker.setLatLng(position);
        else {
          marker = L.marker(position, { icon: pin, draggable: true, title: "Your field — drag to move", alt: "Selected field location", autoPan: true }).addTo(instance);
          marker.bindTooltip("Your field", { direction: "top", className: "field-pin-label" });
          marker.on("dragend", () => {
            if (!marker) return;
            const point = marker.getLatLng();
            select(point.lat, point.lng);
          });
        }
      };
      revealPin.current = () => {
        if (!marker) return;
        const panel = document.querySelector<HTMLElement>(".map-planner:not([hidden])")?.getBoundingClientRect();
        const size = instance.getSize();
        const mobile = window.innerWidth <= 760;
        instance.panInside(marker.getLatLng(), {
          paddingTopLeft: mobile ? [35, 145] : [panel ? panel.right + 30 : 45, 120],
          paddingBottomRight: mobile ? [50, panel ? Math.max(110, size.y - panel.top + 28) : 110] : [70, 130],
          animate: false,
        });
      };
      instance.on("click", e => select(e.latlng.lat, e.latlng.lng));
      const observer = new ResizeObserver(() => { instance.invalidateSize(); revealPin.current?.(); });
      observer.observe(container.current);
      renderSelection.current();
      setReady(true);
      cleanup = () => { observer.disconnect(); marker?.remove(); instance.remove(); map.current = null; renderSelection.current = null; revealPin.current = null; };
    }).catch(() => { if (!disposed) setFailed(true); });
    return () => { disposed = true; cleanup(); };
  }, []);

  useEffect(() => {
    if (ready) map.current?.setView([props.view.latitude, props.view.longitude], props.zoom ?? FIELD_ZOOM);
  }, [props.view, props.zoom, ready]);
  useEffect(() => { renderSelection.current?.(); revealPin.current?.(); }, [props.selection, ready]);

  function useCentre() {
    const centre = map.current?.getCenter();
    if (centre) props.onSelect({ name: "Your field", latitude: centre.lat, longitude: centre.lng });
  }

  return (
    <section className="map-canvas" aria-label="Field map">
      <div className="satellite-map" ref={container} tabIndex={0} role="region" aria-label="Field location map. Click to select your field, or pan with arrow keys and choose Use map centre." aria-describedby="map-instructions" />
      <div className="map-toolbar" role="group" aria-label="Location controls">
        <span><Icon name="pin" size={17} />{props.selection ? "Click anywhere to move your pin" : "Click the map to place your field"}</span>
        <button type="button" disabled={!ready} onClick={useCentre}>Use map centre<Icon name="pin" size={16} /></button>
        {props.selection && <button type="button" className="map-clear" aria-label="Clear field location" onClick={() => props.onSelect(null)}><Icon name="trash" size={17} /></button>}
      </div>
      <p className={`map-instructions ${failed ? "has-error" : ""}`} id="map-instructions" role="status">{failed ? "Map unavailable. Try a location search." : !ready ? "Loading map…" : ""}</p>
      {tileError && <p className="tile-warning" role="status">Imagery unavailable. Choose Street map in the layer control.</p>}
      <details className="map-context-menu" onToggle={e => setContextOpen(e.currentTarget.open)}>
        <summary aria-label="NASA layers"><Icon name="satellite" size={17} /><span>NASA layers</span></summary>
        {contextOpen && <div className="map-context-content"><RegionalMapContext map={ready ? map.current : null} location={props.selection ?? undefined} /></div>}
      </details>
    </section>
  );
}
