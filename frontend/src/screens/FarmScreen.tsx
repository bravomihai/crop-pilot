import type { FarmRequest } from "../types";

type Props = { farm: FarmRequest; onChange: (farm: FarmRequest) => void; onNext: () => void };

// TODO(P1): map with polygon drawing (e.g. react-leaflet + leaflet-draw, or MapLibre).
// Write the drawn polygon to farm.field.boundary (GeoJSON, [lon, lat]) and compute area_ha.
export default function FarmScreen({ farm, onChange, onNext }: Props) {
  const ring = farm.field.boundary.coordinates[0];
  return (
    <section>
      <h2>Selectați parcela</h2>
      <div className="placeholder">Harta (de făcut): desenați conturul parcelei</div>
      <label>
        Nume parcelă
        <input
          value={farm.field.name ?? ""}
          onChange={(e) => onChange({ ...farm, field: { ...farm.field, name: e.target.value } })}
        />
      </label>
      <p className="muted">
        Contur: {ring.length - 1} puncte · {farm.field.area_ha ?? "?"} ha
      </p>
      <button onClick={onNext}>Continuă</button>
    </section>
  );
}
