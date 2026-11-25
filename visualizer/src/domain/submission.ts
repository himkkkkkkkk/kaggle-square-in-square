import Papa from 'papaparse';
import { MAX_ANGLE_MAGNITUDE, MAX_COORDINATE_MAGNITUDE, parseDecimalLiteral } from './decimal';
import { boundsFromAabb, quadBounds, squareQuad, unionBounds } from './geometry';
import type { LoadedSubmission, PuzzleIssue, PuzzleLayout, SquareRecord } from './types';

export const REQUIRED_COLUMNS = ['n', 'square_id', 'x', 'y', 'angle'] as const;
export const MIN_PUZZLE_SIZE = 1;
export const MAX_PUZZLE_SIZE = 1000;
export const JSON_MAX_PUZZLE_SIZE = 2043;
export const AREA_LOWER_BOUND_TOLERANCE = 1e-7;

interface CsvRow {
  [column: string]: string | undefined;
}

interface RawRecord {
  line: number;
  squareIdText: string;
  x: string;
  y: string;
  angle: string;
}

export interface SubmissionParseResult {
  submission: LoadedSubmission | null;
  error: string | null;
}

export function parseSubmissionCsv(text: string, sourceName: string): SubmissionParseResult {
  if (text.trim().length === 0) return { submission: null, error: '文件为空' };

  const parsed = Papa.parse<CsvRow>(text, {
    header: true,
    skipEmptyLines: 'greedy',
    dynamicTyping: false,
    transformHeader: (header) => header.trim(),
  });

  const fields = parsed.meta.fields ?? [];
  const missingColumns = REQUIRED_COLUMNS.filter((column) => !fields.includes(column));
  if (missingColumns.length > 0) {
    return { submission: null, error: `缺少必需列：${missingColumns.join('、')}` };
  }
  if (parsed.data.length === 0) return { submission: null, error: '没有数据行' };

  const fileIssues: PuzzleIssue[] = parsed.errors.slice(0, 3).map<PuzzleIssue>((error) => ({
    severity: 'warning',
    kind: 'structure',
    message: `CSV 第 ${typeof error.row === 'number' ? error.row + 2 : '?'} 行：${error.message}`,
  }));

  const grouped = new Map<number, RawRecord[]>();
  for (const [index, row] of parsed.data.entries()) {
    const line = index + 2;
    const nText = (row.n ?? '').trim();
    const n = Number(nText);
    if (!/^\d+$/.test(nText) || !Number.isInteger(n) || n < MIN_PUZZLE_SIZE || n > MAX_PUZZLE_SIZE) {
      fileIssues.push({
        severity: 'error',
        kind: 'structure',
        message: `第 ${line} 行：n="${nText}" 不在 ${MIN_PUZZLE_SIZE}..${MAX_PUZZLE_SIZE}`,
      });
      continue;
    }
    const record: RawRecord = {
      line,
      squareIdText: (row.square_id ?? '').trim(),
      x: (row.x ?? '').trim(),
      y: (row.y ?? '').trim(),
      angle: (row.angle ?? '').trim(),
    };
    const bucket = grouped.get(n);
    if (bucket) bucket.push(record);
    else grouped.set(n, [record]);
  }

  if (grouped.size === 0) return { submission: null, error: '没有可用的题目数据行' };

  const puzzles = [...grouped.entries()]
    .sort((left, right) => left[0] - right[0])
    .map(([n, records]) => buildPuzzle(n, records));

  return {
    submission: {
      sourceName,
      rowCount: puzzles.reduce((total, puzzle) => total + puzzle.rows, 0),
      puzzleSizes: puzzles.map((puzzle) => puzzle.n),
      puzzles,
      fileIssues,
    },
    error: null,
  };
}

/** Parse search/result.json: {"10": [[x, y, angle], ...]}. Array indices become square_id. */
export function parseSubmissionJson(text: string, sourceName: string): SubmissionParseResult {
  if (text.trim().length === 0) return { submission: null, error: '文件为空' };
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch (error) {
    return { submission: null, error: `JSON 格式错误：${error instanceof Error ? error.message : String(error)}` };
  }
  if (typeof data !== 'object' || data === null || Array.isArray(data)) {
    return { submission: null, error: 'JSON 顶层必须是 n 到布局数组的对象' };
  }

  const grouped = new Map<number, RawRecord[]>();
  const fileIssues: PuzzleIssue[] = [];
  for (const [nText, value] of Object.entries(data)) {
    const n = Number(nText);
    if (!/^\d+$/.test(nText) || !Number.isInteger(n) || n < MIN_PUZZLE_SIZE || n > JSON_MAX_PUZZLE_SIZE) {
      fileIssues.push({
        severity: 'error',
        kind: 'structure',
        message: `n="${nText}" 不在 ${MIN_PUZZLE_SIZE}..${JSON_MAX_PUZZLE_SIZE}`,
      });
      continue;
    }
    if (!Array.isArray(value)) return { submission: null, error: `n=${n} 的布局不是数组` };
    const records: RawRecord[] = [];
    for (const [squareId, square] of value.entries()) {
      if (
        !Array.isArray(square) ||
        square.length !== 3 ||
        square.some((item) => typeof item !== 'number' && typeof item !== 'string')
      ) {
        return { submission: null, error: `n=${n} 的第 ${squareId} 个正方形必须是 [x, y, angle]` };
      }
      records.push({
        line: squareId + 1,
        squareIdText: String(squareId),
        x: String(square[0]),
        y: String(square[1]),
        angle: String(square[2]),
      });
    }
    grouped.set(n, records);
  }
  if (grouped.size === 0) return { submission: null, error: '没有可用的题目布局' };

  const puzzles = [...grouped.entries()]
    .sort((left, right) => left[0] - right[0])
    .map(([n, records]) => buildPuzzle(n, records));
  return {
    submission: {
      sourceName,
      rowCount: puzzles.reduce((total, puzzle) => total + puzzle.rows, 0),
      puzzleSizes: puzzles.map((puzzle) => puzzle.n),
      puzzles,
      fileIssues,
    },
    error: null,
  };
}

