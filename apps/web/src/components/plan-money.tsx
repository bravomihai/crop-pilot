"use client";
import type { PlanEconomics } from "@croppilot/contracts";
import { jumpTo } from "@/lib/jump";
import { lei, leiRange, signedLei } from "@/lib/money";

const ROWS = [
  ["income", "Income from selling the crops"],
  ["costs", "Costs of growing them"],
  ["subsidies", "Subsidies (APIA)"],
  ["margin", "What is left"],
] as const;

const RATING = { good: "a good previous crop", ok: "an acceptable previous crop", poor: "a poor previous crop", forbidden: "a previous crop to avoid" };
const BASIS = {
  commercial_farms: "commercial farms in the county",
  all_farms: "all farms in the county",
  national: "national average",
};

/** Rough money estimate per hectare and year for one plan. Not a forecast. */
export default function PlanMoney({ economics }: { economics?: PlanEconomics }) {
  if (!economics) return null;
  const { per_year: year } = economics;
  const order = year.crop_order_effect;
  return (
    <section className="plan-money" aria-label="Money per hectare and year, estimate">
      <h4>
        Money per hectare a year <span className="plan-money-tag">estimate</span>
      </h4>
      <table>
        <tbody>
          {ROWS.map(([key, label]) => {
            const range = year[key];
            return (
              <tr key={key} className={key === "margin" ? "plan-money-margin" : undefined}>
                <th scope="row">{label}</th>
                <td>
                  {range ? (
                    <>
                      <strong>{lei(range.typical)}</strong>
                      {range.low !== range.high && <span className="plan-money-range">{leiRange(range)}</span>}
                    </>
                  ) : (
                    <span className="plan-money-unknown">Unknown</span>
                  )}
                </td>
              </tr>
            );
          })}
          {year.margin && order != null && order !== 0 && (
            <tr className="plan-money-order">
              <th scope="row">of which from crop order</th>
              <td>
                <strong>{signedLei(order)}</strong>
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {economics.warnings.map((text, index) => (
        <p key={index} className="plan-money-warning">
          {text}
        </p>
      ))}
      {economics.notes.length > 0 && (
        <ul className="plan-money-notes">
          {economics.notes.map((text, index) => (
            <li key={index}>{text}</li>
          ))}
        </ul>
      )}
      {!year.margin && (
        <a className="plan-money-add" href="#money-inputs" onClick={(event) => jumpTo(event, "money-inputs")}>
          Add your prices to complete this
        </a>
      )}
      <details className="plan-money-details">
        <summary>How the money is estimated</summary>
        <p>
          Typical value in bold; the range shows a bad and a good year (20th and 80th percentile of the last 10
          years). {economics.county ? `${economics.county} county` : "County"} yields, the region&apos;s median
          farm-gate price of the last 3 years and published cost budgets indexed to official input prices, spread
          over the {economics.covered_years.toLocaleString("en-GB")} years this plan covers. Not a forecast; it does
          not change the ranking.
        </p>
        <h5>By crop (one season each)</h5>
        <ul>
          {economics.crops.map((crop, index) => (
            <li key={index}>
              <strong>{crop.crop_name}</strong>
              {crop.previous_crop && crop.previous_rating && (
                <> after {crop.previous_crop.toLowerCase()} ({RATING[crop.previous_rating]})</>
              )}
              :{" "}
              {crop.yield_t_per_ha ? `${crop.yield_t_per_ha.typical.toLocaleString("en-GB")} t/ha` : "yield unknown"}
              {crop.yield_basis && ` (${BASIS[crop.yield_basis]})`}
              {" × "}
              {crop.price_lei_per_t ? `${lei(crop.price_lei_per_t.typical)}/t` : "price unknown"}
              {crop.price_basis === "farmer" && " (your price)"}
              {" = "}
              {crop.income ? lei(crop.income.typical) : "income unknown"}; costs{" "}
              {crop.costs ? lei(crop.costs.typical) : "unknown"}
              {crop.cost_basis === "farmer" && " (your cost)"}
              {crop.cost_basis === "proxy" && " (stand-in budget of a similar crop)"}
              {crop.nitrogen_saving && <>, including {lei(crop.nitrogen_saving.typical)} less nitrogen fertiliser thanks to the legume before it</>}
              {crop.crop_order_effect != null && crop.crop_order_effect !== 0 && (
                <>; crop order {signedLei(crop.crop_order_effect)}</>
              )}
              {crop.price_lei_per_t && crop.price_basis !== "farmer" && crop.price_lei_per_t.low !== crop.price_lei_per_t.high && (
                <span className="plan-money-price-note">
                  {" "}
                  (prices in the last 3 years: {leiRange(crop.price_lei_per_t)}/t)
                </span>
              )}
            </li>
          ))}
        </ul>
        <h5>Subsidies and their conditions</h5>
        <ul>
          {economics.payments.map((payment) => (
            <li key={payment.id}>
              <strong>
                {payment.label} ({payment.id})
                {payment.lei_per_ha_year !== null && `: ${lei(payment.lei_per_ha_year)}/ha a year`}
              </strong>
              {payment.included === "if_eligible" && " · counted only in the high estimate"}
              {payment.included === "not_included" && " · not counted"}. {payment.condition}
            </li>
          ))}
        </ul>
      </details>
    </section>
  );
}
