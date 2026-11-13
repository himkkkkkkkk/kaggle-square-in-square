import { useState } from 'react';
import type { ReactNode } from 'react';

interface PanelProps {
  title: string;
  className?: string;
  scroll?: boolean;
  children: ReactNode;
}

export function Panel({ title, className = '', scroll = true, children }: PanelProps) {
  const [open, setOpen] = useState(true);
  return (
    <section
      className={`flex min-h-0 flex-col overflow-hidden rounded-lg border border-slate-800 bg-slate-900/50 ${className}`}
    >
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        className="flex min-h-11 shrink-0 items-center justify-between gap-2 border-b border-slate-800 px-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-300 transition-colors duration-100 hover:bg-slate-800/60"
      >
        <span>{title}</span>
        <span aria-hidden="true" className="font-mono text-slate-500">
          {open ? '−' : '+'}
        </span>
      </button>
      {open && <div className={scroll ? 'min-h-0 flex-1 overflow-y-auto p-3' : 'p-3'}>{children}</div>}
    </section>
  );
}
