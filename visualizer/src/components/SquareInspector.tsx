import { useState } from 'react';
import { formatDecimal } from '../domain/decimal';
import { pairKey } from '../domain/overlap';
import { squareCsvRow } from '../domain/submission';
import type { OverlapPair, PuzzleLayout, SquareRecord } from '../domain/types';

interface SquareInspectorProps {
  layout: PuzzleLayout | null;
  square: SquareRecord | null;
  pairs: readonly OverlapPair[];
  onCenter: (squareId: number) => void;
}

const BUTTON =
  'min-h-11 rounded border border-slate-700 px-3 text-xs text-slate-200 transition-colors duration-100 hover:bg-slate-800 active:bg-slate-700 sm:min-h-9';

export function SquareInspector({ layout, square, pairs, onCenter }: SquareInspectorProps) {
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');

  if (!layout) return <p className="text-xs text-slate-400">未加载题目。</p>;
  if (!square) return <p className="text-xs text-slate-400">在画布上点击正方形，查看 id、原始十进制字符串、顶点与相关 pair。</p>;

  const record = squareCsvRow(layout.n, square);
  const rows: [string, string][] = [
    ['square_id', String(square.squareId)],
    ['x 原始', square.raw.x],
    ['y 原始', square.raw.y],
    ['angle 原始', square.raw.angle],
    ['x 预览', formatDecimal(square.pose.x)],
    ['y 预览', formatDecimal(square.pose.y)],
    ['angle 预览', formatDecimal(square.pose.angle)],
  ];

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(record);
      setCopyState('copied');
    } catch {
      setCopyState('failed');
    }
  };

  return (
    <div className="text-xs">
      <dl>
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-baseline justify-between gap-2 border-b border-slate-800/70 py-1">
            <dt className="shrink-0 text-slate-500">{label}</dt>
            <dd className="break-all text-right font-mono text-slate-100">{value}</dd>
          </div>
        ))}
      </dl>

      <h3 className="mt-2 text-[10px] uppercase tracking-wide text-slate-500">四个顶点（由中心与旋转角计算）</h3>
      <ul className="mt-1 space-y-0.5 font-mono text-[11px] text-slate-300">
        {square.quad.map((vertex, index) => (
          <li key={index} className="flex justify-between gap-2">
            <span className="text-slate-500">v{index}</span>
            <span>
              ({formatDecimal(vertex.x)}, {formatDecimal(vertex.y)})
            </span>
          </li>
        ))}
      </ul>

      <div className="mt-2 flex flex-wrap gap-2">
        <button type="button" onClick={() => onCenter(square.squareId)} className={BUTTON}>
          居中到该正方形
        </button>
        <button type="button" onClick={handleCopy} className={BUTTON}>
          复制记录
        </button>
      </div>
      <code className="mt-2 block break-all rounded bg-slate-950 px-2 py-1 font-mono text-[11px] text-slate-400">
        {record}
      </code>
      {copyState === 'copied' && <p className="mt-1 text-[11px] text-emerald-300">已复制 CSV 记录。</p>}
      {copyState === 'failed' && (
        <p className="mt-1 text-[11px] text-rose-300">
          复制失败：浏览器拒绝剪贴板访问（需要安全上下文或用户授权）。可手动选中上方记录。
        </p>
      )}

      <h3 className="mt-3 text-[10px] uppercase tracking-wide text-slate-500">相关快速检查 pair</h3>
      {pairs.length === 0 ? (
        <p className="mt-1 text-[11px] text-slate-400">该正方形未出现在可疑 pair 中。</p>
      ) : (
        <ul className="mt-1 space-y-0.5 text-[11px]">
          {pairs.map((pair) => (
            <li key={pairKey(pair)} className="flex justify-between gap-2 font-mono">
              <span className="text-slate-300">
                #{pair.first}–#{pair.second}
              </span>
              <span className={pair.status === 'overlapping' ? 'text-rose-300' : 'text-amber-300'}>
                {pair.status === 'overlapping' ? '重叠' : '接触带/待判定'}
              </span>
            </li>
          ))}
          {pairs.length > 12 && <li className="text-slate-500">还有 {pairs.length - 12} 条未显示</li>}
        </ul>
      )}
    </div>
  );
}
