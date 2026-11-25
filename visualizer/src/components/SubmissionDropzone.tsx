import { useRef, useState } from 'react';
import type { ChangeEvent, DragEvent } from 'react';

interface SubmissionDropzoneProps {
  compact?: boolean;
  isParsing: boolean;
  error: string | null;
  sourceName: string | null;
  onFile: (file: File) => void;
  onDemo: () => void;
  onGrid: () => void;
  onClear: () => void;
}

const PRIMARY_BUTTON =
  'min-h-11 rounded border border-sky-500/70 bg-sky-500/15 px-3 text-xs font-medium text-sky-200 transition-colors duration-100 hover:bg-sky-500/25 active:bg-sky-500/30 sm:min-h-9';
const SECONDARY_BUTTON =
  'min-h-11 rounded border border-slate-700 px-3 text-xs text-slate-300 transition-colors duration-100 hover:bg-slate-800 active:bg-slate-700 sm:min-h-9';

export function SubmissionDropzone({
  compact = false,
  isParsing,
  error,
  sourceName,
  onFile,
  onDemo,
  onGrid,
  onClear,
}: SubmissionDropzoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragging, setDragging] = useState(false);

  const acceptFiles = (files: FileList | null) => {
    const file = files && files.length > 0 ? files[0] : null;
    if (file) onFile(file);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    acceptFiles(event.dataTransfer.files);
  };

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    acceptFiles(event.target.files);
    event.target.value = '';
  };

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={
        compact
          ? `flex min-w-0 flex-col gap-2 rounded-lg border px-3 py-2 ${dragging ? 'border-sky-400 bg-sky-500/10' : 'border-slate-800 bg-slate-900/50'}`
          : `flex min-w-0 flex-col gap-3 rounded-xl border border-dashed px-4 py-8 ${dragging ? 'border-sky-400 bg-sky-500/10' : 'border-slate-700 bg-slate-900/40'}`
      }
    >
      {!compact && (
        <div>
          <h2 className="text-sm font-semibold text-slate-100">导入 CSV / JSON 布局</h2>
          <p className="text-xs text-slate-400">支持拖放与文件选择；解析后按 n 分组预览。</p>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => inputRef.current?.click()} className={PRIMARY_BUTTON}>
          选择 CSV / JSON 文件
        </button>
        <button type="button" onClick={onDemo} className={SECONDARY_BUTTON}>
          示例布局
        </button>
        <button type="button" onClick={onGrid} className={SECONDARY_BUTTON}>
          n=1000 网格夹具
        </button>
        {sourceName && (
          <button type="button" onClick={onClear} className={SECONDARY_BUTTON}>
            清除
          </button>
        )}
      </div>
      <p className="text-[11px] text-slate-500">
        CSV 列 n, square_id, x, y, angle；JSON 格式 <code>{'{"n": [[x, y, angle], ...]}'}</code>。文件仅在本地解析。
      </p>
      {isParsing && (
        <p role="status" className="text-xs text-sky-300">
          正在解析文件…
        </p>
      )}
      {error && (
        <p role="alert" className="break-words text-xs text-rose-300">
          解析失败：{error}
        </p>
      )}
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.json,text/csv,application/json"
        className="hidden"
        onChange={handleChange}
      />
    </div>
  );
}
