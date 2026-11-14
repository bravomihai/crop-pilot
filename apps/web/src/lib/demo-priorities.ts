import {
  visualScenario,
  type ClimateScenario,
  type DemoCropId,
} from "./dashboard-scenario";

/** Local presentation settings, deliberately separate from the engine contract. */
export type FarmingPriorities = {
  investment: number;
  water: number;
  regeneration: number;
  logistics: number;
  cleanup: number;
};

export const DEFAULT_FARMING_PRIORITIES: FarmingPriorities = {
  investment: 50,
  water: 50,
  regeneration: 50,
  logistics: 50,
  cleanup: 50,
};

export const PRIORITY_CONTROLS = [
  {
    key: "investment",
    label: "Investment budget",
    low: "Low inputs",
    high: "Intensive production",
    description:
      "Lower settings favour low-input options such as oats and pea. Higher settings allow more intensive crops.",
    icon: "budget",
  },
  {
    key: "water",
    label: "Water reserve",
    low: "Drought risk",
    high: "Water available",
    description:
      "Lower settings favour the demo's drought-tolerant profiles, such as sorghum and sunflower.",
    icon: "drop",
  },
  {
    key: "regeneration",
    label: "Soil regeneration",
    low: "Immediate returns",
    high: "Soil health",
    description:
      "Shift from the sample cash-crop profiles towards legumes such as pea and alfalfa.",
    icon: "leaf",
  },
  {
    key: "logistics",
    label: "Time & logistics",
    low: "Low maintenance",
    high: "More interventions",
    description:
      "Lower settings favour crops with fewer sample field operations. Higher settings allow more intensive management.",
    icon: "history",
  },
  {
    key: "cleanup",
    label: "Field cleanup need",
    low: "Normal pressure",
    high: "High pressure",
    description:
      "High settings require a demo profile that allows inter-row cultivation or a crop-specific cleanup programme. This is not herbicide advice.",
    icon: "field",
  },
] as const;

/** Entirely fictional profiles; no costs, profits, pesticide efficacy, or agronomy are estimated. */
const PROFILES: Record<DemoCropId, FarmingPriorities> = {
  maize: {
    investment: 85,
    water: 85,
    regeneration: 20,
    logistics: 85,
    cleanup: 85,
  },
  winter_wheat: {
    investment: 35,
    water: 45,
    regeneration: 25,
    logistics: 25,
    cleanup: 35,
  },
  sunflower: {
    investment: 45,
    water: 25,
    regeneration: 25,
    logistics: 55,
    cleanup: 85,
  },
  rapeseed: {
    investment: 65,
    water: 55,
    regeneration: 30,
    logistics: 70,
    cleanup: 45,
  },
  soybean: {
    investment: 65,
    water: 70,
    regeneration: 85,
    logistics: 65,
    cleanup: 80,
  },
  winter_barley: {
    investment: 35,
    water: 40,
    regeneration: 30,
    logistics: 30,
    cleanup: 35,
  },
  alfalfa: {
    investment: 40,
    water: 45,
    regeneration: 95,
    logistics: 50,
    cleanup: 30,
  },
  sorghum: {
    investment: 40,
    water: 20,
    regeneration: 30,
    logistics: 45,
    cleanup: 85,
  },
  oats: {
    investment: 15,
    water: 35,
    regeneration: 45,
    logistics: 15,
    cleanup: 25,
  },
  pea: {
    investment: 20,
    water: 40,
    regeneration: 90,
    logistics: 25,
    cleanup: 35,
  },
  sugar_beet: {
    investment: 95,
    water: 90,
    regeneration: 10,
    logistics: 95,
    cleanup: 95,
  },
};

export function normalisePriorities(
  input: FarmingPriorities,
): FarmingPriorities {
  return Object.fromEntries(
    PRIORITY_CONTROLS.map(({ key }) => [
      key,
      Number.isFinite(input[key])
        ? Math.round(Math.min(100, Math.max(0, input[key])))
        : 50,
    ]),
  ) as FarmingPriorities;
}

export function rankDemoCrops(
  input: FarmingPriorities,
  scenario: ClimateScenario,
  previousCrop = "",
) {
  const priorities = normalisePriorities(input);
  const changed = PRIORITY_CONTROLS.filter(
    ({ key }) => priorities[key] !== 50,
  ).length;
  const ranked = visualScenario(scenario)
    .crops.map((crop) => {
      const profile = PROFILES[crop.id];
      const reasons: string[] = [];
      const matches: string[] = [];
      if (previousCrop === crop.id)
        reasons.push("Repeats the last entered crop (demo rotation check).");
      if (
        priorities.investment < 50 &&
        profile.investment > 40 + priorities.investment * 1.2
      )
        reasons.push("Above your investment allowance.");
      if (priorities.water < 50 && profile.water > 40 + priorities.water * 1.2)
        reasons.push("Needs more water than your selected reserve.");
      if (
        priorities.logistics < 50 &&
        profile.logistics > 30 + priorities.logistics * 1.4
      )
        reasons.push("Needs more field operations than your time allowance.");
      if (
        priorities.cleanup > 50 &&
        profile.cleanup < (priorities.cleanup - 50) * 1.6
      )
        reasons.push("Does not meet your field cleanup requirement.");

      // At 50 all extra weights are zero: retain the existing demo baseline exactly.
      let total = crop.score * 2;
      let weight = 2;
      for (const { key } of PRIORITY_CONTROLS) {
        const offset = (priorities[key] - 50) / 50;
        // Normal cleanup pressure imposes no preference for a treatment programme.
        if (offset === 0 || (key === "cleanup" && offset < 0)) continue;
        const importance = Math.abs(offset) * 1.4;
        const affinity = offset > 0 ? profile[key] : 100 - profile[key];
        total += affinity * importance;
        weight += importance;
      }
      if (priorities.investment < 50 && profile.investment <= 40)
        matches.push("Low-input demo profile");
      if (priorities.investment > 50 && profile.investment >= 65)
        matches.push("Intensive-production demo profile");
      if (priorities.water < 50 && profile.water <= 40)
        matches.push("Lower-water demo profile");
      if (priorities.water > 50 && profile.water >= 65)
        matches.push("Matches higher water availability");
      if (priorities.regeneration > 50 && profile.regeneration >= 80)
        matches.push("Soil-regeneration demo profile");
      if (priorities.regeneration < 50 && profile.regeneration <= 30)
        matches.push("Immediate-return demo profile");
      if (priorities.logistics < 50 && profile.logistics <= 30)
        matches.push("Fewer sample field operations");
      if (priorities.logistics > 50 && profile.logistics >= 65)
        matches.push("Fits a higher-intervention setup");
      if (priorities.cleanup > 50 && profile.cleanup >= 80)
        matches.push("Meets the demo cleanup requirement");
      return {
        ...crop,
        score: Math.round(total / weight),
        eligible: reasons.length === 0,
        reasons,
        matches,
      };
    })
    .sort((a, b) => b.score - a.score);
  return {
    priorities,
    changed,
    ranked,
    eligible: ranked.filter((crop) => crop.eligible),
    excluded: ranked.filter((crop) => !crop.eligible),
  };
}

export type DemoCropRanking = ReturnType<typeof rankDemoCrops>;
