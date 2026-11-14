import { visualScenario, type ClimateScenario } from "@/lib/dashboard-scenario";
import Icon, { type IconName } from "./icon";

export default function KpiCards({ scenario }: { scenario: ClimateScenario }) {
  const values = visualScenario(scenario);
  const cards: {
    title: string;
    source: string;
    value: string;
    unit: string;
    badge: string;
    caption: string;
    icon: IconName;
  }[] = [
    {
      title: "Water saving",
      source: "SMAP / POWER",
      value: String(values.waterSaving),
      unit: "%",
      badge: "Illustrative",
      caption: "Potential irrigation saving · sample only",
      icon: "drop",
    },
    {
      title: "Soil moisture",
      source: "SMAP / POWER",
      value: String(values.moisture),
      unit: "%",
      badge: "Sample",
      caption: "Illustrative moisture indicator",
      icon: "drop",
    },
    {
      title: "Mean temperature",
      source: "NASA POWER",
      value: values.temperature,
      unit: "°C",
      badge: "Scenario",
      caption: "Example baseline 25.3°C + your offset",
      icon: "temperature",
    },
    {
      title: "Vegetation index",
      source: "MODIS 250 m",
      value: values.ndvi,
      unit: "",
      badge: "Sample",
      caption: "NDVI example · no field observation",
      icon: "leaf",
    },
  ];
  return (
    <section className="kpi-section" aria-labelledby="metrics-title">
      <div className="kpi-section-heading">
        <h2 id="metrics-title">Field indicators</h2>
        <span>Illustrative values · not NASA measurements</span>
      </div>
      <div className="kpi-grid">
        {cards.map((card) => (
          <article className="dashboard-card kpi-card" key={card.title}>
            <div className="kpi-heading">
              <span>{card.title}</span>
              <Icon name={card.icon} size={17} />
            </div>
            <span className="source-pill">
              <i />
              {card.source} · SAMPLE
            </span>
            <div className="kpi-value">
              {card.value}
              <span>{card.unit}</span>
            </div>
            <span className="metric-badge">{card.badge}</span>
            <p>{card.caption}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
