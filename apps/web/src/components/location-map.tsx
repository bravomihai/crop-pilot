"use client";
import { useEffect, useRef, useState } from "react";
import type { Map as LeafletMap, CircleMarker, Polygon } from "leaflet";
import type { Location } from "@croppilot/contracts";
import type { Coordinate } from "@/lib/parcel-geometry";
export default function LocationMap({
  location,
  onSelect,
  fieldBoundary = [],
  onBoundaryChange,
  drawingBoundary = false,
  disabled = false,
}: {
  location?: Location;
  onSelect: (value: Location) => void;
  fieldBoundary?: Coordinate[];
  onBoundaryChange?: (value: Coordinate[]) => void;
  drawingBoundary?: boolean;
  disabled?: boolean;
}) {
  const [ready, setReady] = useState(false);
  const container = useRef<HTMLDivElement>(null),
    map = useRef<LeafletMap | null>(null),
    marker = useRef<CircleMarker | null>(null),
    polygon = useRef<Polygon | null>(null);
  const callback = useRef(onSelect);
  callback.current = onSelect;
  const boundaryCallback = useRef(onBoundaryChange);
  boundaryCallback.current = onBoundaryChange;
  const boundaryRef = useRef(fieldBoundary);
  boundaryRef.current = fieldBoundary;
  const drawingRef = useRef(drawingBoundary);
  drawingRef.current = drawingBoundary;
  const disabledRef = useRef(disabled);
  disabledRef.current = disabled;
  useEffect(() => {
    let disposed = false;
    void import("leaflet").then((L) => {
      if (disposed || !container.current) return;
      map.current = L.map(container.current).setView([45.9, 24.9], 6);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map.current);
      map.current.on("click", (event) => {
        if (disabledRef.current) return;
        const latitude = Number(event.latlng.lat.toFixed(6));
        const longitude = Number(event.latlng.lng.toFixed(6));
        if (drawingRef.current) {
          if (boundaryRef.current.length >= 100) return;
          const point: Coordinate = [longitude, latitude];
          boundaryCallback.current?.([
            ...boundaryRef.current,
            point,
          ]);
          return;
        }
        callback.current({
          name: "Point selected on the map",
          latitude,
          longitude,
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
    else {
      marker.current?.remove();
      marker.current = null;
    }
    return () => {
      disposed = true;
    };
  }, [location, ready]);
  useEffect(() => {
    let disposed = false;
    if (fieldBoundary.length < 2) {
      polygon.current?.remove();
      polygon.current = null;
    } else {
      void import("leaflet").then((L) => {
        if (disposed || !map.current) return;
        const points = fieldBoundary.map(
          ([longitude, latitude]) => [latitude, longitude] as [number, number],
        );
        if (polygon.current) {
          polygon.current.setLatLngs(points);
        } else {
          polygon.current = L.polygon(points, {
            color: "#d97706",
            fillOpacity: 0.18,
          }).addTo(map.current);
        }
      });
    }
    return () => {
      disposed = true;
    };
  }, [fieldBoundary, ready]);
  return (
    <div className="location-map-wrap">
      <div
        ref={container}
        className="map"
        role="region"
        aria-label="Map: select a point or draw a field boundary"
        aria-disabled={disabled || undefined}
      />
    </div>
  );
}
