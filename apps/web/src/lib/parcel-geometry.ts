import { area } from "@turf/area";
import { centerOfMass } from "@turf/center-of-mass";
import { lineString, polygon } from "@turf/helpers";
import { kinks } from "@turf/kinks";
import { simplify } from "@turf/simplify";
import { locationSchema, type Location } from "@fieldshift/contracts";

/** GeoJSON order: longitude first. Convert explicitly at the Leaflet boundary. */
export type Coordinate = [longitude: number, latitude: number];
export type DrawSegment = { kind: "corner" | "freehand"; points: Coordinate[] };
export type FieldSelection = {
  location: Location;
  boundary: Coordinate[] | null;
  areaHectares: number | null;
};

export const MAX_BOUNDARY_POINTS = 100;

const equal = (a: Coordinate, b: Coordinate) => a[0] === b[0] && a[1] === b[1];

function containsPoint(point: Coordinate, ring: Coordinate[]): boolean {
  const [longitude, latitude] = point;
  let inside = false;
  for (
    let index = 0, previous = ring.length - 1;
    index < ring.length;
    previous = index, index += 1
  ) {
    const [x1, y1] = ring[index];
    const [x2, y2] = ring[previous];
    const cross = (longitude - x1) * (y2 - y1) - (latitude - y1) * (x2 - x1);
    if (
      Math.abs(cross) < 1e-10 &&
      longitude >= Math.min(x1, x2) &&
      longitude <= Math.max(x1, x2) &&
      latitude >= Math.min(y1, y2) &&
      latitude <= Math.max(y1, y2)
    )
      return true;
    if ((y1 > latitude) !== (y2 > latitude)) {
      const crossingLongitude =
        x1 + ((latitude - y1) * (x2 - x1)) / (y2 - y1);
      if (longitude < crossingLongitude) inside = !inside;
    }
  }
  return inside;
}

function representativePoint(points: Coordinate[]): Coordinate {
  const candidate = centerOfMass(polygon([[...points, points[0]]])).geometry
    .coordinates as Coordinate;
  if (containsPoint(candidate, points)) return candidate;

  // A concave parcel's center of mass can fall outside its boundary.
  const signedArea = points.reduce((sum, point, index) => {
    const next = points[(index + 1) % points.length];
    return sum + point[0] * next[1] - next[0] * point[1];
  }, 0);
  const span = Math.max(
    Math.max(...points.map(([longitude]) => longitude)) -
      Math.min(...points.map(([longitude]) => longitude)),
    Math.max(...points.map(([, latitude]) => latitude)) -
      Math.min(...points.map(([, latitude]) => latitude)),
  );
  const offsets = [
    Math.max(span * 1e-6, 1e-9),
    Math.max(span * 1e-7, 1e-10),
    Math.max(span * 1e-8, 1e-11),
  ];
  for (let index = 0; index < points.length; index += 1) {
    const first = points[index];
    const second = points[(index + 1) % points.length];
    const dx = second[0] - first[0];
    const dy = second[1] - first[1];
    const length = Math.hypot(dx, dy);
    if (length === 0) continue;
    const inward = signedArea > 0 ? [-dy, dx] : [dy, -dx];
    for (const offset of offsets) {
      const inside: Coordinate = [
        (first[0] + second[0]) / 2 + (inward[0] / length) * offset,
        (first[1] + second[1]) / 2 + (inward[1] / length) * offset,
      ];
      if (containsPoint(inside, points)) return inside;
    }
  }
  throw new Error("Could not find a representative point inside the field.");
}

export function tracePoints(segments: DrawSegment[]): Coordinate[] {
  return segments
    .flatMap((segment) => segment.points)
    .filter(
      (point, index, all) => index === 0 || !equal(point, all[index - 1]),
    );
}

export function addCorner(
  segments: DrawSegment[],
  point: Coordinate,
): DrawSegment[] {
  const previous = tracePoints(segments).at(-1);
  if (previous && equal(previous, point)) return segments;
  return [...segments, { kind: "corner", points: [point] }];
}

/** Simplify only this stroke. Existing corners and both curve anchors survive. */
export function addFreehand(
  segments: DrawSegment[],
  points: Coordinate[],
  tolerance: number,
): DrawSegment[] {
  const unique = points.filter(
    (point, index) => index === 0 || !equal(point, points[index - 1]),
  );
  if (unique.length < 2)
    return unique.length ? addCorner(segments, unique[0]) : segments;
  const curve = simplify(lineString(unique), { tolerance, highQuality: true });
  return [
    ...segments,
    { kind: "freehand", points: curve.geometry.coordinates as Coordinate[] },
  ];
}

export function createParcel(
  points: Coordinate[],
  name = "Field-1",
): FieldSelection {
  const vertices = points.filter(
    (point, index) => index === 0 || !equal(point, points[index - 1]),
  );
  if (vertices.length > 1 && equal(vertices[0], vertices[vertices.length - 1]))
    vertices.pop();
  if (vertices.length < 3)
    throw new Error("Add at least three different points before finishing.");
  if (vertices.length > MAX_BOUNDARY_POINTS)
    throw new Error(
      `A field boundary can contain at most ${MAX_BOUNDARY_POINTS} points.`,
    );
  for (const [longitude, latitude] of vertices)
    locationSchema.parse({ latitude, longitude });
  if (
    new Set(vertices.map((point) => point.join(","))).size !== vertices.length
  )
    throw new Error(
      "The outline touches itself. Undo the last section and try again.",
    );
  const boundary = [...vertices, vertices[0]];
  const shape = polygon([boundary]);
  if (kinks(shape).features.length)
    throw new Error(
      "The outline crosses itself. Undo the last section and try again.",
    );
  const squareMetres = area(shape);
  if (!Number.isFinite(squareMetres) || squareMetres < 1)
    throw new Error("The outline has no usable area. Draw a wider boundary.");
  const [longitude, latitude] = representativePoint(vertices);
  return {
    boundary,
    areaHectares: squareMetres / 10_000,
    location: locationSchema.parse({ name, latitude, longitude }),
  };
}