export function parseSubmissionFile(text: string, sourceName: string): SubmissionParseResult {
  return sourceName.toLowerCase().endsWith('.json')
    ? parseSubmissionJson(text, sourceName)
    : parseSubmissionCsv(text, sourceName);
}

function buildPuzzle(n: number, records: readonly RawRecord[]): PuzzleLayout {
  const issues: PuzzleIssue[] = [];
  const squares: SquareRecord[] = [];
  const seenIds = new Set<number>();
  const poseOwners = new Map<string, number>();

  if (records.length !== n) {
    issues.push({ severity: 'error', kind: 'structure', message: `行数 ${records.length} 与 n=${n} 不一致` });
  }

  for (const record of records) {
    const squareId = Number(record.squareIdText);
    if (!/^\d+$/.test(record.squareIdText) || !Number.isInteger(squareId) || squareId < 0 || squareId >= n) {
      issues.push({
        severity: 'error',
        kind: 'structure',
        message: `第 ${record.line} 行：square_id="${record.squareIdText}" 不在 0..${n - 1}`,
      });
      continue;
    }
    if (seenIds.has(squareId)) {
      issues.push({
        severity: 'error',
        kind: 'duplicate',
        message: `第 ${record.line} 行：square_id ${squareId} 重复出现`,
      });
      continue;
    }
    seenIds.add(squareId);

    const xLiteral = parseDecimalLiteral(record.x);
    const yLiteral = parseDecimalLiteral(record.y);
    const angleLiteral = parseDecimalLiteral(record.angle);
    if (!xLiteral.ok || !yLiteral.ok || !angleLiteral.ok) {
      const problems = [
        !xLiteral.ok ? `x：${xLiteral.message}` : null,
        !yLiteral.ok ? `y：${yLiteral.message}` : null,
        !angleLiteral.ok ? `angle：${angleLiteral.message}` : null,
      ].filter((problem): problem is string => problem !== null);
      issues.push({ severity: 'error', kind: 'numeric', message: `square_id ${squareId}：${problems.join('；')}` });
      continue;
    }
    if (Math.max(Math.abs(xLiteral.value), Math.abs(yLiteral.value)) > MAX_COORDINATE_MAGNITUDE) {
      issues.push({
        severity: 'error',
        kind: 'anomaly',
        message: `square_id ${squareId}：坐标绝对值超过 ${MAX_COORDINATE_MAGNITUDE}`,
      });
      continue;
    }
    if (Math.abs(angleLiteral.value) > MAX_ANGLE_MAGNITUDE) {
      issues.push({
        severity: 'error',
        kind: 'anomaly',
        message: `square_id ${squareId}：angle 绝对值超过 ${MAX_ANGLE_MAGNITUDE}`,
      });
      continue;
    }

    const poseKey = `${record.x}|${record.y}|${record.angle}`;
    const owner = poseOwners.get(poseKey);
    if (owner === undefined) poseOwners.set(poseKey, squareId);
    else {
      issues.push({
        severity: 'warning',
        kind: 'duplicate',
        message: `square_id ${owner} 与 ${squareId} 位姿完全相同`,
      });
    }

    const quad = squareQuad(xLiteral.value, yLiteral.value, angleLiteral.value);
    squares.push({
      squareId,
      raw: { x: record.x, y: record.y, angle: record.angle },
      pose: { x: xLiteral.value, y: yLiteral.value, angle: angleLiteral.value },
      quad,
      bounds: quadBounds(quad),
    });
  }

  const missingIds = Array.from({ length: n }, (_, index) => index).filter((id) => !seenIds.has(id));
  if (missingIds.length > 0) {
    const preview = missingIds.slice(0, 8).join(', ');
    issues.push({
      severity: 'error',
      kind: 'structure',
      message: `缺少 square_id：${preview}${missingIds.length > 8 ? ` 等 ${missingIds.length} 个` : ''}`,
    });
  }

  squares.sort((left, right) => left.squareId - right.squareId);
  const combined = squares.length > 0 ? unionBounds(squares.map((square) => square.bounds)) : null;
  const bounds = combined ? boundsFromAabb(combined) : null;

  if (bounds && squares.length === n && bounds.sideLength < Math.sqrt(n) - AREA_LOWER_BOUND_TOLERANCE) {
    issues.push({
      severity: 'error',
      kind: 'anomaly',
      message: `包围边长 ${bounds.sideLength.toFixed(6)} 低于面积下界 √n=${Math.sqrt(n).toFixed(6)}`,
    });
  }

  return { n, rows: records.length, squares, issues, bounds };
}

/** 导出当前 n：列固定为 n,square_id,x,y,angle，坐标使用原始十进制字符串。 */
export function puzzleToCsv(layout: PuzzleLayout): string {
  const rows = layout.squares.map((square) => [
    String(layout.n),
    String(square.squareId),
    square.raw.x,
    square.raw.y,
    square.raw.angle,
  ]);
  return `${Papa.unparse({ fields: [...REQUIRED_COLUMNS], data: rows })}\n`;
}

export function squareCsvRow(n: number, square: SquareRecord): string {
  return `${n},${square.squareId},${square.raw.x},${square.raw.y},${square.raw.angle}`;
}
