// In-memory store so everything works from day one.
// TODO(P5): replace with DynamoDB (see infra/README.md). Keep the same function signatures.
import { randomUUID } from "node:crypto";
import type { AnalysisRecord, FarmRequest } from "./types";

interface Db {
  farms: Map<string, FarmRequest>;
  analyses: Map<string, AnalysisRecord>;
  latestByFarm: Map<string, string>;
}

// globalThis keeps the data across hot reloads and route modules in dev.
const g = globalThis as unknown as { __fieldshiftDb?: Db };
const db: Db = (g.__fieldshiftDb ??= { farms: new Map(), analyses: new Map(), latestByFarm: new Map() });

export const newId = (prefix: string) => `${prefix}_${randomUUID().replace(/-/g, "").slice(0, 12)}`;

export async function saveFarm(farm: FarmRequest): Promise<string> {
  const farm_id = farm.farm_id ?? newId("farm");
  db.farms.set(farm_id, { ...farm, farm_id });
  return farm_id;
}

export async function getFarm(farmId: string): Promise<FarmRequest | undefined> {
  return db.farms.get(farmId);
}

export async function findFarmByPhone(phone: string): Promise<FarmRequest | undefined> {
  for (const farm of db.farms.values()) if (farm.contact?.phone_e164 === phone) return farm;
  return undefined;
}

export async function saveAnalysis(rec: AnalysisRecord): Promise<void> {
  db.analyses.set(rec.analysis_id, rec);
  if (rec.status === "done") db.latestByFarm.set(rec.farm_id, rec.analysis_id);
}

export async function getAnalysis(analysisId: string): Promise<AnalysisRecord | undefined> {
  return db.analyses.get(analysisId);
}

export async function latestAnalysis(farmId: string): Promise<AnalysisRecord | undefined> {
  const id = db.latestByFarm.get(farmId);
  return id ? db.analyses.get(id) : undefined;
}
