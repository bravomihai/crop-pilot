// TypeScript views of the contracts. Source of truth: /contracts/schemas/*.schema.json.
// If a schema changes, update the matching type here.

export type Criterion =
  | "suitability" | "yield" | "water" | "soil" | "erosion"
  | "pest_break" | "succession" | "forage" | "income";

export type Scenario = {
  climate: "historical" | "ssp245" | "ssp585";
  horizon?: 2030 | 2050;
  rain_change_pct?: number;
  temp_change_c?: number;
};

export type FarmRequest = {
  farm_id?: string;
  language?: "ro" | "en";
  contact?: { phone_e164?: string; channel?: "sms" | "whatsapp" };
  field: {
    name?: string;
    boundary: { type: "Polygon"; coordinates: number[][][] };
    area_ha?: number;
    irrigated: boolean;
  };
  history: {
    source: "apia" | "spray_records" | "typed" | "satellite" | "none";
    confirmed_by_farmer?: boolean;
    seasons: { year: number; crop: string; yield_t_ha?: number; cover_crop_after?: string }[];
  };
  current_rotation: string[];
  priorities: Partial<Record<Criterion, number>>;
  constraints?: {
    excluded_crops?: string[];
    market_crops?: string[];
    equipment?: string[];
    max_irrigation_mm?: number;
    allow_cover_crops?: boolean;
  };
  rotation_years?: number;
  scenario: Scenario;
};

export type Strategy = {
  id: string;
  kind: "existing" | "alternative";
  label: string;
  sequence: string[];
  cover_crops?: { after_year_index: number; crop: string }[];
  total_score: number;
  rank: number;
  scores: Partial<Record<Criterion, number | null>>;
  violations?: string[];
  calendar?: (string | null)[][];
  why: string;
  evidence: { claim: string; source: string; criterion?: Criterion; weather_years?: number[] }[];
  benefits: string[];
  risks: string[];
  local_checks: string[];
  confidence: {
    level: "high" | "medium" | "low";
    signals: { history: number; rotation_evidence: number; satellite_coverage: number; climate_sensitivity: number };
  };
};

export type AnalysisResult = {
  analysis_id: string;
  farm_id: string;
  created_at: string;
  language?: "ro" | "en";
  scenario: Scenario;
  weights_used: Partial<Record<Criterion, number>>;
  strategies: Strategy[];
  data_gaps: string[];
  sources?: { id: string; title: string; url?: string }[];
  disclaimer: string;
};

export type Analysis = {
  analysis_id: string;
  farm_id: string;
  status: "running" | "done" | "failed";
  result?: AnalysisResult;
  error?: string;
};
