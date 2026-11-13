import { BROAD_PHASE_PADDING, CONTACT_TOLERANCE, aabbOverlap, padAabb } from './geometry';
import type { OverlapPair, OverlapReport, OverlapStatus, Quad, SquareRecord } from './types';

export interface PairStatus {
  status: OverlapStatus;
  overlap: number;
}

function axisSpan(quad: Quad, axisX: number, axisY: number): [number, number] {
  let minimum = Infinity;
  let maximum = -Infinity;
  for (const vertex of quad) {
    const value = vertex.x * axisX + vertex.y * axisY;
    if (value < minimum) minimum = value;
    if (value > maximum) maximum = value;
  }
  return [minimum, maximum];
}

export function satStatus(first: SquareRecord, second: SquareRecord): PairStatus {
  const axes: [number, number][] = [
    [Math.cos(first.pose.angle), Math.sin(first.pose.angle)],
    [-Math.sin(first.pose.angle), Math.cos(first.pose.angle)],
    [Math.cos(second.pose.angle), Math.sin(second.pose.angle)],
    [-Math.sin(second.pose.angle), Math.cos(second.pose.angle)],
  ];
  let overlap = Infinity;
  for (const [axisX, axisY] of axes) {
    const [firstMin, firstMax] = axisSpan(first.quad, axisX, axisY);
    const [secondMin, secondMax] = axisSpan(second.quad, axisX, axisY);
    const axisOverlap = Math.min(firstMax, secondMax) - Math.max(firstMin, secondMin);
    if (axisOverlap < overlap) overlap = axisOverlap;
  }
  const status: OverlapStatus =
    overlap < -CONTACT_TOLERANCE ? 'separated' : overlap > CONTACT_TOLERANCE ? 'overlapping' : 'undecided';
  return { status, overlap };
}

export function checkOverlaps(squares: readonly SquareRecord[]): OverlapReport {
  const padded = squares.map((square) => padAabb(square.bounds, BROAD_PHASE_PADDING));
  const order = squares.map((_, index) => index).sort((left, right) => padded[left].minX - padded[right].minX);
  const pairs: OverlapPair[] = [];
  let testedPairs = 0;

  for (let cursor = 0; cursor < order.length; cursor += 1) {
    const firstIndex = order[cursor];
    const firstBounds = padded[firstIndex];
    for (let next = cursor + 1; next < order.length; next += 1) {
      const secondIndex = order[next];
      const secondBounds = padded[secondIndex];
      if (secondBounds.minX > firstBounds.maxX) break;
      if (!aabbOverlap(firstBounds, secondBounds)) continue;
      testedPairs += 1;
      const first = squares[firstIndex];
      const second = squares[secondIndex];
      const { status, overlap } = satStatus(first, second);
      if (status === 'separated') continue;
      pairs.push({
        first: Math.min(first.squareId, second.squareId),
        second: Math.max(first.squareId, second.squareId),
        status,
        overlap,
      });
    }
  }

  pairs.sort((left, right) => left.first - right.first || left.second - right.second);
  return {
    pairs,
    overlapping: pairs.filter((pair) => pair.status === 'overlapping').length,
    undecided: pairs.filter((pair) => pair.status === 'undecided').length,
    testedPairs,
  };
}

export function pairsForSquare(report: OverlapReport, squareId: number): OverlapPair[] {
  return report.pairs.filter((pair) => pair.first === squareId || pair.second === squareId);
}

export function pairKey(pair: { first: number; second: number }): string {
  return `${pair.first}-${pair.second}`;
}
