export interface Vertex {
  x: number;
  y: number;
}

export type Quad = readonly [Vertex, Vertex, Vertex, Vertex];

export interface Aabb {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

export interface LayoutBounds {
  aabb: Aabb;
  width: number;
  height: number;
  sideLength: number;
}

export interface RawPose {
  x: string;
  y: string;
  angle: string;
}

export interface NumericPose {
  x: number;
  y: number;
  angle: number;
}

export interface SquareRecord {
  squareId: number;
  raw: RawPose;
  pose: NumericPose;
  quad: Quad;
  bounds: Aabb;
}

export type IssueSeverity = 'error' | 'warning';
export type IssueKind = 'structure' | 'numeric' | 'duplicate' | 'anomaly';

export interface PuzzleIssue {
  severity: IssueSeverity;
  kind: IssueKind;
  message: string;
}

export interface PuzzleLayout {
  n: number;
  rows: number;
  squares: readonly SquareRecord[];
  issues: readonly PuzzleIssue[];
  bounds: LayoutBounds | null;
}

export type OverlapStatus = 'separated' | 'overlapping' | 'undecided';

export interface OverlapPair {
  first: number;
  second: number;
  status: Exclude<OverlapStatus, 'separated'>;
  overlap: number;
}

export interface OverlapReport {
  pairs: readonly OverlapPair[];
  overlapping: number;
  undecided: number;
  testedPairs: number;
}

export interface Camera {
  scale: number;
  offsetX: number;
  offsetY: number;
}

export interface ViewportSize {
  width: number;
  height: number;
}

export interface LoadedSubmission {
  sourceName: string;
  puzzleSizes: readonly number[];
  puzzles: readonly PuzzleLayout[];
  rowCount: number;
  fileIssues: readonly PuzzleIssue[];
}
