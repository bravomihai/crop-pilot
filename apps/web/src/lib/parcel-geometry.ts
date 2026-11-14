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

const equal = (a: Coordinate, b: Coordinate) => a[0] === b[0] && a[1] === b[1];

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
  if (vertices.length > 5000)
    throw new Error(
      "This outline is too detailed. Undo a stroke or redraw a smaller boundary.",
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
  const [longitude, latitude] = centerOfMass(shape).geometry.coordinates;
  return {
    boundary,
    areaHectares: squareMetres / 10_000,
    location: locationSchema.parse({ name, latitude, longitude }),
  };
}
