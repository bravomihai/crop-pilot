import type { PlanEconomics } from "@croppilot/contracts";
import { lei, leiRange } from "@/lib/money";

const ROWS = [
  ["income", "Income from selling the crops"],
  ["costs", "Costs of growing them"],
  ["subsidies", "Subsidies (APIA)"],
  ["margin", "What is left"],
] as const;

/** Rough money estimate per hectare and year for one plan. Not a forecast. */
export default function PlanMoney({ economics }: { economics?: PlanEconomics }) {
  if (!economics) return null;
  const { per_year: year } = economics;
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
                      <span className="plan-money-range">{leiRange(range)}</span>
                    </>
                  ) : (
                    <span className="plan-money-unknown">Unknown</span>
                  )}
                </td>
              </tr>
            );
          })}
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
      <details className="plan-money-details">
        <summary>How the money is estimated</summary>
        <p>
          Typical value in bold, with a low–high range. {economics.county ? `${economics.county} county` : "County"}{" "}
          yields of the last 10 years, regional farm-gate prices of the last 3 years and published cost budgets,
          spread over the {economics.covered_years.toLocaleString("en-GB")} years this plan covers. Not a forecast;
          it does not change the ranking.
        </p>
        <h5>By crop (one season each)</h5>
        <ul>
          {economics.crops.map((crop, index) => (
            <li key={index}>
              <strong>{crop.crop_name}:</strong>{" "}
              {crop.yield_t_per_ha
                ? `${crop.yield_t_per_ha.typical.toLocaleString("en-GB")} t/ha`
                : "yield unknown"}
              {" × "}
              {crop.price_lei_per_t ? `${lei(crop.price_lei_per_t.typical)}/t` : "price unknown"}
              {" = "}
              {crop.income ? lei(crop.income.typical) : "income unknown"}; costs{" "}
              {crop.costs ? lei(crop.costs.typical) : "unknown"}
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
