import type { PuzzleLayout, Quad, Vertex } from '../domain/types';

export function pointInQuad(point: Vertex, quad: Quad): boolean {
  let positive = 0;
  let negative = 0;
  for (let index = 0; index < quad.length; index += 1) {
    const start = quad[index];
    const end = quad[(index + 1) % quad.length];
    const cross = (end.x - start.x) * (point.y - start.y) - (end.y - start.y) * (point.x - start.x);
    if (cross > 0) positive += 1;
    else if (cross < 0) negative += 1;
  }
  return positive === 0 || negative === 0;
}

/** 后绘制的正方形在上层，因此从数组末尾向前命中。 */
export function pickSquare(layout: PuzzleLayout, point: Vertex): number | null {
  for (let index = layout.squares.length - 1; index >= 0; index -= 1) {
    const square = layout.squares[index];
    if (
      point.x < square.bounds.minX ||
      point.x > square.bounds.maxX ||
      point.y < square.bounds.minY ||
      point.y > square.bounds.maxY
    ) {
      continue;
    }
    if (pointInQuad(point, square.quad)) return square.squareId;
  }
  return null;
}
