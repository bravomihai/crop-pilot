"use client";
import { useEffect, useRef } from "react";
import type { Map as LeafletMap, CircleMarker, Polygon } from "leaflet";
import type { Location } from "@fieldshift/contracts";

type Position = [number, number];

export default function LocationMap({
  location,
  onSelect,
  fieldBoundary,
  onBoundaryChange,
  drawingBoundary,
}: {
  location?: Location;
  onSelect: (value: Location) => void;
  fieldBoundary: Position[];
  onBoundaryChange: (value: Position[]) => void;
  drawingBoundary: boolean;
}) {
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
        const latitude = Number(event.latlng.lat.toFixed(6));
        const longitude = Number(event.latlng.lng.toFixed(6));
        if (drawingRef.current) {
          const point: Position = [longitude, latitude];
          boundaryCallback.current([
            ...boundaryRef.current,
            point,
          ]);
          return;
        }
        callback.current({
          name: "Punct selectat pe hartă",
          latitude,
          longitude,
        });
      });
    });
    return () => {
      disposed = true;
      map.current?.remove();
      map.current = null;
      marker.current = null;
      polygon.current = null;
    };
  }, []);
  useEffect(() => {
    let disposed = false;
    if (!location) {
      marker.current?.remove();
      marker.current = null;
    } else {
      void import("leaflet").then((L) => {
        if (disposed || !map.current) return;
        marker.current?.remove();
        marker.current = L.circleMarker(
          [location.latitude, location.longitude],
          { radius: 8, color: "#16634b", fillOpacity: 0.8 },
        ).addTo(map.current);
        map.current.setView([location.latitude, location.longitude], 10);
      });
    }
    return () => {
      disposed = true;
    };
  }, [location]);
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
  }, [fieldBoundary]);
  return (
    <div
      ref={container}
      className="map"
      role="region"
      aria-label="Hartă România: selectează un punct sau trasează conturul terenului"
    />
  );
}
