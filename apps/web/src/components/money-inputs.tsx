"use client";
import { useState, type FormEvent } from "react";
import type { RecommendationRequest, RecommendationResult } from "@croppilot/contracts";
import { lei } from "@/lib/money";

type MoneyInputs = NonNullable<RecommendationRequest["money_inputs"]>;
type CropRow = { id: string; name: string; price?: number; cost?: number; missing: boolean };

/** Every crop in the shown plans, with the price and cost the estimate used (if any). */
export function moneyCrops(result: RecommendationResult): CropRow[] {
  const rows = new Map<string, CropRow>();
  for (const plan of [...result.plans, ...(result.baseline ? [result.baseline] : [])]) {
    for (const crop of plan.economics?.crops ?? []) {
      const row = rows.get(crop.crop_id) ?? { id: crop.crop_id, name: crop.crop_name, missing: false };
      row.price ??= crop.price_lei_per_t?.typical;
      row.cost ??= crop.costs?.typical;
      row.missing ||= !crop.price_lei_per_t || !crop.costs;
      rows.set(crop.crop_id, row);
    }
  }
  return [...rows.values()].sort((a, b) => Number(b.missing) - Number(a.missing));
}

const positive = (text: string) => {
  const value = Number(text.replace(",", "."));
  return Number.isFinite(value) && value > 0 && value <= 100000 ? value : undefined;
};

/** The farmer's own prices and costs, for crops without data or to replace the averages. */
export default function MoneyInputs({
  result,
  request,
  busy,
  onApply,
}: {
  result: RecommendationResult;
  request?: RecommendationRequest;
  busy: boolean;
  onApply?: (inputs: RecommendationRequest["money_inputs"]) => void;
}) {
  const crops = moneyCrops(result);
  const given = request?.money_inputs;
  const [prices, setPrices] = useState<Record<string, string>>(() =>
    Object.fromEntries(Object.entries(given?.prices_lei_per_t ?? {}).map(([k, v]) => [k, String(v)])),
  );
  const [costs, setCosts] = useState<Record<string, string>>(() =>
    Object.fromEntries(Object.entries(given?.costs_lei_per_ha ?? {}).map(([k, v]) => [k, String(v)])),
  );
  if (!onApply || !crops.length) return null;
  const missing = crops.filter((crop) => crop.missing);
  const others = crops.filter((crop) => !crop.missing);

  function submit(event: FormEvent) {
    event.preventDefault();
    const pick = (values: Record<string, string>) =>
      Object.fromEntries(
        Object.entries(values).flatMap(([id, text]) => {
          const value = positive(text);
          return value === undefined ? [] : [[id, value]];
        }),
      );
    const inputs: MoneyInputs = { prices_lei_per_t: pick(prices), costs_lei_per_ha: pick(costs) };
    const empty = !Object.keys(inputs.prices_lei_per_t!).length && !Object.keys(inputs.costs_lei_per_ha!).length;
    onApply!(empty ? undefined : inputs);
  }

  const row = (crop: CropRow) => (
    <div className="money-input-row" key={crop.id}>
      <span className="money-input-crop">{crop.name}</span>
      <label>
        <span>Price you get (lei/t)</span>
        <input
          inputMode="decimal"
          value={prices[crop.id] ?? ""}
          placeholder={crop.price ? String(Math.round(crop.price)) : "unknown"}
          onChange={(event) => setPrices({ ...prices, [crop.id]: event.target.value })}
        />
      </label>
      <label>
        <span>Your cost (lei/ha)</span>
        <input
          inputMode="decimal"
          value={costs[crop.id] ?? ""}
          placeholder={crop.cost ? String(Math.round(crop.cost)) : "unknown"}
          onChange={(event) => setCosts({ ...costs, [crop.id]: event.target.value })}
        />
      </label>
    </div>
  );

  return (
    <form className="money-inputs" id="money-inputs" tabIndex={-1} onSubmit={submit} aria-labelledby="money-inputs-title">
      <h3 id="money-inputs-title">Your prices and costs</h3>
      {missing.length > 0 ? (
        <p>
          There are no official recent figures for {missing.map((crop) => crop.name.toLowerCase()).join(" and ")}, so
          plans with {missing.length > 1 ? "these crops" : "it"} show the money as unknown. Add what you get and spend
          to complete them. Your values are used for this calculation only and are not stored.
        </p>
      ) : (
        <p>The estimate uses county and regional averages. Use your own figures where you know them; they are not stored.</p>
      )}
      {missing.map(row)}
      {others.length > 0 && (
        <details open={missing.length === 0 || undefined}>
          <summary>Use your own figures for the other crops</summary>
          <p className="money-input-hint">
            Grey values are what the estimate uses now: {others.map((c) => `${c.name.toLowerCase()} ${c.price ? lei(c.price) + "/t" : ""}`).join(", ")}.
          </p>
          {others.map(row)}
        </details>
      )}
      <div className="money-input-actions">
        <button type="submit" className="button" disabled={busy}>
          {busy ? "Recalculating…" : "Recalculate the money"}
        </button>
        {given && (
          <button
            type="button"
            className="text-button"
            disabled={busy}
            onClick={() => {
              setPrices({});
              setCosts({});
              onApply(undefined);
            }}
          >
            Use the averages again
          </button>
        )}
      </div>
    </form>
  );
}
