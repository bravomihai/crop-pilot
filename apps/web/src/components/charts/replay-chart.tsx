"use client";
import { useId, useState } from "react";
import { useChartWidth } from "./use-chart-width";

/** Display-only props. No dependency on a proposed plan.replay contract field. */
export type ReplaySeries = {
  id: string;
  label: string;
  baseline?: boolean;
  points: { year: number; value: number | null }[];
};

export default function ReplayChart({
  series,
  title = "Historical replay preview",
}: {
  series: ReplaySeries[];
  title?: string;
}) {
  const id = useId();
  const { ref, width } = useChartWidth();
  const years = [
    ...new Set(
      series.flatMap((entry) => entry.points.map((point) => point.year)),
    ),
  ].sort((a, b) => a - b);
  const [index, setIndex] = useState(0);
  const selected = Math.min(index, Math.max(0, years.length - 1));
  const left = 38,
    right = width - 18,
    top = 18,
    bottom = 190;
  const x = (year: number) =>
    years.length < 2
      ? (left + right) / 2
      : left +
        ((year - years[0]) / (years.at(-1)! - years[0])) * (right - left);
  const y = (value: number) =>
    bottom - (Math.max(0, Math.min(100, value)) / 100) * (bottom - top);
  return (
    <section
      className="analysis-chart future-chart"
      aria-labelledby={`${id}-title`}
    >
      <h3 id={`${id}-title`}>{title}</h3>
      <p className="chart-legend">
        One labelled line per plan · dashed: current rotation · breaks in a
        line: Unknown. Display scale: 0–100.
      </p>
      {years.length ? (
        <>
          <div ref={ref}>
            <svg
              viewBox={`0 0 ${width} 224`}
              role="img"
              aria-label={`${title}. ${series.map((entry) => entry.label).join(", ")}. Use the year selector or table for exact values.`}
              onPointerMove={(event) => {
                const bounds = event.currentTarget.getBoundingClientRect();
                const px =
                  ((event.clientX - bounds.left) / bounds.width) * width;
                setIndex(
                  years.reduce(
                    (best, year, current) =>
                      Math.abs(x(year) - px) < Math.abs(x(years[best]) - px)
                        ? current
                        : best,
                    0,
                  ),
                );
              }}
            >
              {[0, 25, 50, 75, 100].map((value) => (
                <g key={value}>
                  <line
                    className="chart-grid"
                    x1={left}
                    x2={right}
                    y1={y(value)}
                    y2={y(value)}
                  />
                  <text
                    className="chart-axis-text"
                    x={left - 8}
                    y={y(value) + 4}
                    textAnchor="end"
                  >
                    {value}
                  </text>
                </g>
              ))}
              {years.map((year, current) =>
                current % Math.max(1, Math.ceil(years.length / 6)) === 0 ||
                current === years.length - 1 ? (
                  <text
                    className="chart-axis-text"
                    x={x(year)}
                    y={bottom + 23}
                    textAnchor="middle"
                    key={year}
                  >
                    {year}
                  </text>
                ) : null,
              )}
              {series.map((entry, position) => {
                let drawing = false;
                const path = years
                  .map((year) => {
                    const value = entry.points.find(
                      (point) => point.year === year,
                    )?.value;
                    if (value == null) {
                      drawing = false;
                      return "";
                    }
                    const segment = `${drawing ? "L" : "M"}${x(year)},${y(value)}`;
                    drawing = true;
                    return segment;
                  })
                  .join(" ");
                return (
                  <g
                    className={`chart-tone-${position} ${entry.baseline ? "replay-baseline" : ""}`}
                    key={entry.id}
                  >
                    <path
                      className="replay-line"
                      d={path}
                      fill="none"
                      strokeWidth={2.5}
                      strokeDasharray={entry.baseline ? "7 5" : undefined}
                    />
                    {entry.points
                      .filter((point) => point.value != null)
                      .map((point) => (
                        <circle
                          className="replay-point"
                          key={point.year}
                          cx={x(point.year)}
                          cy={y(point.value!)}
                          r={3}
                        />
                      ))}
                  </g>
                );
              })}
              <line
                className="crosshair"
                x1={x(years[selected])}
                x2={x(years[selected])}
                y1={top}
                y2={bottom}
              />
            </svg>
          </div>
          <label className="chart-year-picker" htmlFor={`${id}-year`}>
            Inspect year: {years[selected]}
            <input
              id={`${id}-year`}
              type="range"
              min={0}
              max={years.length - 1}
              step={1}
              value={selected}
              onChange={(event) => setIndex(Number(event.target.value))}
              aria-valuetext={String(years[selected])}
            />
          </label>
          <div className="chart-readout" role="status" aria-atomic="true">
            <strong>{years[selected]}</strong>
            {series.map((entry, position) => {
              const value = entry.points.find(
                (point) => point.year === years[selected],
              )?.value;
              return (
                <span key={entry.id} className={`chart-tone-${position}`}>
                  <i
                    className={entry.baseline ? "legend-dash" : "legend-line"}
                  />
                  {entry.label}
                  {entry.baseline ? " (current rotation)" : ""}:{" "}
                  <b>
                    {value == null ? "Unknown" : `${Math.round(value)} / 100`}
                  </b>
                </span>
              );
            })}
          </div>
          <details className="chart-data-table">
            <summary>Read replay values as a table</summary>
            <div className="table-scroll">
              <table>
                <caption>{title} — exact supplied values</caption>
                <thead>
                  <tr>
                    <th scope="col">Year</th>
                    {series.map((entry) => (
                      <th key={entry.id} scope="col">
                        {entry.label}
                        {entry.baseline ? " (baseline)" : ""}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {years.map((year) => (
                    <tr key={year}>
                      <th scope="row">{year}</th>
                      {series.map((entry) => (
                        <td key={entry.id}>
                          {entry.points.find((point) => point.year === year)
                            ?.value ?? "Unknown"}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      ) : (
        <p>No replay observations are available.</p>
      )}
    </section>
  );
}
