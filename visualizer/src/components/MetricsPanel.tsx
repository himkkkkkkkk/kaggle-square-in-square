import { formatScore } from '../domain/metrics';
import type { PuzzleSummary } from '../domain/metrics';
import type { PuzzleIssue } from '../domain/types';

interface MetricsPanelProps {
  summary: PuzzleSummary | null;
  issues: readonly PuzzleIssue[];
  status: string | null;
  onExportPng: () => void;
  onExportCsv: () => void;
}

const ISSUE_KIND_LABEL: Record<PuzzleIssue['kind'], string> = {
  structure: '结构',
  numeric: '数值',
  duplicate: '重复',
  anomaly: '异常',
};

const STATUS_TEXT: Record<PuzzleSummary['previewStatus'], string> = {
  ok: '预览检查未发现重叠；最终合法性仍由项目 Python 高精度判别器认证。',
  'grid-fallback': '存在重叠或输入错误：按官方口径该题将退化为网格罚分，当前 L 仅供参考。',
  pending: '存在接触带内的待判定 pair：不得视为合法，需 Python 区间认证。',
};

const BUTTON =
  'min-h-11 rounded border border-slate-700 px-3 text-xs text-slate-200 transition-colors duration-100 hover:bg-slate-800 active:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-40 sm:min-h-9';

export function MetricsPanel({ summary, issues, status, onExportPng, onExportCsv }: MetricsPanelProps) {
  if (!summary) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2 text-xs text-slate-400">
        未选择题目：请先在左侧选择 n。
      </div>
    );
  }

  const metrics: { label: string; value: string }[] = [
    { label: 'n', value: String(summary.n) },
    { label: 'L_n', value: formatScore(summary.sideLength, 6) },
    { label: 's_n = L/√n − 1', value: formatScore(summary.score, 6) },
    { label: '网格罚分 s_grid', value: formatScore(summary.gridScore, 6) },
    { label: '差值 s − s_grid', value: formatScore(summary.scoreDelta, 6) },
    { label: '正方形数 / 行数', value: `${summary.squareCount} / ${summary.rows}` },
    { label: '快速重叠 pair', value: String(summary.overlapping) },
    { label: '待判定 pair', value: String(summary.undecided) },
  ];

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2">
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        {metrics.map(({ label, value }) => (
          <div key={label} className="min-w-0">
            <dt className="truncate text-[10px] uppercase tracking-wide text-slate-500">{label}</dt>
            <dd className="truncate font-mono text-sm text-slate-100">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-1 break-words text-[11px] text-slate-400">{STATUS_TEXT[summary.previewStatus]}</p>
      {issues.length > 0 && (
        <ul className="mt-1 space-y-0.5 text-[11px]">
          {issues.slice(0, 6).map((issue, index) => (
            <li
              key={`${issue.kind}-${index}`}
              className={`break-words ${issue.severity === 'error' ? 'text-rose-300' : 'text-amber-300'}`}
            >
              {issue.severity === 'error' ? '错误' : '警告'} · {ISSUE_KIND_LABEL[issue.kind]}：{issue.message}
            </li>
          ))}
          {issues.length > 6 && <li className="text-slate-500">还有 {issues.length - 6} 条问题未显示</li>}
        </ul>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button type="button" onClick={onExportPng} className={BUTTON}>
          导出当前画布 PNG
        </button>
        <button type="button" onClick={onExportCsv} className={BUTTON}>
          导出 n={summary.n} CSV
        </button>
        {status && <span className="break-words text-[11px] text-slate-400">{status}</span>}
      </div>
    </div>
  );
}
