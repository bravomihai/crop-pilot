// Season strip: one row per rotation year, 12 months. Bare soil stands out.

const MONTHS = ["I", "F", "M", "A", "M", "I", "I", "A", "S", "O", "N", "D"];

// TODO(P1): colours and Romanian names from CropRules instead of this fixed map.
const COLORS: Record<string, string> = {
  maize: "#E3B23C",
  winter_wheat: "#C9A66B",
  soybean: "#7FB069",
  sunflower: "#F2C14E",
  sorghum: "#B5651D",
  winter_vetch: "#5B8E7D",
  bare: "#D9534F",
};

export default function SeasonStrip({ calendar }: { calendar: (string | null)[][] }) {
  return (
    <table className="strip" aria-label="Calendarul rotației">
      <thead>
        <tr><th />{MONTHS.map((m, i) => <th key={i}>{m}</th>)}</tr>
      </thead>
      <tbody>
        {calendar.map((row, y) => (
          <tr key={y}>
            <th>An {y + 1}</th>
            {row.map((crop, m) => (
              <td key={m} title={crop ?? "necunoscut"}
                style={{ background: crop ? COLORS[crop] ?? "#999" : "transparent" }} />
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
