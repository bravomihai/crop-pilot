"use client";
import { useEffect, useId, useState } from "react";
import type { Map as LeafletMap } from "leaflet";
import type { Location } from "@croppilot/contracts";
import {
  advertisedDate,
  contextMonths,
  GIBS_CAPABILITIES_URL,
  GIBS_CHOICES,
  gibsTileUrl,
  isCovered,
  parseGibsCapabilities,
  powerCell,
  RULE_ZONES,
  type GibsMetadata,
} from "@/lib/regional-context";

function OfficialLegend({ layer }: { layer: GibsMetadata }) {
  const [labels, setLabels] = useState("");
  useEffect(() => {
    if (!layer.legend) return;
    const controller = new AbortController();
    void fetch(layer.legend, {
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]),
    })
      .then((response) => {
        if (!response.ok) throw new Error();
        return response.text();
      })
      .then((xml) => {
        const doc = new DOMParser().parseFromString(xml, "image/svg+xml");
        setLabels(
          Array.from(doc.getElementsByTagNameNS("*", "text"))
            .map((node) => node.textContent)
            .join(" · "),
        );
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setLabels(
            "Legend scale could not be loaded. Open the official legend to inspect it.",
          );
      });
    return () => controller.abort();
  }, [layer.legend]);
  if (!layer.legend) return <p>No legend is advertised for this layer.</p>;
  return (
    <div className="gibs-legend">
      <img
        src={layer.legend}
        alt={`Official NASA legend for ${layer.title}. ${labels}`}
        loading="lazy"
      />
      <p>{labels || "Loading official legend labels…"}</p>
      <a href={layer.legend} target="_blank" rel="noreferrer">
        Open official legend (new tab)
      </a>
    </div>
  );
}

