import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent, RefObject } from 'react';
import { PAN_DRAG_THRESHOLD, WHEEL_ZOOM_FACTOR, panCamera, screenToWorld, zoomAt } from '../canvas/camera';
import { pickSquare } from '../canvas/hitTest';
import { CANVAS_BACKGROUND, renderLayout } from '../canvas/renderer';
import type { DisplayOptions, RenderOptions } from '../canvas/renderer';
import type { Camera, PuzzleLayout, ViewportSize } from '../domain/types';

interface LayoutCanvasProps {
  layout: PuzzleLayout | null;
  camera: Camera;
  display: DisplayOptions;
  renderOptions: RenderOptions;
  canvasRef: RefObject<HTMLCanvasElement | null>;
  onCameraChange: (camera: Camera) => void;
  onViewportChange: (viewport: ViewportSize) => void;
  onSelectSquare: (squareId: number | null) => void;
  onToggleDisplay: (key: keyof DisplayOptions) => void;
  onResetView: () => void;
}

interface DragState {
  pointerId: number;
  startX: number;
  startY: number;
  lastX: number;
  lastY: number;
  moved: boolean;
}

const TOGGLES: { key: keyof DisplayOptions; label: string }[] = [
  { key: 'showIds', label: '编号' },
  { key: 'showVertices', label: '顶点' },
  { key: 'showBounds', label: '包围框' },
  { key: 'showAxes', label: '坐标轴' },
];

export function LayoutCanvas({
  layout,
  camera,
  display,
  renderOptions,
  canvasRef,
  onCameraChange,
  onViewportChange,
  onSelectSquare,
  onToggleDisplay,
  onResetView,
}: LayoutCanvasProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const cameraRef = useRef(camera);
  const dragRef = useRef<DragState | null>(null);
  const [size, setSize] = useState<ViewportSize>({ width: 0, height: 0 });
  const [isPanning, setIsPanning] = useState(false);

  useEffect(() => {
    cameraRef.current = camera;
  }, [camera]);

  useLayoutEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const next = {
        width: Math.max(1, Math.round(entry.contentRect.width)),
        height: Math.max(1, Math.round(entry.contentRect.height)),
      };
      setSize((current) => (current.width === next.width && current.height === next.height ? current : next));
      onViewportChange(next);
    });
    observer.observe(host);
    return () => observer.disconnect();
  }, [onViewportChange]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || size.width === 0 || size.height === 0) return;
    const ratio = Math.min(window.devicePixelRatio || 1, 3);
    canvas.width = Math.round(size.width * ratio);
    canvas.height = Math.round(size.height * ratio);
    const context = canvas.getContext('2d');
    if (!context) return;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    if (layout) {
      renderLayout(context, layout, camera, size, renderOptions);
    } else {
      context.fillStyle = CANVAS_BACKGROUND;
      context.fillRect(0, 0, size.width, size.height);
    }
  }, [layout, camera, size, renderOptions, canvasRef]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const anchor = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      const factor = event.deltaY < 0 ? WHEEL_ZOOM_FACTOR : 1 / WHEEL_ZOOM_FACTOR;
      onCameraChange(zoomAt(cameraRef.current, anchor, factor));
    };
    canvas.addEventListener('wheel', handleWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', handleWheel);
  }, [canvasRef, onCameraChange]);

  const handlePointerDown = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    if (event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      lastX: event.clientX,
      lastY: event.clientY,
      moved: false,
    };
  };

  const handlePointerMove = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const deltaX = event.clientX - drag.lastX;
    const deltaY = event.clientY - drag.lastY;
    drag.lastX = event.clientX;
    drag.lastY = event.clientY;
    if (Math.abs(event.clientX - drag.startX) + Math.abs(event.clientY - drag.startY) > PAN_DRAG_THRESHOLD) {
      drag.moved = true;
      setIsPanning(true);
    }
    if (drag.moved) onCameraChange(panCamera(cameraRef.current, deltaX, deltaY));
  };

  const handlePointerUp = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    dragRef.current = null;
    setIsPanning(false);
    if (drag.moved || !layout) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const world = screenToWorld(cameraRef.current, { x: event.clientX - rect.left, y: event.clientY - rect.top });
    onSelectSquare(pickSquare(layout, world));
  };

  const handlePointerCancel = () => {
    dragRef.current = null;
    setIsPanning(false);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="flex flex-wrap items-center gap-1.5">
        {TOGGLES.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            aria-pressed={display[key]}
            onClick={() => onToggleDisplay(key)}
            className={`min-h-11 rounded border px-2 text-xs transition-colors duration-100 sm:min-h-8 ${
              display[key]
                ? 'border-slate-600 bg-slate-800 text-slate-100'
                : 'border-slate-800 text-slate-500 hover:bg-slate-800/60'
            }`}
          >
            {label}
          </button>
        ))}
        <span className="mx-1 hidden h-5 w-px bg-slate-800 sm:block" aria-hidden="true" />
        <button
          type="button"
          onClick={onResetView}
          className="min-h-11 rounded border border-slate-700 px-2 text-xs text-sky-300 transition-colors duration-100 hover:bg-slate-800 sm:min-h-8"
        >
          重置视图
        </button>
      </div>
      <div ref={hostRef} className="relative min-h-64 flex-1 overflow-hidden rounded">
        <canvas
          ref={canvasRef}
          role="img"
          aria-label="布局画布：滚轮缩放，拖动平移，点击正方形查看详情，双击重置视图"
          className={`absolute inset-0 h-full w-full touch-none ${isPanning ? 'cursor-grabbing' : 'cursor-crosshair'}`}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerCancel}
          onDoubleClick={onResetView}
        />
        <p className="pointer-events-none absolute bottom-2 left-2 rounded bg-slate-950/80 px-2 py-1 text-[11px] text-slate-400">
          滚轮缩放 · 拖动平移 · 双击重置 · 点击选中
        </p>
      </div>
    </div>
  );
}
