import type { Location } from "@croppilot/contracts";

// Copied from services/engine/fieldshift/evaluator/rules/ro_south.json (region.boxes).
// Keep this display-only copy in sync with the rules owner; do not import engine files.
export const RULE_ZONES = [
  { name: "Oltenia plain", lat: [43.65, 44.55], lon: [22.6, 24.6] },
  { name: "Muntenia plain", lat: [43.6, 44.95], lon: [24.6, 27.2] },
  {
    name: "Bărăgan and lower Siret plain",
    lat: [43.9, 45.5],
    lon: [26.8, 28.2],
  },
  { name: "Dobrogea", lat: [43.7, 45.3], lon: [27.6, 29.7] },
] as const;
export function isCovered(location: Location) {
  return RULE_ZONES.some(
    ({ lat, lon }) =>
      location.latitude >= lat[0] &&
      location.latitude <= lat[1] &&
      location.longitude >= lon[0] &&
      location.longitude <= lon[1],
  );
}
export function powerCell(
  location: Location,
): [[number, number], [number, number]] {
  const latitude = Math.round(location.latitude / 0.5) * 0.5;
  const longitude = Math.round(location.longitude / 0.625) * 0.625;
  return [
    [Math.max(-90, latitude - 0.25), longitude - 0.3125],
    [Math.min(90, latitude + 0.25), longitude + 0.3125],
  ];
}

export const GIBS_CAPABILITIES_URL =
  "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml";
// Identifiers verified against the above capabilities on 2026-11-14.
// Matrix sets, legends, and date availability are read again at runtime, never guessed.
export const GIBS_CHOICES = [
  {
    id: "SMAP_L4_Analyzed_Root_Zone_Soil_Moisture",
    label: "SMAP root-zone soil moisture",
  },
  {
    id: "MODIS_Terra_Land_Surface_Temp_Day",
    label: "MODIS daytime land surface temperature",
  },
  { id: "IMERG_Precipitation_Rate", label: "GPM IMERG precipitation rate" },
] as const;
export type GibsMetadata = {
  id: string;
  title: string;
  matrix: string;
  maxNativeZoom: number;
  style: string;
  tileSize: number;
  values: string[];
  defaultDate: string;
  legend?: string;
};
const children = (node: Element | undefined, name: string) =>
  node
    ? Array.from(node.children).filter((child) => child.localName === name)
    : [];
const text = (node: Element | undefined, name: string) =>
  children(node, name)[0]?.textContent?.trim() ?? "";
export function parseGibsCapabilities(xml: string): GibsMetadata[] {
  const doc = new DOMParser().parseFromString(xml, "application/xml");
  if (doc.getElementsByTagName("parsererror").length)
    throw new Error("NASA capabilities could not be read.");
  const layers = Array.from(doc.getElementsByTagNameNS("*", "Layer"));
  const matrices = Array.from(doc.getElementsByTagNameNS("*", "Contents"))[0];
  if (!matrices) throw new Error("NASA capabilities have no layer contents.");
  return GIBS_CHOICES.flatMap(({ id }) => {
    const layer = layers.find(
      (candidate) => text(candidate, "Identifier") === id,
    );
    if (
      !layer ||
      !children(layer, "Format").some(
        (format) => format.textContent === "image/png",
      )
    )
      return [];
    const matrixId = text(
      children(layer, "TileMatrixSetLink")[0],
      "TileMatrixSet",
    );
    const matrix = children(matrices, "TileMatrixSet").find(
      (candidate) => text(candidate, "Identifier") === matrixId,
    );
    const dimension = children(layer, "Dimension").find(
      (candidate) => text(candidate, "Identifier") === "Time",
    );
    const style = children(layer, "Style").find(
      (candidate) => candidate.getAttribute("isDefault") === "true",
    );
    if (
      !matrix ||
      !dimension ||
      !style ||
      !text(matrix, "SupportedCRS").endsWith(":3857")
    )
      return [];
    const levels = children(matrix, "TileMatrix");
    const maxNativeZoom = Math.max(
      ...levels.map((level) => Number(text(level, "Identifier"))),
    );
    const legendNode = children(style, "LegendURL").find((candidate) =>
      candidate
        .getAttributeNS("http://www.w3.org/1999/xlink", "role")
        ?.endsWith("/horizontal"),
    );
    const href =
      legendNode?.getAttributeNS("http://www.w3.org/1999/xlink", "href") ??
      undefined;
    const legend = href?.startsWith("https://gibs.earthdata.nasa.gov/")
      ? href
      : undefined;
    if (!Number.isFinite(maxNativeZoom) || !levels.length) return [];
    return [
      {
        id,
        title: text(layer, "Title"),
        matrix: matrixId,
        maxNativeZoom,
        style: text(style, "Identifier"),
        tileSize: Number(text(levels[0], "TileWidth")),
        values: children(dimension, "Value").map(
          (value) => value.textContent?.trim() ?? "",
        ),
        defaultDate: text(dimension, "Default"),
        legend,
      },
    ];
  });
}

export function contextMonths(now = new Date()) {
  return Array.from({ length: 60 }, (_, index) =>
    new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - 59 + index, 1))
      .toISOString()
      .slice(0, 7),
  );
}

/** Select the latest advertised daily snapshot within the selected month, including gaps. */
export function advertisedDate(values: string[], month: string): string | null {
  const [year, number] = month.split("-").map(Number);
  if (!year || !number || number > 12) return null;
  const monthStart = Date.UTC(year, number - 1, 1);
  const monthEnd = Date.UTC(year, number, 1) - 86_400_000;
  let best: number | null = null;
  for (const value of values) {
    const [start, end, duration] = value.split("/");
    const first = Date.parse(start.slice(0, 10));
    if (!Number.isFinite(first)) continue;
    if (!end) {
      if (first >= monthStart && first <= monthEnd)
        best = Math.max(best ?? first, first);
      continue;
    }
    const days = /^P(\d+)D$/.exec(duration ?? "");
    const last = Date.parse(end.slice(0, 10));
    if (!days || !Number(days[1]) || !Number.isFinite(last)) continue;
    const step = Number(days[1]) * 86_400_000;
    const limit = Math.min(last, monthEnd);
    const candidate = first + Math.floor((limit - first) / step) * step;
    if (candidate >= Math.max(first, monthStart) && candidate <= limit)
      best = Math.max(best ?? candidate, candidate);
  }
  return best === null ? null : new Date(best).toISOString().slice(0, 10);
}

export function gibsTileUrl(layer: GibsMetadata, date: string) {
  return `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/${encodeURIComponent(layer.id)}/${encodeURIComponent(layer.style)}/${date}/${encodeURIComponent(layer.matrix)}/{z}/{y}/{x}.png`;
}
