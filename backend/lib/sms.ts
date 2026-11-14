// SMS / WhatsApp commands (contracts/api.md, "SMS / WhatsApp flow").
// Provider-agnostic: the webhook route turns the provider payload into an InboundMessage first.
import { runAnalysis } from "./analyses";
import { findFarmByPhone, latestAnalysis } from "./store";
import type { AnalysisResult, FarmRequest } from "./types";

export interface InboundMessage {
  from: string; // E.164, e.g. +40700000000
  text: string;
  channel: "sms" | "whatsapp";
}

const HELP =
  "FieldShift comenzi: REZULTAT, ANALIZA, APA, SOL, VENIT, SECETA, AJUTOR";

const PRIORITY_COMMANDS: Record<string, string> = { APA: "water", SOL: "soil", VENIT: "income" };

export const stripDiacritics = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "");

export async function handleMessage(msg: InboundMessage): Promise<string> {
  const command = stripDiacritics(msg.text).trim().split(/\s+/)[0]?.toUpperCase() ?? "";
  const farm = await findFarmByPhone(msg.from);
  if (!farm?.farm_id) {
    return "FieldShift: numarul nu e legat de o ferma. Inregistrati parcela in aplicatie cu acest numar.";
  }

  if (command === "REZULTAT") {
    const latest = await latestAnalysis(farm.farm_id);
    return latest?.result ? summary(latest.result, msg.channel) : "FieldShift: nicio analiza inca. Trimiteti ANALIZA.";
  }
  if (command === "ANALIZA") return rerun(farm, {}, msg.channel);
  if (command in PRIORITY_COMMANDS) return rerun(farm, { priorities: boosted(farm.priorities, PRIORITY_COMMANDS[command]) }, msg.channel);
  if (command === "SECETA") return rerun(farm, { scenario: { ...farm.scenario, rain_change_pct: -20 } }, msg.channel);
  return HELP;
}

async function rerun(farm: FarmRequest, overrides: Parameters<typeof runAnalysis>[1], channel: InboundMessage["channel"]) {
  // Runs inline. TODO(P5): if the provider times out (Twilio waits ~15 s), reply "Analizam..."
  // immediately and send the summary later through the provider's send-message API.
  const rec = await runAnalysis(farm.farm_id!, overrides);
  if (!rec?.result) return "FieldShift: analiza a esuat. Incercati din nou mai tarziu.";
  return summary(rec.result, channel);
}

/** Make `criterion` the highest priority, keeping the others. */
function boosted(priorities: Record<string, number>, criterion: string): Record<string, number> {
  const max = Math.max(0, ...Object.values(priorities));
  return { ...priorities, [criterion]: max + 2 };
}

/** ~2 SMS segments without diacritics; WhatsApp keeps diacritics. */
export function summary(result: AnalysisResult, channel: InboundMessage["channel"]): string {
  const ranked = [...result.strategies].sort((a, b) => a.rank - b.rank);
  const lines = ranked.map((s) => {
    const tag = s.kind === "existing" ? " (actuala)" : "";
    return `${s.rank}) ${s.label.replace(/^Rotația actuală:\s*/, "")}${tag} ${Math.round(s.total_score * 100)}/100`;
  });
  const link = `${process.env.PUBLIC_APP_URL ?? ""}/r/${result.analysis_id}`;
  const text = `FieldShift:\n${lines.join("\n")}\nDetalii: ${link}`;
  return channel === "sms" ? stripDiacritics(text) : text;
}
