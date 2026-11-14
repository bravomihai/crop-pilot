// Loose types for what the backend stores and forwards. The contracts in
// /contracts/schemas are the source of truth; the engine validates bodies.

export type Json = Record<string, unknown>;

export interface FarmRequest extends Json {
  farm_id?: string;
  contact?: { phone_e164?: string; channel?: "sms" | "whatsapp" };
  current_rotation: string[];
  priorities: Record<string, number>;
  scenario: { climate: string; horizon?: number; rain_change_pct?: number; temp_change_c?: number };
}

export interface Strategy extends Json {
  id: string;
  kind: "existing" | "alternative";
  label: string;
  total_score: number;
  rank: number;
}

export interface AnalysisResult extends Json {
  analysis_id: string;
  farm_id: string;
  strategies: Strategy[];
}

export interface AnalysisRecord {
  analysis_id: string;
  farm_id: string;
  status: "running" | "done" | "failed";
  result?: AnalysisResult;
  error?: string;
}
