"use client";
import { useId, useState } from "react";
import { linearTrend } from "@/lib/chart-data";
import { useChartWidth } from "./use-chart-width";

export default function ClimateTrendChart({
  points,
  title,
  unit,
}: {
  points: { year: number; value: number | null }[];
  title: string;
  unit: string;
}) {
  const id = useId();
  const { ref, width } = useChartWidth();
  const data = [...points].sort((a, b) => a.year - b.year);
  const [index, setIndex] = useState(0);
  const selected = Math.min(index, Math.max(0, data.length - 1));
  const trend = linearTrend(data);
  const known = data.flatMap((point) =>
    point.value == null ? [] : [point.value],
  );
  const trendEnds =
    trend && data.length
      ? [trend.at(data[0].year), trend.at(data.at(-1)!.year)]
      : [];
  const min = Math.min(0, ...known, ...trendEnds),
    max = Math.max(1, ...known, ...trendEnds);
  const left = 46,
    right = width - 18,
    top = 22,
    bottom = 192;
  const step = (right - left) / Math.max(1, data.length);
  const x = (position: number) => left + (position + 0.5) * step;
  const y = (value: number) =>
    bottom - ((value - min) / (max - min)) * (bottom - top);
  return (
    <section
      className="analysis-chart future-chart"
      aria-labelledby={`${id}-title`}
    >
      <h3 id={`${id}-title`}>{title}</h3>
      <p className="chart-legend">
        Labelled bars: supplied yearly values · dashed line: simple linear trend
        · hatching: Unknown.
      </p>
      {data.length ? (
        <>
          <div ref={ref}>
            <svg
              viewBox={`0 0 ${width} 228`}
              role="img"
              aria-label={`${title}, in ${unit}. Use the year selector or table for exact values.`}
              onPointerMove={(event) => {
                const bounds = event.currentTarget.getBoundingClientRect();
                const px =
                  ((event.clientX - bounds.left) / bounds.width) * width;
                setIndex(
                  Math.min(
                    data.length - 1,
                    Math.max(0, Math.floor((px - left) / step)),
                  ),
                );
              }}
            >
              <defs>
                <pattern
                  id={`${id}-unknown`}
                  width={6}
                  height={6}
                  patternUnits="userSpaceOnUse"
                >
                  <path
                    d="M-1,1l2,-2M0,6l6,-6M5,7l2,-2"
                    className="chart-hatch"
                  />
                </pattern>
              </defs>
              {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
                const value = min + (max - min) * fraction;
                return (
                  <g key={fraction}>
                    <line
                      className="chart-grid"
                      x1={left}
                      x2={right}
                      y1={y(value)}
                      y2={y(value)}
                    />
                    <text
                      className="chart-axis-text"
                      x={left - 7}
                      y={y(value) + 4}
                      textAnchor="end"
                    >
                      {Math.round(value)}
                    </text>
                  </g>
                );
              })}
              {data.map((point, position) => (
                <g key={point.year}>
                  {point.value == null ? (
                    <rect
                      x={x(position) - step * 0.3}
                      width={step * 0.6}
                      y={top}
                      height={bottom - top}
                      fill={`url(#${id}-unknown)`}
                    />
                  ) : (
                    <rect
                      className="climate-bar"
                      x={x(position) - step * 0.3}
                      width={step * 0.6}
                      y={Math.min(y(point.value), y(0))}
                      height={Math.abs(y(point.value) - y(0))}
                    />
                  )}
                  <text
                    className="chart-axis-text"
                    x={x(position)}
                    y={bottom + 22}
                    textAnchor="middle"
                  >
                    {data.length <= 7 ||
                    position % Math.ceil(data.length / 6) === 0
                      ? point.year
                      : ""}
                  </text>
                </g>
              ))}
              {trend && (
                <line
                  className="trend-line"
                  x1={x(0)}
                  y1={y(trend.at(data[0].year))}
                  x2={x(data.length - 1)}
                  y2={y(trend.at(data.at(-1)!.year))}
                />
              )}
              <line
                className="crosshair"
                x1={x(selected)}
                x2={x(selected)}
                y1={top}
                y2={bottom}
              />
            </svg>
          </div>
          <label className="chart-year-picker" htmlFor={`${id}-year`}>
            Inspect year: {data[selected].year}
            <input
              id={`${id}-year`}
              type="range"
              min={0}
              max={data.length - 1}
              value={selected}
              step={1}
              onChange={(event) => setIndex(Number(event.target.value))}
              aria-valuetext={String(data[selected].year)}
            />
          </label>
          <div className="chart-readout" role="status">
            <span>
              <strong>{data[selected].year}</strong>:{" "}
              {data[selected].value == null
                ? "Unknown"
                : `${data[selected].value} ${unit}`}
            </span>
            <span>
              {trend
                ? `Simple linear trend: ${trend.slope > 0 ? "+" : ""}${trend.slope.toFixed(2)} ${unit}/year`
                : "Insufficient known observations for a trend."}
            </span>
          </div>
          <details className="chart-data-table">
            <summary>Read yearly values as a table</summary>
            <table>
              <caption>{title}</caption>
              <thead>
                <tr>
                  <th scope="col">Year</th>
                  <th scope="col">Value ({unit})</th>
                </tr>
              </thead>
              <tbody>
                {data.map((point) => (
                  <tr key={point.year}>
                    <th scope="row">{point.year}</th>
                    <td>{point.value ?? "Unknown"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </>
      ) : (
        <p>No climate observations are available.</p>
      )}
    </section>
  );
}
