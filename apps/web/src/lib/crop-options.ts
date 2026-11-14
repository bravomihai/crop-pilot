import type { HistorySource } from "@fieldshift/contracts";

export const RULE_CROPS = [
  ["winter_wheat", "Winter wheat"],
  ["winter_barley", "Winter barley"],
  ["winter_rapeseed", "Winter rapeseed"],
  ["maize", "Maize"],
  ["sunflower", "Sunflower"],
  ["soybean", "Soybean"],
  ["pea", "Pea"],
  ["oats", "Oats"],
  ["sorghum", "Grain sorghum"],
  ["dry_beans", "Dry beans"],
  ["sugar_beet", "Sugar beet"],
  ["spring_barley", "Spring barley"],
  ["triticale", "Triticale"],
  ["winter_rye", "Winter rye"],
  ["potato", "Potato"],
] as const;

export const HISTORY_SOURCES = [
  ["typed", "Typed from memory"],
  ["apia", "APIA application"],
  ["spray_records", "Spray records"],
  ["unknown", "Unknown"],
] as const satisfies readonly (readonly [HistorySource, string])[];
