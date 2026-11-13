import { useMemo, useRef, useState } from 'react';
import type { KeyboardEvent as ReactKeyboardEvent } from 'react';
import { OFFICIAL_PUZZLE_COUNT, formatScore } from '../domain/metrics';
import type { PreviewStatus, PuzzleSummary, SubmissionSummary } from '../domain/metrics';
import type { PuzzleIssue } from '../domain/types';
import { Panel } from './Panel';

type PuzzleSort = 'n' | 'score' | 'overlap';

interface PuzzleNavigatorProps {
  summaries: readonly PuzzleSummary[];
  totals: SubmissionSummary;
  fileIssues: readonly PuzzleIssue[];
  activeN: number | null;
  onSelect: (n: number) => void;
}

const STATUS_TEXT: Record<PreviewStatus, string> = {
  ok: '预览通过',
  'grid-fallback': '网格罚分',
  pending: '待判定',
};

const STATUS_CLASS: Record<PreviewStatus, string> = {
  ok: 'bg-emerald-500/15 text-emerald-300',
  'grid-fallback': 'bg-rose-500/15 text-rose-300',
  pending: 'bg-amber-500/15 text-amber-200',
};

const SORTS: { key: PuzzleSort; label: string }[] = [
  { key: 'n', label: '按 n' },
  { key: 'score', label: '按得分' },
  { key: 'overlap', label: '按重叠' },
];

export function PuzzleNavigator({ summaries, totals, fileIssues, activeN, onSelect }: PuzzleNavigatorProps) {
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<PuzzleSort>('n');
  const listRef = useRef<HTMLUListElement | null>(null);

  const ordered = useMemo(() => {
    const keyword = query.trim();
    const filtered = keyword === '' ? [...summaries] : summaries.filter((summary) => String(summary.n).includes(keyword));
    filtered.sort((left, right) => {
      if (sort === 'score') {
        return (left.score ?? left.gridScore) - (right.score ?? right.gridScore) || left.n - right.n;
      }
      if (sort === 'overlap') {
        return right.overlapping + right.undecided - (left.overlapping + left.undecided) || left.n - right.n;
      }
      return left.n - right.n;
    });
    return filtered;
  }, [summaries, query, sort]);

  const focusItem = (index: number) => {
    const item = ordered[index];
    if (!item) return;
    onSelect(item.n);
    listRef.current?.querySelector<HTMLButtonElement>(`[data-index="${index}"]`)?.focus();
  };

  const handleItemKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>, index: number) => {
    const lastIndex = ordered.length - 1;
    const target =
      event.key === 'ArrowDown'
        ? index + 1
        : event.key === 'ArrowUp'
          ? index - 1
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? lastIndex
              : null;
    if (target === null) return;
    event.preventDefault();
    focusItem(Math.min(lastIndex, Math.max(0, target)));
  };

  return (
    <Panel title="题目导航" className="min-h-0 flex-1">
      <div className="flex flex-col gap-2">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown') {
              event.preventDefault();
              focusItem(0);
            }
          }}
          type="search"
          inputMode="numeric"
          placeholder="搜索 n"
          aria-label="按 n 搜索题目"
          className="min-h-11 w-full rounded border border-slate-700 bg-slate-950 px-2 text-sm text-slate-100 placeholder:text-slate-500 sm:min-h-9"
        />
        <div className="flex gap-1" role="group" aria-label="排序方式">
          {SORTS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              aria-pressed={sort === key}
              onClick={() => setSort(key)}
              className={`min-h-11 flex-1 rounded border px-2 text-xs transition-colors duration-100 sm:min-h-8 ${
                sort === key
                  ? 'border-sky-500/70 bg-sky-500/15 text-sky-200'
                  : 'border-slate-700 text-slate-400 hover:bg-slate-800'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <ul ref={listRef} className="mt-2 space-y-1">
        {ordered.map((summary, index) => (
          <li key={summary.n}>
            <button
              type="button"
              data-index={index}
              aria-current={summary.n === activeN ? 'true' : undefined}
              onClick={() => onSelect(summary.n)}
              onKeyDown={(event) => handleItemKeyDown(event, index)}
              className={`min-h-11 w-full rounded border px-2 py-1.5 text-left transition-colors duration-100 ${
                summary.n === activeN
                  ? 'border-sky-500 bg-sky-500/10'
                  : 'border-slate-800 hover:border-slate-600 hover:bg-slate-800/60'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-sm text-slate-100">n={summary.n}</span>
                <span className={`rounded px-1.5 py-0.5 text-[10px] ${STATUS_CLASS[summary.previewStatus]}`}>
                  {STATUS_TEXT[summary.previewStatus]}
                </span>
              </div>
              <div className="mt-0.5 flex flex-wrap gap-x-3 font-mono text-[11px] text-slate-400">
                <span>L={formatScore(summary.sideLength, 4)}</span>
                <span>s={formatScore(summary.score, 6)}</span>
                <span>
                  行 {summary.rows}/{summary.n}
                </span>
                <span>
                  重叠 {summary.overlapping} · 待判定 {summary.undecided}
                </span>
              </div>
            </button>
          </li>
        ))}
        {ordered.length === 0 && <li className="px-1 py-3 text-xs text-slate-500">没有匹配的题目。</li>}
      </ul>

      <div className="mt-3 border-t border-slate-800 pt-2 text-[11px] text-slate-400">
        <p>
          已加载 {totals.loadedCount} 题 · 预览通过 {totals.okCount} · 网格罚分 {totals.fallbackCount} · 待判定{' '}
          {totals.pendingCount}
        </p>
        <p className="mt-1">
          已加载题目合计（保守口径）：
          <span className="font-mono text-slate-200">{formatScore(totals.loadedScore, 9)}</span>
        </p>
        <p className="mt-1">
          按官方口径 1..{OFFICIAL_PUZZLE_COUNT} 估算（缺失/非法/待判定按网格罚分）：
          <span className="font-mono text-slate-200">{formatScore(totals.rangeScore, 9)}</span>，缺失{' '}
          {totals.rangeMissing} 题
        </p>
        {!totals.complete && (
          <p className="mt-1 text-amber-300/90">
            当前文件不是完整 1000 题提交，以上仅为已加载范围 + 网格罚分补齐的估算，不是官方成绩。
          </p>
        )}
        {fileIssues.length > 0 && (
          <ul className="mt-1 space-y-0.5 text-amber-300/90">
            {fileIssues.slice(0, 3).map((issue, index) => (
              <li key={index} className="break-words">
                {issue.message}
              </li>
            ))}
            {fileIssues.length > 3 && <li>还有 {fileIssues.length - 3} 条文件级问题</li>}
          </ul>
        )}
      </div>
    </Panel>
  );
}
