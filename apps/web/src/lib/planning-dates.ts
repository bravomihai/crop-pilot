/** True between 6 November and the end of February, when autumn sowing windows have closed. */
export function afterAutumnSowing(isoDate: string): boolean {
  const match = /^\d{4}-(\d{2})-(\d{2})$/.exec(isoDate);
  if (!match) return false;
  const month = Number(match[1]);
  const day = Number(match[2]);
  return (month === 11 && day > 5) || month === 12 || month <= 2;
}

/** A map center from a page link (?lat=..&lon=..&name=..), limited to Romania's box. */
export function fieldFromQuery(
  search: string,
): { name: string; latitude: number; longitude: number } | null {
  const params = new URLSearchParams(search);
  const latitude = Number(params.get("lat"));
  const longitude = Number(params.get("lon"));
  if (!params.has("lat") || !params.has("lon")) return null;
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  if (latitude < 43.5 || latitude > 48.3 || longitude < 20.2 || longitude > 29.8) return null;
  const name = (params.get("name") ?? "").trim().slice(0, 80) || "Your field";
  return { name, latitude, longitude };
}
