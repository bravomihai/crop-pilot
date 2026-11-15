import type { RecommendationRequest, RecommendationResult } from "@fieldshift/contracts";
import { HISTORY_SOURCES, RULE_CROPS } from "@/lib/crop-options";

const cropName = (id: string) => RULE_CROPS.find(([crop]) => crop === id)?.[1] ?? id.replace(/_/g, " ");
const sourceName = (id?: string) => HISTORY_SOURCES.find(([source]) => source === id)?.[1];
const signed = (value: number, unit: string) => `${value > 0 ? "+" : ""}${value}${unit}`;
// Local date and time of the viewer (a UTC date can be a day off near midnight in Romania).
const calculatedAt = (iso: string) =>
  new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
const coordinate = (value: number, positive: string, negative: string) =>
  `${Math.abs(value).toFixed(4)}° ${value < 0 ? negative : positive}`;

/** The inputs behind a result, as text rows (used on the printed sheet for the agronomist). */
export function requestRows(request: RecommendationRequest, result: RecommendationResult): [string, string][] {
  const { location, soil, constraints, scenario, priorities } = request;
  const last = request.history.at(-1);
  const previous = last
    ? [cropName(last.crop_id), last.harvest_year && `harvested ${last.harvest_year}`, sourceName(last.source)]
        .filter(Boolean)
        .join(", ")
    : "Not given";
  const soilText = [
    soil?.texture && soil.texture !== "unknown" ? soil.texture : "texture not given",
    soil?.ph != null ? `pH ${soil.ph}` : null,
    soil?.organic_carbon_pct != null ? `organic carbon ${soil.organic_carbon_pct}%` : null,
    soil?.source && soil.source !== "unknown" ? `(${soil.source.replace("_", " ")})` : null,
  ]
    .filter(Boolean)
    .join(", ");
  const weights = (["water", "soil", "climate", "productivity"] as const)
    .filter((key) => priorities[key] !== undefined)
    .map((key) => `${key} ${priorities[key]}/5`)
    .join(", ");
  const hypothetical = scenario.temp_change_c !== 0 || scenario.rain_change_pct !== 0;
  return [
    ["Field", `${location.name ?? "Selected point"} · ${coordinate(location.latitude, "N", "S")}, ${coordinate(location.longitude, "E", "W")}`],
    ["Field available from", request.available_from],
    ["Previous crop", previous],
    ["Current rotation", request.current_rotation?.length ? request.current_rotation.map(cropName).join(" → ") : "Not given"],
    ["Soil", soilText],
    [
      "Irrigation",
      constraints.irrigated
        ? `Available${constraints.max_irrigation_mm != null ? `, up to ${constraints.max_irrigation_mm} mm` : ""}`
        : "Rain-fed",
    ],
    ["Priorities (0–5)", weights],
    ["Crops avoided", constraints.excluded_crops.length ? constraints.excluded_crops.map(cropName).join(", ") : "None"],
    [
      "Climate scenario",
      hypothetical
        ? `${signed(scenario.temp_change_c, " °C")}, ${signed(scenario.rain_change_pct, "% rain")} (hypothetical, not a forecast)`
        : "None (observed past weather)",
    ],
    ["Calculated", `${calculatedAt(result.generated_at)} · ${result.mode === "demo" ? "demo (fictional)" : "computed"} · reference ${result.request_id}`],
  ];
}

/** Printed only: what was entered, so the agronomist can read the sheet on its own. */
export default function RequestSummary({
  request,
  result,
}: {
  request?: RecommendationRequest;
  result: RecommendationResult;
}) {
  if (!request) return null;
  return (
    <section className="request-summary print-only" aria-label="What was entered">
      <h3>What was entered</h3>
      <dl>
        {requestRows(request, result).map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
