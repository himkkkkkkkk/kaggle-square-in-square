import { describe, expect, it } from 'vitest';
import { pickSquare, pointInQuad } from '../canvas/hitTest';
import { parseDecimalLiteral } from '../domain/decimal';
import { gridCsv, singleSquareCsv, twoSquaresCsv } from '../domain/fixtures';
import { analyzeLayout, gridFallbackScore, rawScore, summarizeSubmission } from '../domain/metrics';
import { checkOverlaps } from '../domain/overlap';
import { parseSubmissionCsv, puzzleToCsv } from '../domain/submission';
import type { LoadedSubmission } from '../domain/types';

function load(csv: string): LoadedSubmission {
  const result = parseSubmissionCsv(csv, 'test.csv');
  if (!result.submission) throw new Error(result.error ?? '解析失败');
  return result.submission;
}

describe('几何与指标', () => {
  it('n=1 网格：L=1、s=0', () => {
    const analyzed = analyzeLayout(load(gridCsv(1)).puzzles[0]);
    expect(analyzed.layout.bounds?.sideLength).toBeCloseTo(1, 12);
    expect(analyzed.summary.score).toBeCloseTo(0, 12);
    expect(analyzed.report.pairs).toHaveLength(0);
  });

  it('n=4 网格：L=2、s=0', () => {
    const analyzed = analyzeLayout(load(gridCsv(4)).puzzles[0]);
    expect(analyzed.layout.bounds?.sideLength).toBeCloseTo(2, 12);
    expect(analyzed.summary.score).toBeCloseTo(0, 12);
    expect(rawScore(4, 2)).toBeCloseTo(0, 12);
  });

  it('n=2 网格：s=√2−1', () => {
    const analyzed = analyzeLayout(load(gridCsv(2)).puzzles[0]);
    expect(analyzed.layout.bounds?.sideLength).toBeCloseTo(2, 12);
    expect(analyzed.summary.score).toBeCloseTo(Math.SQRT2 - 1, 12);
  });

  it('旋转 45° 的单个正方形：L≈√2', () => {
    const layout = load(singleSquareCsv(Math.PI / 4)).puzzles[0];
    expect(layout.bounds?.sideLength).toBeCloseTo(Math.SQRT2, 12);
  });

  it('整体平移后 L 与 s 不变', () => {
    const base = analyzeLayout(load(gridCsv(4)).puzzles[0]);
    const shifted = analyzeLayout(load(gridCsv(4, 3.25, -7.5)).puzzles[0]);
    expect(shifted.layout.bounds?.sideLength).toBeCloseTo(base.layout.bounds?.sideLength ?? NaN, 12);
    expect(shifted.summary.score).toBeCloseTo(base.summary.score ?? NaN, 12);
  });

  it('L 取横纵跨度的最大值', () => {
    const layout = load('n,square_id,x,y,angle\n2,0,0.5,0.5,0\n2,1,5.5,0.5,0\n').puzzles[0];
    expect(layout.bounds?.width).toBeCloseTo(6, 12);
    expect(layout.bounds?.height).toBeCloseTo(1, 12);
    expect(layout.bounds?.sideLength).toBeCloseTo(6, 12);
  });
});

describe('快速重叠检查', () => {
  it('两个边界接触正方形：待判定，不显示正面积重叠', () => {
    const report = checkOverlaps(load(twoSquaresCsv(1)).puzzles[0].squares);
    expect(report.overlapping).toBe(0);
    expect(report.pairs).toHaveLength(1);
    expect(report.pairs[0].status).toBe('undecided');
    expect(report.pairs[0].overlap).toBeCloseTo(0, 12);
  });

  it('两个明显重叠正方形：可跳转并标记', () => {
    const report = checkOverlaps(load(twoSquaresCsv(0.5)).puzzles[0].squares);
    expect(report.overlapping).toBe(1);
    expect(report.pairs[0]).toMatchObject({ first: 0, second: 1, status: 'overlapping' });
  });

  it('n=1000 网格：L=32、无重叠 pair，接触全部为待判定', () => {
    const analyzed = analyzeLayout(load(gridCsv(1000)).puzzles[0]);
    expect(analyzed.layout.squares).toHaveLength(1000);
    expect(analyzed.layout.bounds?.sideLength).toBeCloseTo(32, 9);
    expect(analyzed.summary.score).toBeCloseTo(32 / Math.sqrt(1000) - 1, 9);
    expect(analyzed.report.overlapping).toBe(0);
    expect(analyzed.report.pairs.length).toBeGreaterThan(0);
    expect(analyzed.report.pairs.every((pair) => pair.status === 'undecided')).toBe(true);
    expect(analyzed.summary.previewStatus).toBe('pending');
  });
});

