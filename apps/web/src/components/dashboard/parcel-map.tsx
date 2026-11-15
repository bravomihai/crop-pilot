"use client";

import { useEffect, useRef, useState } from "react";
import type { Location } from "@croppilot/contracts";
import type { Map as LeafletMap } from "leaflet";
import {
  addCorner,
  addFreehand,
  createParcel,
  MAX_BOUNDARY_POINTS,
  MAX_FIELD_PARTS,
  tracePoints,
  type Coordinate,
  type DrawSegment,
  type FieldSelection,
} from "@/lib/parcel-geometry";
import Icon from "./icon";
import RegionalMapContext from "../regional-map-context";

const MAX_MAP_ZOOM = 17;

type Commands = {
  start: () => void;
  startPart: () => void;
  finish: () => void;
  undo: () => void;
  cancel: () => void;
  clear: () => void;
};
type Props = {
  view: Location;
  zoom?: number;
  selection: FieldSelection | null;
  color: string;
  opacity: number;
  onSelect: (selection: FieldSelection | null) => void;
  onDrawingChange: (drawing: boolean) => void;
  parts?: FieldSelection[];
  onAddPart?: (part: FieldSelection) => void;
};

export default function ParcelMap(props: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<LeafletMap | null>(null);
  const commands = useRef<Commands | null>(null);
  const renderSelection = useRef<(() => void) | null>(null);
  const latest = useRef(props);
  const appliedView = useRef(props.view);
  latest.current = props;
  const [ready, setReady] = useState(false);
  const [drawing, setDrawing] = useState(false);
  const [vertices, setVertices] = useState(0);
  const [message, setMessage] = useState("Draw your field boundary on the map.");
  const [tileError, setTileError] = useState(false);
  const [referenceError, setReferenceError] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);

  useEffect(() => {
    let disposed = false;
    let cleanup = () => {};
    void import("leaflet")
      .then((L) => {
        if (disposed || !container.current) return;
        const element = container.current;
        const initial = latest.current.view;
        const instance = L.map(element, {
          zoomControl: false,
          preferCanvas: true,
          maxZoom: MAX_MAP_ZOOM,
        }).setView([initial.latitude, initial.longitude], latest.current.zoom ?? 13);
        map.current = instance;
        L.control.zoom({ position: "bottomright" }).addTo(instance);
        const imagery = L.tileLayer(
          "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
          {
            maxZoom: MAX_MAP_ZOOM,
            attribution:
              'Imagery &copy; <a href="https://www.esri.com/">Esri</a>, Maxar, Earthstar Geographics, and the GIS User Community',
          },
        );
        const labels = L.tileLayer(
          "https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
          {
            maxZoom: MAX_MAP_ZOOM,
            attribution: "Labels &copy; Esri",
            pane: "overlayPane",
          },
        );
        const roads = L.tileLayer(
          "https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}",
          {
            maxZoom: MAX_MAP_ZOOM,
            attribution:
              "Roads &copy; Esri, HERE, Garmin, OpenStreetMap contributors",
            pane: "overlayPane",
          },
        );
        const satellite = L.layerGroup([imagery, roads, labels]).addTo(
          instance,
        );
        const streets = L.tileLayer(
          "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
          {
            maxZoom: MAX_MAP_ZOOM,
            attribution:
              '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
          },
        );
        L.control
          .layers(
            { Satellite: satellite, "Street map": streets },
            {},
            { position: "bottomright" },
          )
          .addTo(instance);
        L.control
          .scale({ imperial: false, position: "bottomright" })
          .addTo(instance);
        imagery.on("tileerror", () => {
          if (!disposed) setTileError(true);
        });
        for (const reference of [labels, roads])
          reference.on("tileerror", () => {
            if (!disposed) setReferenceError(true);
          });
        const selected = L.featureGroup().addTo(instance);
        const sketch = L.featureGroup().addTo(instance);
        const guide = L.polyline([], {
          color: "#fff",
          weight: 2,
          dashArray: "7 7",
          interactive: false,
        }).addTo(instance);
        let active = false;
        let drawingPart = false;
        let segments: DrawSegment[] = [];
        let gesture: {
          id: number;
          origin: { x: number; y: number };
          last: { x: number; y: number };
          points: Coordinate[];
          freehand: boolean;
          tolerance: number;
        } | null = null;

        function coordinate(event: PointerEvent): Coordinate {
          const point = instance.containerPointToLatLng(
            instance.mouseEventToContainerPoint(event),
          );
          return [point.lng, point.lat];
        }
        function latLngs(points: Coordinate[]): [number, number][] {
          return points.map(([longitude, latitude]) => [latitude, longitude]);
        }
        function release() {
          if (gesture && element.hasPointerCapture(gesture.id))
            element.releasePointerCapture(gesture.id);
          gesture = null;
        }
        function interactions(enabled: boolean) {
          for (const handler of [
            instance.dragging,
            instance.doubleClickZoom,
            instance.touchZoom,
            instance.boxZoom,
            instance.scrollWheelZoom,
            instance.keyboard,
          ]) {
            if (enabled) handler.enable();
            else handler.disable();
          }
          element.classList.toggle("is-drawing", !enabled);
          element.style.touchAction = enabled ? "" : "none";
        }
        function paintSketch(extra: Coordinate[] = []) {
          sketch.clearLayers();
          const points = [...tracePoints(segments), ...extra];
          if (points.length > 1)
            L.polyline(latLngs(points), {
              color: "#ffffff",
              weight: 3,
              interactive: false,
            }).addTo(sketch);
          const anchors = [
            points[0],
            ...segments.map((segment) => segment.points.at(-1)),
          ].filter((point): point is Coordinate => Boolean(point));
          anchors.forEach((point, index) =>
            L.circleMarker([point[1], point[0]], {
              radius: index === 0 ? 7 : 4,
              color: "#fff",
              weight: 2,
              fillColor: "#123c2f",
              fillOpacity: 1,
              interactive: false,
            }).addTo(sketch),
          );
          const count = tracePoints(segments).length;
          setVertices(count);
          if (count >= MAX_BOUNDARY_POINTS)
            setMessage(
              `The ${MAX_BOUNDARY_POINTS}-point limit is reached. Finish the outline or undo a gesture.`,
            );
        }
        function resetSketch() {
          segments = [];
          release();
          sketch.clearLayers();
          guide.setLatLngs([]);
          setVertices(0);
        }
        function stop() {
          active = false;
          resetSketch();
          interactions(true);
          setDrawing(false);
          latest.current.onDrawingChange(false);
        }
        function finish() {
          if (!active) return;
          try {
            const field = createParcel(tracePoints(segments), drawingPart ? `Part ${(latest.current.parts?.length ?? 0) + 1}` : "Selected field");
            if (drawingPart) latest.current.onAddPart?.(field);
            else latest.current.onSelect(field);
            stop();
            if (!drawingPart)
              instance.fitBounds(L.latLngBounds(latLngs(field.boundary!)), {
                padding: [36, 36],
                maxZoom: 17,
              });
            setMessage(
              `${drawingPart ? "Part" : "Field"} selected. Approximate area: ${field.areaHectares!.toFixed(2)} ha. In computed mode, soil and terrain use up to three samples inside the boundary.`,
            );
          } catch (cause) {
            setMessage(
              cause instanceof Error
                ? cause.message
                : "This outline could not be completed. Try again.",
            );
          }
        }
        commands.current = {
          start() {
            resetSketch();
            drawingPart = false;
            active = true;
            selected.clearLayers();
            latest.current.onSelect(null);
            interactions(false);
            setDrawing(true);
            latest.current.onDrawingChange(true);
            setMessage(
              `Click for corners; hold and drag for curves. Click the first point, double-click, or choose Finish to close. Maximum ${MAX_BOUNDARY_POINTS} points.`,
            );
            element.focus();
          },
          startPart() {
            resetSketch();
            drawingPart = true;
            active = true;
            interactions(false);
            setDrawing(true);
            latest.current.onDrawingChange(true);
            setMessage("Draw a closed part inside the field without overlapping another part.");
            element.focus();
          },
          finish,
          undo() {
            release();
            segments = segments.slice(0, -1);
            guide.setLatLngs([]);
            paintSketch();
            setMessage(
              "Last drawing gesture removed. Continue tracing or finish the outline.",
            );
          },
          cancel() {
            stop();
            setMessage(
              "Drawing cancelled. Start again to trace the field boundary.",
            );
          },
          clear() {
            stop();
            selected.clearLayers();
            latest.current.onSelect(null);
            setMessage("Field cleared. Draw a new boundary to continue.");
          },
        };
        renderSelection.current = () => {
          selected.clearLayers();
          const { selection, color, opacity, parts = [] } = latest.current;
          if (!selection || (active && !drawingPart)) return;
          if (selection.boundary)
            L.polygon(latLngs(selection.boundary), {
              color,
              weight: 3,
              fillColor: color,
              fillOpacity: opacity,
            }).addTo(selected);
          parts.forEach((part, index) => {
            if (!part.boundary) return;
            L.polygon(latLngs(part.boundary), {
              color: "#ffffff",
              weight: 2,
              fillColor: color,
              fillOpacity: 0.4,
            }).bindTooltip(`Part ${index + 1}`, { permanent: true }).addTo(selected);
          });
        };
        function down(event: PointerEvent) {
          if (
            !active ||
            !event.isPrimary ||
            event.button !== 0 ||
            (event.target as Element).closest(".leaflet-control")
          )
            return;
          if (tracePoints(segments).length >= MAX_BOUNDARY_POINTS) {
            setMessage(
              `The ${MAX_BOUNDARY_POINTS}-point limit is reached. Finish the outline or undo a gesture.`,
            );
            return;
          }
          event.preventDefault();
          event.stopPropagation();
          const point = instance.mouseEventToContainerPoint(event);
          const longitudeTolerance = Math.abs(
            instance.containerPointToLatLng([point.x + 2, point.y]).lng -
              coordinate(event)[0],
          );
          gesture = {
            id: event.pointerId,
            origin: point,
            last: point,
            points: [coordinate(event)],
            freehand: false,
            tolerance: longitudeTolerance,
          };
          element.setPointerCapture(event.pointerId);
        }
        function move(event: PointerEvent) {
          if (!active) return;
          if (gesture && gesture.id !== event.pointerId) return;
          const point = coordinate(event);
          const pixel = instance.mouseEventToContainerPoint(event);
          if (gesture) {
            event.preventDefault();
            if (
              Math.hypot(
                pixel.x - gesture.origin.x,
                pixel.y - gesture.origin.y,
              ) >= 5
            )
              gesture.freehand = true;
            if (
              gesture.freehand &&
              Math.hypot(pixel.x - gesture.last.x, pixel.y - gesture.last.y) >=
                3 &&
              gesture.points.length < 5000
            ) {
              gesture.points.push(point);
              gesture.last = pixel;
              paintSketch(gesture.points);
            }
          }
          const last = gesture?.freehand
            ? gesture.points.at(-1)
            : tracePoints(segments).at(-1);
          guide.setLatLngs(last ? latLngs([last, point]) : []);
        }
        function up(event: PointerEvent) {
          if (!active || !gesture || gesture.id !== event.pointerId) return;
          event.preventDefault();
          const point = coordinate(event);
          const current = gesture;
          release();
          const pixel = instance.mouseEventToContainerPoint(event);
          const moved =
            Math.hypot(
              pixel.x - current.origin.x,
              pixel.y - current.origin.y,
            ) >= 5;
          const points = tracePoints(segments);
          if (
            !current.freehand &&
            !moved &&
            points.length >= 3 &&
            instance
              .latLngToContainerPoint([points[0][1], points[0][0]])
              .distanceTo(pixel) <= 12
          ) {
            finish();
            return;
          }
          const updated =
            current.freehand || moved
              ? addFreehand(
                  segments,
                  [...current.points, point],
                  current.tolerance,
                )
              : addCorner(segments, point);
          guide.setLatLngs([]);
          if (tracePoints(updated).length > MAX_BOUNDARY_POINTS) {
            setMessage(
              `That stroke exceeds the ${MAX_BOUNDARY_POINTS}-point limit. Undo a gesture or redraw a shorter section.`,
            );
            return;
          }
          segments = updated;
          paintSketch();
        }
        function cancelPointer() {
          release();
          if (active) paintSketch();
        }
        function doubleClick(event: MouseEvent) {
          if (
            active &&
            !(event.target as Element).closest(".leaflet-control")
          ) {
            event.preventDefault();
            event.stopPropagation();
            finish();
          }
        }
        function key(event: KeyboardEvent) {
          if (!active) return;
          if (event.key === "Escape") {
            event.preventDefault();
            commands.current?.cancel();
          }
          if (event.key === "Enter") {
            event.preventDefault();
            finish();
          }
          if (
            (event.ctrlKey || event.metaKey) &&
            event.key.toLowerCase() === "z"
          ) {
            event.preventDefault();
            commands.current?.undo();
          }
        }
        element.addEventListener("pointerdown", down, true);
        element.addEventListener("pointermove", move);
        element.addEventListener("pointerup", up);
        element.addEventListener("pointercancel", cancelPointer);
        element.addEventListener("lostpointercapture", cancelPointer);
        element.addEventListener("dblclick", doubleClick, true);
        element.addEventListener("keydown", key);
        window.addEventListener("blur", cancelPointer);
        const observer = new ResizeObserver(() => instance.invalidateSize());
        observer.observe(element);
        renderSelection.current();
        setReady(true);
        cleanup = () => {
          release();
          observer.disconnect();
          element.removeEventListener("pointerdown", down, true);
          element.removeEventListener("pointermove", move);
          element.removeEventListener("pointerup", up);
          element.removeEventListener("pointercancel", cancelPointer);
          element.removeEventListener("lostpointercapture", cancelPointer);
          element.removeEventListener("dblclick", doubleClick, true);
          element.removeEventListener("keydown", key);
          window.removeEventListener("blur", cancelPointer);
          selected.clearLayers();
          instance.remove();
          map.current = null;
          commands.current = null;
          renderSelection.current = null;
        };
      })
      .catch(() => {
        if (!disposed)
          setMessage("The map could not load. Refresh the page to try again.");
      });
    return () => {
      disposed = true;
      cleanup();
    };
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (appliedView.current !== props.view) commands.current?.cancel();
    appliedView.current = props.view;
    map.current?.setView([props.view.latitude, props.view.longitude], props.zoom ?? 13);
  }, [props.view, props.zoom, ready]);
  useEffect(() => {
    renderSelection.current?.();
  }, [props.selection, props.parts, props.color, props.opacity, ready]);

  return (
    <section className="dashboard-card map-card" aria-labelledby="map-title">
      <div className="card-heading">
        <div>
          <span className="heading-icon">
            <Icon name="satellite" />
          </span>
          <h2 id="map-title">Your field, from above</h2>
        </div>
        <span className="subtle-badge">Esri imagery</span>
      </div>
      <div className="map-toolbar">
        {!drawing ? (
          <button
            className="button button--primary"
            type="button"
            disabled={!ready}
            onClick={() => commands.current?.start()}
          >
            <Icon name="draw" size={16} />
            {props.selection ? "Redraw field" : "Draw field"}
          </button>
        ) : (
          <>
            <button
              className="button button--primary"
              type="button"
              disabled={vertices < 3}
              onClick={() => commands.current?.finish()}
            >
              <Icon name="check" size={16} />
              Finish outline
            </button>
            <button
              className="button button--secondary"
              type="button"
              disabled={vertices === 0}
              onClick={() => commands.current?.undo()}
            >
              Undo
            </button>
            <button
              className="text-button"
              type="button"
              onClick={() => commands.current?.cancel()}
            >
              Cancel
            </button>
          </>
        )}
        {!drawing && props.selection && props.onAddPart && (
          <button
            className="button button--secondary"
            type="button"
            disabled={!ready || (props.parts?.length ?? 0) >= MAX_FIELD_PARTS}
            onClick={() => commands.current?.startPart()}
          >
            Draw field part
          </button>
        )}
        <button
          className="map-clear"
          type="button"
          disabled={!ready || (!drawing && !props.selection)}
          onClick={() => commands.current?.clear()}
          aria-label="Clear field and drawing"
        >
          <Icon name="trash" size={17} />
        </button>
      </div>
      <div
        className="satellite-map"
        ref={container}
        tabIndex={0}
        role="region"
        aria-label="Satellite map. Draw the field boundary using corner clicks and drags for curved edges."
        aria-describedby="map-instructions"
      />
      <div className="map-caption">
        <span>
          <span className="map-key" />
          Your selected field
        </span>
        <span>WGS84 · approximate area</span>
      </div>
      <p className="map-instructions" id="map-instructions" role="status">
        {!ready
          ? message.startsWith("The map")
            ? message
            : "Loading the satellite map…"
          : message}
      </p>
      {drawing && (
        <p className="map-shortcuts">
          Enter: finish · Ctrl/⌘ Z: undo · Esc: cancel · {vertices} points
        </p>
      )}
      {tileError && (
        <p className="tile-warning">
          Satellite imagery could not load. Check your connection or choose
          Street map from the layer control.
        </p>
      )}
      {referenceError && !tileError && (
        <p className="tile-warning">
          Some road or place labels could not load. Satellite imagery and
          drawing remain separate from these reference layers.
        </p>
      )}
      <details
        className="map-context-menu"
        onToggle={(event) => setContextOpen(event.currentTarget.open)}
      >
        <summary aria-label="NASA layers">
          <Icon name="satellite" size={17} />
          <span>NASA layers</span>
        </summary>
        {contextOpen && (
          <div className="map-context-content">
            <RegionalMapContext
              map={ready ? map.current : null}
              location={props.selection?.location}
            />
          </div>
        )}
      </details>
    </section>
  );
}
