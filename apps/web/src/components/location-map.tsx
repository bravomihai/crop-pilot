"use client";
import { useEffect, useRef, useState } from "react";
import type { Map as LeafletMap, CircleMarker } from "leaflet";
import type { Location } from "@fieldshift/contracts";
import RegionalMapContext from "./regional-map-context";
export default function LocationMap({
  location,
  onSelect,
  disabled = false,
}: {
  location?: Location;
  onSelect: (value: Location) => void;
  disabled?: boolean;
}) {
  const [ready, setReady] = useState(false);
  const container = useRef<HTMLDivElement>(null),
    map = useRef<LeafletMap | null>(null),
    marker = useRef<CircleMarker | null>(null);
  const callback = useRef(onSelect);
  callback.current = onSelect;
  const disabledRef = useRef(disabled);
  disabledRef.current = disabled;
  useEffect(() => {
    let disposed = false;
    void import("leaflet").then((L) => {
      if (disposed || !container.current) return;
      map.current = L.map(container.current).setView([48, 16], 4);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map.current);
      map.current.on("click", (event) => {
        if (disabledRef.current) return;
        callback.current({
          name: "Point selected on the map",
          latitude: Number(event.latlng.lat.toFixed(6)),
          longitude: Number(event.latlng.lng.toFixed(6)),
        });
      });
      setReady(true);
    });
    return () => {
      disposed = true;
      map.current?.remove();
      map.current = null;
      marker.current = null;
    };
  }, []);
  useEffect(() => {
    let disposed = false;
    if (location)
      void import("leaflet").then((L) => {
        if (disposed || !map.current) return;
        marker.current?.remove();
        marker.current = L.circleMarker(
          [location.latitude, location.longitude],
          { radius: 8, color: "#16634b", fillOpacity: 0.8 },
        ).addTo(map.current);
        map.current.setView([location.latitude, location.longitude], 10);
      });
    return () => {
      disposed = true;
    };
  }, [location, ready]);
  return (
    <div className="location-map-wrap">
      <div
        ref={container}
        className="map"
        role="region"
        aria-label="Map: click to select a point"
        aria-disabled={disabled || undefined}
      />
      <RegionalMapContext
        map={ready ? map.current : null}
        location={location}
      />
    </div>
  );
}
