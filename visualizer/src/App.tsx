import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { LayoutCanvas } from './components/LayoutCanvas';
import { MetricsPanel } from './components/MetricsPanel';
import { OverlapPanel } from './components/OverlapPanel';
import { Panel } from './components/Panel';
import { PuzzleNavigator } from './components/PuzzleNavigator';
import { SquareInspector } from './components/SquareInspector';
import { SubmissionDropzone } from './components/SubmissionDropzone';
import { centerCamera, fitBounds, focusRegion } from './canvas/camera';
import { downloadCanvasPng, downloadTextFile } from './canvas/export';
import type { DisplayOptions, RenderOptions } from './canvas/renderer';
import { unionBounds } from './domain/geometry';
import { demoCsv, gridCsv } from './domain/fixtures';
import { analyzeLayout, summarizeSubmission } from './domain/metrics';
import { pairKey, pairsForSquare } from './domain/overlap';
import { parseSubmissionFile, puzzleToCsv } from './domain/submission';
import type { Camera, LoadedSubmission, OverlapPair, ViewportSize } from './domain/types';

export default function App() {
  const [isParsing, setIsParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [submission, setSubmission] = useState<LoadedSubmission | null>(null);
  const [activeN, setActiveN] = useState<number | null>(null);
  const [selectedSquareId, setSelectedSquareId] = useState<number | null>(null);
  const [selectedPairKey, setSelectedPairKey] = useState<string | null>(null);
  const [camera, setCamera] = useState<Camera>({ scale: 48, offsetX: 0, offsetY: 0 });
  const [viewport, setViewport] = useState<ViewportSize>({ width: 0, height: 0 });
  const [fitToken, setFitToken] = useState(0);
  const [display, setDisplay] = useState<DisplayOptions>({
    showIds: true,
    showVertices: false,
    showBounds: true,
    showAxes: true,
  });
  const [reducedMotion, setReducedMotion] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const analyzed = useMemo(() => (submission ? submission.puzzles.map(analyzeLayout) : []), [submission]);
  const summaries = useMemo(() => analyzed.map((item) => item.summary), [analyzed]);
  const totals = useMemo(() => summarizeSubmission(summaries), [summaries]);
  const active = useMemo(() => analyzed.find((item) => item.layout.n === activeN) ?? null, [analyzed, activeN]);
  const selectedSquare = useMemo(
    () => active?.layout.squares.find((square) => square.squareId === selectedSquareId) ?? null,
    [active, selectedSquareId],
  );
  const inspectorPairs = useMemo(
    () => (active && selectedSquareId !== null ? pairsForSquare(active.report, selectedSquareId) : []),
    [active, selectedSquareId],
  );
  const activePair = useMemo(
    () => active?.report.pairs.find((pair) => pairKey(pair) === selectedPairKey) ?? null,
    [active, selectedPairKey],
  );
  const pairSquareIds = useMemo(() => (activePair ? [activePair.first, activePair.second] : []), [activePair]);
  const warningSquareIds = useMemo(
    () =>
      new Set(
        active?.report.pairs
          .filter((pair) => pair.status === 'overlapping')
          .flatMap((pair) => [pair.first, pair.second]) ?? [],
      ),
    [active],
  );
  const contactSquareIds = useMemo(
    () =>
      new Set(
        active?.report.pairs
          .filter((pair) => pair.status === 'undecided')
          .flatMap((pair) => [pair.first, pair.second]) ?? [],
      ),
    [active],
  );
  const renderOptions = useMemo<RenderOptions>(
    () => ({ ...display, selectedSquareId, pairSquareIds, warningSquareIds, contactSquareIds }),
    [display, selectedSquareId, pairSquareIds, warningSquareIds, contactSquareIds],
  );

  useEffect(() => {
    document.documentElement.dataset.motion = reducedMotion ? 'reduced' : 'full';
  }, [reducedMotion]);

  useEffect(() => {
    if (!active || viewport.width === 0 || viewport.height === 0) return;
    setCamera(fitBounds(active.layout.bounds, viewport));
  }, [active, viewport, fitToken]);

  const applyText = useCallback((text: string, sourceName: string) => {
    setIsParsing(true);
    setParseError(null);
    window.setTimeout(() => {
      const result = parseSubmissionFile(text, sourceName);
      if (result.submission) {
        setSubmission(result.submission);
        setActiveN(result.submission.puzzleSizes[0] ?? null);
        setSelectedSquareId(null);
        setSelectedPairKey(null);
        setStatus(null);
      } else {
        setSubmission(null);
        setActiveN(null);
        setParseError(result.error ?? '未知解析错误');
      }
      setIsParsing(false);
    }, 0);
  }, []);

  const handleFile = useCallback(
    (file: File) => {
      setIsParsing(true);
      setParseError(null);
      file
        .text()
        .then((text) => applyText(text, file.name))
        .catch((error: unknown) => {
          setParseError(error instanceof Error ? error.message : '无法读取文件');
          setIsParsing(false);
        });
    },
    [applyText],
  );

  const handleDemo = useCallback(() => applyText(demoCsv(), '示例布局.csv'), [applyText]);
  const handleGrid = useCallback(() => applyText(gridCsv(1000), 'grid-1000.csv'), [applyText]);

  const handleClear = useCallback(() => {
    setSubmission(null);
    setParseError(null);
    setActiveN(null);
    setSelectedSquareId(null);
    setSelectedPairKey(null);
    setStatus(null);
  }, []);

  const handleViewportChange = useCallback((next: ViewportSize) => {
    setViewport((current) =>
      current.width === next.width && current.height === next.height ? current : next,
    );
  }, []);

  const handleSelectPuzzle = useCallback((n: number) => {
    setActiveN(n);
    setSelectedSquareId(null);
    setSelectedPairKey(null);
  }, []);

  const handleSelectSquare = useCallback((squareId: number | null) => {
    setSelectedSquareId(squareId);
    setSelectedPairKey(null);
  }, []);

  const handleToggleDisplay = useCallback((key: keyof DisplayOptions) => {
    setDisplay((current) => ({ ...current, [key]: !current[key] }));
  }, []);

  const handleResetView = useCallback(() => setFitToken((token) => token + 1), []);

  const handleFocusSquare = useCallback(
    (squareId: number) => {
      if (!active) return;
      const square = active.layout.squares.find((item) => item.squareId === squareId);
      if (!square) return;
      setSelectedSquareId(squareId);
      setSelectedPairKey(null);
      setCamera((current) => centerCamera(current, { x: square.pose.x, y: square.pose.y }, viewport));
    },
    [active, viewport],
  );

  const handleFocusPair = useCallback(
    (pair: OverlapPair) => {
      if (!active) return;
      const first = active.layout.squares.find((square) => square.squareId === pair.first);
      const second = active.layout.squares.find((square) => square.squareId === pair.second);
      if (!first || !second) return;
      setSelectedPairKey(pairKey(pair));
      setSelectedSquareId(null);
      const region = unionBounds([first.bounds, second.bounds]);
      if (region && viewport.width > 0 && viewport.height > 0) setCamera(focusRegion(region, viewport));
    },
    [active, viewport],
  );

  const handleExportCsv = useCallback(() => {
    if (!active) return;
    const filename = `squares-n${active.layout.n}.csv`;
    downloadTextFile(puzzleToCsv(active.layout), filename);
    setStatus(`已导出 ${filename}（原始十进制字符串，仅含 n=${active.layout.n}）`);
  }, [active]);

  const handleExportPng = useCallback(() => {
    if (!active) return;
    const canvas = canvasRef.current;
    if (!canvas) {
      setStatus('PNG 导出失败：画布尚未就绪');
      return;
    }
    const filename = `squares-n${active.layout.n}.png`;
    downloadCanvasPng(canvas, filename)
      .then(() => setStatus(`已导出 ${filename}`))
      .catch((error: unknown) => setStatus(error instanceof Error ? error.message : 'PNG 导出失败'));
  }, [active]);

  return (
    <div className="flex min-h-dvh flex-col bg-slate-950 text-slate-200 lg:h-dvh lg:overflow-hidden">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-slate-800 px-3 py-2 lg:px-4">
        <div className="min-w-0">
          <h1 className="truncate text-sm font-semibold tracking-wide text-slate-100">
            Squares in Squares · 布局调试
          </h1>
          <p className="truncate text-xs text-slate-400">
            {submission
              ? `${submission.sourceName} · ${submission.rowCount} 行 · ${submission.puzzleSizes.length} 题`
              : '未加载文件'}
            {isParsing ? ' · 解析中…' : ''}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <label className="flex min-h-11 items-center gap-2 rounded border border-slate-700 px-2 text-xs text-slate-300 sm:min-h-9">
            <input
              type="checkbox"
              checked={reducedMotion}
              onChange={(event) => setReducedMotion(event.target.checked)}
              className="size-4"
            />
            减少动效
          </label>
        </div>
      </header>

      <p className="border-b border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-[11px] text-amber-200 lg:px-4">
        浏览器结果仅用于调试。最终合法性由项目 Python 高精度判别器认证。
      </p>

      <main className="grid min-h-0 flex-1 gap-2 p-2 lg:grid-cols-[minmax(0,17rem)_minmax(0,1fr)_minmax(0,22rem)] lg:gap-3 lg:overflow-hidden lg:p-3">
        {submission ? (
          <>
            <div className="order-2 flex min-h-0 min-w-0 flex-col gap-2 lg:order-1">
              <SubmissionDropzone
                compact
                isParsing={isParsing}
                error={parseError}
                sourceName={submission.sourceName}
                onFile={handleFile}
                onDemo={handleDemo}
                onGrid={handleGrid}
                onClear={handleClear}
              />
              <PuzzleNavigator
                summaries={summaries}
                totals={totals}
                fileIssues={submission.fileIssues}
                activeN={activeN}
                onSelect={handleSelectPuzzle}
              />
            </div>

            <div className="order-1 flex min-h-0 min-w-0 flex-col gap-2 lg:order-2">
              <MetricsPanel
                summary={active ? active.summary : null}
                issues={active ? active.layout.issues : []}
                status={status}
                onExportPng={handleExportPng}
                onExportCsv={handleExportCsv}
              />
              <section className="flex min-h-0 flex-1 flex-col rounded-lg border border-slate-800 bg-[#0b0f16] p-2">
                <LayoutCanvas
                  layout={active ? active.layout : null}
                  camera={camera}
                  display={display}
                  renderOptions={renderOptions}
                  canvasRef={canvasRef}
                  onCameraChange={setCamera}
                  onViewportChange={handleViewportChange}
                  onSelectSquare={handleSelectSquare}
                  onToggleDisplay={handleToggleDisplay}
                  onResetView={handleResetView}
                />
              </section>
            </div>

            <div className="order-3 flex min-h-0 min-w-0 flex-col gap-2 lg:overflow-y-auto">
              <Panel title="正方形检查器" scroll={false}>
                <SquareInspector
                  layout={active ? active.layout : null}
                  square={selectedSquare}
                  pairs={inspectorPairs}
                  onCenter={handleFocusSquare}
                />
              </Panel>
              <Panel title="快速重叠检查" scroll={false}>
                <OverlapPanel
                  report={active ? active.report : null}
                  selectedPairKey={selectedPairKey}
                  onFocusPair={handleFocusPair}
                />
              </Panel>
            </div>
          </>
        ) : (
          <div className="min-w-0 lg:col-span-3">
            <SubmissionDropzone
              isParsing={isParsing}
              error={parseError}
              sourceName={null}
              onFile={handleFile}
              onDemo={handleDemo}
              onGrid={handleGrid}
              onClear={handleClear}
            />
          </div>
        )}
      </main>
    </div>
  );
}