describe('CSV 解析、异常与导出', () => {
  it('保留原始十进制字符串（含科学计数法）并只导出当前 n', () => {
    const submission = load(
      'n,square_id,x,y,angle\n' +
        '16,0,5.0e-1,5.0e-1,0e0\n' +
        '16,1,1.5e+0,5.0e-1,0e0\n',
    );
    const layout = submission.puzzles[0];
    expect(layout.issues.filter((issue) => issue.kind === 'structure').length).toBeGreaterThan(0);
    expect(layout.squares[0].raw.x).toBe('5.0e-1');
    expect(layout.squares[0].pose.x).toBeCloseTo(0.5, 12);
    const csv = puzzleToCsv(layout);
    const lines = csv.trim().split(/\r?\n/);
    expect(lines[0]).toBe('n,square_id,x,y,angle');
    expect(lines).toHaveLength(3);
    expect(lines[1]).toBe('16,0,5.0e-1,5.0e-1,0e0');
    expect(csv).not.toContain('n=16');
  });

  it('缺失 square_id / 行数不足触发错误并回退网格罚分', () => {
    const analyzed = analyzeLayout(load('n,square_id,x,y,angle\n2,0,0.5,0.5,0\n').puzzles[0]);
    expect(analyzed.layout.issues.some((issue) => issue.severity === 'error')).toBe(true);
    expect(analyzed.summary.previewStatus).toBe('grid-fallback');
    expect(analyzed.summary.score).toBeNull();
    expect(gridFallbackScore(2)).toBeCloseTo(Math.SQRT2 - 1, 12);
  });

  it('缺少必需列直接报错', () => {
    const result = parseSubmissionCsv('n,square_id,x,y\n1,0,0,0\n', 'bad.csv');
    expect(result.submission).toBeNull();
    expect(result.error).toContain('angle');
  });

  it('拒绝非十进制字面量与超出双精度的输入', () => {
    expect(parseDecimalLiteral('abc').ok).toBe(false);
    expect(parseDecimalLiteral('1e400')).toMatchObject({ ok: false, problem: 'range' });
    const layout = load('n,square_id,x,y,angle\n1,0,abc,0,0\n').puzzles[0];
    expect(layout.issues.some((issue) => issue.kind === 'numeric')).toBe(true);
    expect(layout.squares).toHaveLength(0);
  });

  it('命中测试可选中旋转后的正方形', () => {
    const layout = load(singleSquareCsv(Math.PI / 4)).puzzles[0];
    expect(pointInQuad({ x: 0.3, y: 0.3 }, layout.squares[0].quad)).toBe(true);
    expect(pickSquare(layout, { x: 0, y: 0 })).toBe(0);
    expect(pickSquare(layout, { x: 0.6, y: 0.6 })).toBeNull();
  });
});

describe('总分口径', () => {
  it('部分文件只统计已加载题目；完整口径缺失按网格罚分', () => {
    const submission = load(gridCsv(4));
    const summaries = submission.puzzles.map((layout) => analyzeLayout(layout).summary);
    const totals = summarizeSubmission(summaries);
    expect(totals.loadedCount).toBe(1);
    expect(totals.loadedScore).toBeCloseTo(0, 9);
    expect(totals.rangeMissing).toBe(999);
    expect(totals.complete).toBe(false);
    let expected = 0;
    for (let n = 2; n <= 1000; n += 1) expected += gridFallbackScore(n);
    expect(totals.rangeScore).toBeCloseTo(expected, 6);
  });
});
