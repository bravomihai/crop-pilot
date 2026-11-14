import Link from "next/link";
import ReplayChart from "@/components/charts/replay-chart";
import ClimateTrendChart from "@/components/charts/climate-trend-chart";
import ThemeControl from "@/components/theme-control";

const years = [2020, 2021, 2022, 2023, 2024, 2025];
const series = [
  { id: "plan-a", label: "Example plan A", values: [70, 64, 79, 68, 74, 82] },
  { id: "plan-b", label: "Example plan B", values: [65, 70, null, 76, 78, 81] },
  {
    id: "baseline",
    label: "Example current rotation",
    baseline: true,
    values: [59, 61, 55, 62, 57, 65],
  },
].map(({ values, ...entry }) => ({
  ...entry,
  points: years.map((year, index) => ({ year, value: values[index] })),
}));

export default function ChartPreviewsPage() {
  return (
    <main className="chart-preview-page">
      <header className="analysis-page-header">
        <Link href="/calculator?fixture=full">← Rotation calculator</Link>
        <ThemeControl />
      </header>
      <h1>Future chart previews</h1>
      <p className="notice notice--warning">
        <strong>DEMO · hard-coded sample values.</strong> These components are
        not connected to results. Replay is waiting for <code>plan.replay</code>
        ; climate trends are waiting for <code>result.climate_context</code>. No
        observations were fetched for these charts.
      </p>
      <ReplayChart series={series} title="Example water-score replay" />
      <ClimateTrendChart
        title="Example yearly rainfall"
        unit="mm"
        points={years.map((year, index) => ({
          year,
          value: [520, 470, null, 560, 490, 610][index],
        }))}
      />
    </main>
  );
}
