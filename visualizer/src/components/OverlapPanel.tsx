import { useMemo, useState } from 'react';
import { pairKey } from '../domain/overlap';
import type { OverlapPair, OverlapReport } from '../domain/types';

interface OverlapPanelProps {
  report: OverlapReport | null;
  selectedPairKey: string | null;
  onFocusPair: (pair: OverlapPair) => void;
}

type PairFilter = 'all' | 'overlapping' | 'undecided';

const MAX_VISIBLE_PAIRS = 200;

const FILTERS: { key: PairFilter; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'overlapping', label: '重叠' },
  { key: 'undecided', label: '待判定' },
];

export function OverlapPanel({ report, selectedPairKey, onFocusPair }: OverlapPanelProps) {
  const [filter, setFilter] = useState<PairFilter>('all');

  const filtered = useMemo(() => {
    if (!report) return [];
    return filter === 'all' ? [...report.pairs] : report.pairs.filter((pair) => pair.status === filter);
  }, [report, filter]);

  if (!report) return <p className="text-xs text-slate-400">未加载题目。</p>;

  const visible = filtered.slice(0, MAX_VISIBLE_PAIRS);

  return (
    <div className="text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded bg-rose-500/15 px-1.5 py-0.5 text-[11px] text-rose-300">重叠 {report.overlapping}</span>
        <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[11px] text-amber-200">
          待判定 {report.undecided}
        </span>
        <span className="text-[11px] text-slate-500">AABB 预筛后 SAT 检查 {report.testedPairs} 对</span>
      </div>

      <div className="mt-2 flex gap-1" role="group" aria-label="pair 过滤">
        {FILTERS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            aria-pressed={filter === key}
            onClick={() => setFilter(key)}
            className={`min-h-11 flex-1 rounded border px-2 text-xs transition-colors duration-100 sm:min-h-8 ${
              filter === key
                ? 'border-sky-500/70 bg-sky-500/15 text-sky-200'
                : 'border-slate-700 text-slate-400 hover:bg-slate-800'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <p className="mt-2 text-[11px] text-slate-400">未发现可疑 pair（宽相位预筛后 SAT 全部判定为分离）。</p>
      ) : (
        <ul className="mt-2 space-y-1">
          {visible.map((pair) => (
            <li key={pairKey(pair)}>
              <button
                type="button"
                onClick={() => onFocusPair(pair)}
                aria-pressed={selectedPairKey === pairKey(pair)}
                className={`flex min-h-11 w-full items-center justify-between gap-2 rounded border px-2 text-left transition-colors duration-100 ${
                  selectedPairKey === pairKey(pair)
                    ? 'border-amber-400 bg-amber-500/10'
                    : 'border-slate-800 hover:border-slate-600 hover:bg-slate-800/60'
                }`}
              >
                <span className="font-mono text-slate-200">
                  #{pair.first}–#{pair.second}
                </span>
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] ${
                    pair.status === 'overlapping'
                      ? 'bg-rose-500/15 text-rose-300'
                      : 'bg-amber-500/15 text-amber-200'
                  }`}
                >
                  {pair.status === 'overlapping' ? '重叠' : '接触带/待判定'}
                </span>
                <span className="font-mono text-[11px] text-slate-400">{pair.overlap.toFixed(4)}</span>
              </button>
            </li>
          ))}
          {filtered.length > MAX_VISIBLE_PAIRS && (
            <li className="px-1 text-[11px] text-slate-500">
              仅显示前 {MAX_VISIBLE_PAIRS} 条，共 {filtered.length} 条。可用过滤缩小范围。
            </li>
          )}
        </ul>
      )}

      <p className="mt-2 text-[11px] text-amber-300/90">
        “待判定”表示落在接触带（±1e-8）内，既未证明分离也未确认重叠，不能视为合法；网格布局的相邻接触会大量落入该状态。最终由项目 Python
        高精度判别器认证。
      </p>
    </div>
  );
}
