/** Presentation fixtures only. These formulas are not agronomic models or NASA observations. */
export const DEMO_CROPS = [
  { id: "maize", name: "Maize", base: 92, heat: 35, dry: 40, wet: 10 },
  {
    id: "winter_wheat",
    name: "Winter wheat",
    base: 88,
    heat: 26,
    dry: 22,
    wet: 16,
  },
  { id: "sunflower", name: "Sunflower", base: 91, heat: 18, dry: 18, wet: 25 },
  { id: "rapeseed", name: "Rapeseed", base: 86, heat: 32, dry: 30, wet: 22 },
  { id: "soybean", name: "Soybean", base: 89, heat: 30, dry: 36, wet: 15 },
  { id: "winter_barley", name: "Barley", base: 87, heat: 24, dry: 24, wet: 20 },
  { id: "alfalfa", name: "Alfalfa", base: 85, heat: 20, dry: 20, wet: 25 },
  { id: "sorghum", name: "Sorghum", base: 88, heat: 10, dry: 10, wet: 26 },
  { id: "oats", name: "Oats", base: 83, heat: 25, dry: 22, wet: 15 },
  { id: "pea", name: "Pea", base: 84, heat: 26, dry: 22, wet: 18 },
  {
    id: "sugar_beet",
    name: "Sugar beet",
    base: 90,
    heat: 32,
    dry: 38,
    wet: 14,
  },
] as const;

export type DemoCropId = (typeof DEMO_CROPS)[number]["id"];
export type ClimateScenario = { temperature: number; rainfall: number };
const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

export function visualScenario({ temperature, rainfall }: ClimateScenario) {
  const heat = clamp(temperature, 0, 5) / 5;
  const dry = clamp(-rainfall, 0, 50) / 50;
  const wet = clamp(rainfall, 0, 50) / 50;
  const stress = clamp(heat * 0.55 + dry * 0.65 + wet * 0.15, 0, 1);
  const level =
    stress >= 0.75
      ? "severe"
      : stress >= 0.5
        ? "high"
        : stress >= 0.22
          ? "moderate"
          : "normal";
  const colors = {
    normal: "#22c55e",
    moderate: "#eab308",
    high: "#f97316",
    severe: "#ef4444",
  };
  const labels = {
    normal: "Baseline scenario",
    moderate: "Moderate stress",
    high: "High stress",
    severe: "Severe stress",
  };
  return {
    stress,
    level,
    color: colors[level],
    label: labels[level],
    opacity: 0.22 + stress * 0.28,
    waterSaving: Math.round(75 - stress * 25),
    moisture: Math.round(clamp(68 + rainfall * 0.42 - temperature * 4, 5, 95)),
    temperature: (25.3 + clamp(temperature, 0, 5)).toFixed(1),
    ndvi: clamp(0.72 - stress * 0.24, 0, 1).toFixed(2),
    crops: DEMO_CROPS.map((crop) => ({
      ...crop,
      score: Math.round(
        clamp(
          crop.base - heat * crop.heat - dry * crop.dry - wet * crop.wet,
          5,
          98,
        ),
      ),
    })).sort((a, b) => b.score - a.score),
  };
}
