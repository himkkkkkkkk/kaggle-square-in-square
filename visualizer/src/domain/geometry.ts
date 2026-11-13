import type { Aabb, LayoutBounds, Quad, Vertex } from './types';

export const HALF_SIDE = 0.5;
/** 与 squares_metric.geometry.FLOAT_CONTACT_TOLERANCE 对齐的接触带宽度。 */
export const CONTACT_TOLERANCE = 1e-8;
/** 与 squares_metric.geometry.BROAD_PHASE_PADDING 对齐的宽相位补齐量。 */
export const BROAD_PHASE_PADDING = 1e-7;

export function squareQuad(x: number, y: number, angle: number): Quad {
  const cosine = Math.cos(angle);
  const sine = Math.sin(angle);
  const corner = (unitX: number, unitY: number): Vertex => ({
    x: x + unitX * cosine - unitY * sine,
    y: y + unitX * sine + unitY * cosine,
  });
  return [
    corner(HALF_SIDE, HALF_SIDE),
    corner(-HALF_SIDE, HALF_SIDE),
    corner(-HALF_SIDE, -HALF_SIDE),
    corner(HALF_SIDE, -HALF_SIDE),
  ];
}

export function quadBounds(quad: Quad): Aabb {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const vertex of quad) {
    if (vertex.x < minX) minX = vertex.x;
    if (vertex.x > maxX) maxX = vertex.x;
    if (vertex.y < minY) minY = vertex.y;
    if (vertex.y > maxY) maxY = vertex.y;
  }
  return { minX, minY, maxX, maxY };
}

export function unionBounds(bounds: readonly Aabb[]): Aabb | null {
  if (bounds.length === 0) return null;
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const bound of bounds) {
    if (bound.minX < minX) minX = bound.minX;
    if (bound.minY < minY) minY = bound.minY;
    if (bound.maxX > maxX) maxX = bound.maxX;
    if (bound.maxY > maxY) maxY = bound.maxY;
  }
  return { minX, minY, maxX, maxY };
}

export function padAabb(bounds: Aabb, padding: number): Aabb {
  return {
    minX: bounds.minX - padding,
    minY: bounds.minY - padding,
    maxX: bounds.maxX + padding,
    maxY: bounds.maxY + padding,
  };
}

export function aabbOverlap(first: Aabb, second: Aabb): boolean {
  return !(
    first.maxX < second.minX ||
    second.maxX < first.minX ||
    first.maxY < second.minY ||
    second.maxY < first.minY
  );
}

export function boundsFromAabb(aabb: Aabb): LayoutBounds {
  const width = aabb.maxX - aabb.minX;
  const height = aabb.maxY - aabb.minY;
  return { aabb, width, height, sideLength: Math.max(width, height) };
}

export function aabbCenter(aabb: Aabb): Vertex {
  return { x: (aabb.minX + aabb.maxX) / 2, y: (aabb.minY + aabb.maxY) / 2 };
}
