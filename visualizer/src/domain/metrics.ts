import { checkOverlaps } from './overlap';
import type { OverlapReport, PuzzleLayout } from './types';

export const OFFICIAL_PUZZLE_COUNT = 1000;

export function rawScore(n: number, sideLength: number): number {
  return sideLength / Math.sqrt(n) - 1;
}

export function gridFallbackScore(n: number): number {
  return Math.ceil(Math.sqrt(n)) / Math.sqrt(n) - 1;
}

export function formatScore(value: number | null, digits = 6): string {
  if (value === null || !Number.isFinite(value)) return '—';
  return value.toFixed(digits);
}

export type PreviewStatus = 'ok' | 'grid-fallback' | 'pending';

export interface PuzzleSummary {
  n: number;
  rows: number;
  squareCount: number;
  sideLength: number | null;
  score: number | null;
  gridScore: number;
  scoreDelta: number | null;
  overlapping: number;
  undecided: number;
  testedPairs: number;
  previewStatus: PreviewStatus;
  errorCount: number;
  warningCount: number;
}

export function summarizePuzzle(layout: PuzzleLayout, report: OverlapReport): PuzzleSummary {
  const sideLength = layout.bounds ? layout.bounds.sideLength : null;
  const errorCount = layout.issues.filter((issue) => issue.severity === 'error').length;
  const warningCount = layout.issues.filter((issue) => issue.severity === 'warning').length;
  const score = sideLength === null || errorCount > 0 ? null : rawScore(layout.n, sideLength);
  const gridScore = gridFallbackScore(layout.n);
  const previewStatus: PreviewStatus =
    errorCount > 0 || report.overlapping > 0 ? 'grid-fallback' : report.undecided > 0 ? 'pending' : 'ok';
  return {
    n: layout.n,
    rows: layout.rows,
    squareCount: layout.squares.length,
    sideLength,
    score,
    gridScore,
    scoreDelta: score === null ? null : score - gridScore,
    overlapping: report.overlapping,
    undecided: report.undecided,
    testedPairs: report.testedPairs,
    previewStatus,
    errorCount,
    warningCount,
  };
}

/** 保守预览得分：只有预览通过才使用实测 s，否则按网格罚分（待判定同样按网格罚分）。 */
export function previewScore(summary: PuzzleSummary): number {
  return summary.previewStatus === 'ok' && summary.score !== null ? summary.score : summary.gridScore;
}

export interface SubmissionSummary {
  loadedCount: number;
  okCount: number;
  fallbackCount: number;
  pendingCount: number;
  loadedScore: number;
  rangeScore: number;
  rangeMissing: number;
  complete: boolean;
}

export function summarizeSubmission(summaries: readonly PuzzleSummary[]): SubmissionSummary {
  const bySize = new Map<number, PuzzleSummary>();
  for (const summary of summaries) bySize.set(summary.n, summary);

  let loadedScore = 0;
  let okCount = 0;
  let fallbackCount = 0;
  let pendingCount = 0;
  for (const summary of summaries) {
    loadedScore += previewScore(summary);
    if (summary.previewStatus === 'ok') okCount += 1;
    else if (summary.previewStatus === 'pending') pendingCount += 1;
    else fallbackCount += 1;
  }

  let rangeScore = 0;
  let rangeMissing = 0;
  for (let n = 1; n <= OFFICIAL_PUZZLE_COUNT; n += 1) {
    const summary = bySize.get(n);
    if (summary) rangeScore += previewScore(summary);
    else {
      rangeScore += gridFallbackScore(n);
      rangeMissing += 1;
    }
  }

  return {
    loadedCount: summaries.length,
    okCount,
    fallbackCount,
    pendingCount,
    loadedScore,
    rangeScore,
    rangeMissing,
    complete: summaries.length === OFFICIAL_PUZZLE_COUNT && rangeMissing === 0,
  };
}

export interface AnalyzedPuzzle {
  layout: PuzzleLayout;
  report: OverlapReport;
  summary: PuzzleSummary;
}

export function analyzeLayout(layout: PuzzleLayout): AnalyzedPuzzle {
  const report = checkOverlaps(layout.squares);
  return { layout, report, summary: summarizePuzzle(layout, report) };
}