export default function RegionalMapContext({
  map,
  location,
}: {
  map: LeafletMap | null;
  location?: Location;
}) {
  const id = useId();
  const [metadata, setMetadata] = useState<GibsMetadata[]>([]);
  const [catalogStatus, setCatalogStatus] = useState(
    "Loading NASA layer availability…",
  );
  const [retry, setRetry] = useState(0);
  const [months] = useState(() => contextMonths());
  const [month, setMonth] = useState(59);
  const [playing, setPlaying] = useState(false);
  const [enabled, setEnabled] = useState<Record<string, boolean>>({});
  const [opacity, setOpacity] = useState<Record<string, number>>({});
  const [errors, setErrors] = useState<Record<string, boolean>>({});
  useEffect(() => {
    const controller = new AbortController();
    setCatalogStatus("Loading NASA layer availability…");
    void fetch(GIBS_CAPABILITIES_URL, {
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(20000)]),
    })
      .then((response) => {
        if (!response.ok) throw new Error();
        return response.text();
      })
      .then((xml) => {
        if (controller.signal.aborted) return;
        const layers = parseGibsCapabilities(xml);
        setMetadata(layers);
        setCatalogStatus(
          layers.length === 3
            ? "Availability and legends read from NASA GIBS capabilities."
            : "Some requested NASA layers are unavailable in the capabilities document.",
        );
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setMetadata([]);
          setCatalogStatus(
            "NASA context is unavailable. The base map and planning form remain usable.",
          );
        }
      });
    return () => controller.abort();
  }, [retry]);
  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(
      () => setMonth((value) => (value + 1) % months.length),
      1200,
    );
    return () => clearInterval(timer);
  }, [playing, months.length]);
  useEffect(() => {
    if (!map) return;
    let disposed = false;
    let remove = () => {};
    void import("leaflet")
      .then((L) => {
        if (disposed) return;
        const group = L.layerGroup().addTo(map);
        for (const zone of RULE_ZONES)
          L.rectangle(
            [
              [zone.lat[0], zone.lon[0]],
              [zone.lat[1], zone.lon[1]],
            ],
            {
              color: "#64748b",
              weight: 1,
              dashArray: "4 5",
              fillOpacity: 0.04,
              interactive: true,
            },
          )
            .bindTooltip(`${zone.name} — crop-rule coverage`)
            .addTo(group);
        if (location)
          L.rectangle(powerCell(location), {
            color: "#a16207",
            weight: 2,
            dashArray: "8 4",
            fillOpacity: 0.04,
          })
            .bindTooltip(
              "The weather used for this field is one value for this whole area (NASA POWER, about 50 km).",
            )
            .addTo(group);
        remove = () => {
          group.remove();
        };
      })
      .catch(() => {});
    return () => {
      disposed = true;
      remove();
    };
  }, [map, location]);
  useEffect(() => {
    if (!map || !metadata.length) return;
    let disposed = false;
    let remove = () => {};
    setErrors({});
    void import("leaflet")
      .then((L) => {
        if (disposed) return;
        if (!map.getPane("nasa-context")) {
          const pane = map.createPane("nasa-context");
          pane.style.zIndex = "350";
          pane.style.pointerEvents = "none";
        }
        const group = L.layerGroup().addTo(map);
        for (const layer of metadata) {
          const date = advertisedDate(layer.values, months[month]);
          if (!enabled[layer.id] || !date) continue;
          const tiles = L.tileLayer(gibsTileUrl(layer, date), {
            maxNativeZoom: layer.maxNativeZoom,
            maxZoom: 20,
            tileSize: layer.tileSize,
            opacity: (opacity[layer.id] ?? 55) / 100,
            pane: "nasa-context",
            attribution: "NASA GIBS / EOSDIS",
          });
          tiles.on("tileerror", () => {
            if (!disposed)
              setErrors((previous) => ({ ...previous, [layer.id]: true }));
          });
          tiles.addTo(group);
        }
        remove = () => group.remove();
      })
      .catch(() => {});
    return () => {
      disposed = true;
      remove();
    };
  }, [map, metadata, enabled, opacity, month, months]);
  return (
    <section className="regional-map-context" aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`}>NASA regional context</h3>
      <p>
        <strong>Regional context (km-scale), not a field measurement.</strong>{" "}
        These dated NASA overlays are separate from the dashboard's fictional
        KPI cards and crop scores.
      </p>
      {location && !isCovered(location) && (
        <p className="coverage-warning" role="status">
          This point is outside the locally documented crop-rule zones. Plans
          use provisional Romania-wide temperature-profile rules here and need
          local review.
        </p>
      )}
      <p className="context-line-legend">
        Dashed grey rectangles: crop-rule zones · dashed amber rectangle: NASA
        POWER weather cell.
      </p>
      <details>
        <summary>Explore NASA layers and dates</summary>
        <p className="catalog-status" role="status">
          {catalogStatus}
        </p>
        <button
          className="text-button"
          type="button"
          onClick={() => setRetry((value) => value + 1)}
        >
          Refresh layer availability
        </button>
        <label htmlFor={`${id}-month`}>
          Month: <output>{months[month]}</output>
          <input
            id={`${id}-month`}
            type="range"
            min={0}
            max={59}
            step={1}
            value={month}
            aria-valuetext={months[month]}
            onChange={(event) => {
              setPlaying(false);
              setMonth(Number(event.target.value));
            }}
          />
        </label>
        <p>
          Last five years. Each month shows an advertised daily snapshot, not a
          monthly average. Missing dates are not substituted.
        </p>
        <button
          className="button button--secondary"
          type="button"
          aria-pressed={playing}
          onClick={() => {
            if (!playing && month === 59) setMonth(0);
            setPlaying((value) => !value);
          }}
        >
          {playing ? "Pause" : "Play"}
        </button>
        <div className="gibs-layer-options">
          {GIBS_CHOICES.map((choice) => {
            const layer = metadata.find((item) => item.id === choice.id);
            const date = layer
              ? advertisedDate(layer.values, months[month])
              : null;
            return (
              <div key={choice.id} className="gibs-layer-option">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={enabled[choice.id] ?? false}
                    disabled={!layer || !map}
                    onChange={(event) =>
                      setEnabled({
                        ...enabled,
                        [choice.id]: event.target.checked,
                      })
                    }
                  />
                  {choice.label}
                </label>
                {layer ? (
                  <>
                    <p>
                      Snapshot:{" "}
                      {date ?? "No available date advertised for this month"}
                    </p>
                    <label htmlFor={`${id}-${choice.id}-opacity`}>
                      Opacity: {opacity[choice.id] ?? 55}%
                      <input
                        id={`${id}-${choice.id}-opacity`}
                        type="range"
                        min={0}
                        max={100}
                        value={opacity[choice.id] ?? 55}
                        onChange={(event) =>
                          setOpacity({
                            ...opacity,
                            [choice.id]: Number(event.target.value),
                          })
                        }
                      />
                    </label>
                    {errors[choice.id] && (
                      <p role="status">
                        This layer's tiles could not load. You can turn it off;
                        the map and form still work.
                      </p>
                    )}
                    <OfficialLegend layer={layer} />
                  </>
                ) : (
                  <p>
                    Layer unavailable until its capabilities can be verified.
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </details>
    </section>
  );
}
