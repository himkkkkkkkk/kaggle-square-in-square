import { screenToWorld, worldToScreen } from './camera';
import type { Camera, LayoutBounds, PuzzleLayout, Quad, ViewportSize } from '../domain/types';

export interface DisplayOptions {
  showIds: boolean;
  showVertices: boolean;
  showBounds: boolean;
  showAxes: boolean;
}

export interface RenderOptions extends DisplayOptions {
  selectedSquareId: number | null;
  pairSquareIds: readonly number[];
  warningSquareIds: ReadonlySet<number>;
  contactSquareIds: ReadonlySet<number>;
}

export const CANVAS_BACKGROUND = '#0b0f16';
const GRID_COLOR = '#1a2330';
const AXIS_COLOR = '#37506f';
const BOUNDS_COLOR = '#5c7396';
const SQUARE_FILL = 'rgba(96, 140, 214, 0.14)';
const SQUARE_STROKE = '#6f9ee6';
const WARNING_STROKE = '#c98a3a';
const CONTACT_STROKE = '#8a6f3f';
const SELECTED_FILL = 'rgba(99, 224, 166, 0.26)';
const SELECTED_STROKE = '#63e0a6';
const PAIR_FILL = 'rgba(255, 179, 71, 0.3)';
const PAIR_STROKE = '#ffb347';
const VERTEX_COLOR = '#e2e8f0';
const LABEL_COLOR = '#c7d3e5';
const GRID_STEPS = [0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000];
const MIN_GRID_PIXELS = 48;
const MAX_GRID_LINES = 400;
const VERTEX_RADIUS = 2.5;
const LABEL_FONT = '11px ui-monospace, SFMono-Regular, Menlo, monospace';

export function renderLayout(
  context: CanvasRenderingContext2D,
  layout: PuzzleLayout,
  camera: Camera,
  viewport: ViewportSize,
  options: RenderOptions,
): void {
  context.fillStyle = CANVAS_BACKGROUND;
  context.fillRect(0, 0, viewport.width, viewport.height);

  if (options.showAxes) drawAxes(context, camera, viewport);
  if (options.showBounds && layout.bounds) drawEnclosingSquare(context, layout.bounds, camera);

  const pairIds = new Set(options.pairSquareIds);
  for (const square of layout.squares) {
    const selected = square.squareId === options.selectedSquareId;
    const inPair = pairIds.has(square.squareId);
    const warning = options.warningSquareIds.has(square.squareId);
    const contact = options.contactSquareIds.has(square.squareId);

    traceQuad(context, square.quad, camera);
    context.fillStyle = selected ? SELECTED_FILL : inPair ? PAIR_FILL : SQUARE_FILL;
    context.fill();
    context.lineWidth = selected || inPair ? 2.4 : 1;
    context.strokeStyle = selected
      ? SELECTED_STROKE
      : inPair
        ? PAIR_STROKE
        : warning
          ? WARNING_STROKE
          : contact
            ? CONTACT_STROKE
            : SQUARE_STROKE;
    context.setLineDash(contact && !selected && !inPair && !warning ? [4, 3] : []);
    context.stroke();
  }
  context.setLineDash([]);

  if (options.showVertices) drawVertices(context, layout, camera);
  if (options.showIds) drawLabels(context, layout, camera);
}

function traceQuad(context: CanvasRenderingContext2D, quad: Quad, camera: Camera): void {
  context.beginPath();
  for (let index = 0; index < quad.length; index += 1) {
    const point = worldToScreen(camera, quad[index]);
    if (index === 0) context.moveTo(point.x, point.y);
    else context.lineTo(point.x, point.y);
  }
  context.closePath();
}

function gridStep(scale: number): number {
  for (const step of GRID_STEPS) {
    if (step * scale >= MIN_GRID_PIXELS) return step;
  }
  return GRID_STEPS[GRID_STEPS.length - 1];
}

function drawAxes(context: CanvasRenderingContext2D, camera: Camera, viewport: ViewportSize): void {
  const step = gridStep(camera.scale);
  const topLeft = screenToWorld(camera, { x: 0, y: 0 });
  const bottomRight = screenToWorld(camera, { x: viewport.width, y: viewport.height });
  const minX = Math.min(topLeft.x, bottomRight.x);
  const maxX = Math.max(topLeft.x, bottomRight.x);
  const minY = Math.min(topLeft.y, bottomRight.y);
  const maxY = Math.max(topLeft.y, bottomRight.y);

  context.save();
  context.lineWidth = 1;
  context.strokeStyle = GRID_COLOR;
  context.beginPath();
  const firstColumn = Math.ceil(minX / step);
  const lastColumn = Math.floor(maxX / step);
  for (let column = firstColumn; column <= lastColumn && column - firstColumn <= MAX_GRID_LINES; column += 1) {
    const screenX = Math.round(worldToScreen(camera, { x: column * step, y: 0 }).x) + 0.5;
    context.moveTo(screenX, 0);
    context.lineTo(screenX, viewport.height);
  }
  const firstRow = Math.ceil(minY / step);
  const lastRow = Math.floor(maxY / step);
  for (let row = firstRow; row <= lastRow && row - firstRow <= MAX_GRID_LINES; row += 1) {
    const screenY = Math.round(worldToScreen(camera, { x: 0, y: row * step }).y) + 0.5;
    context.moveTo(0, screenY);
    context.lineTo(viewport.width, screenY);
  }
  context.stroke();

  const origin = worldToScreen(camera, { x: 0, y: 0 });
  context.strokeStyle = AXIS_COLOR;
  context.beginPath();
  context.moveTo(0, Math.round(origin.y) + 0.5);
  context.lineTo(viewport.width, Math.round(origin.y) + 0.5);
  context.moveTo(Math.round(origin.x) + 0.5, 0);
  context.lineTo(Math.round(origin.x) + 0.5, viewport.height);
  context.stroke();
  context.restore();
}

function drawEnclosingSquare(context: CanvasRenderingContext2D, bounds: LayoutBounds, camera: Camera): void {
  const centerX = (bounds.aabb.minX + bounds.aabb.maxX) / 2;
  const centerY = (bounds.aabb.minY + bounds.aabb.maxY) / 2;
  const half = bounds.sideLength / 2;
  const topLeft = worldToScreen(camera, { x: centerX - half, y: centerY + half });
  const bottomRight = worldToScreen(camera, { x: centerX + half, y: centerY - half });

  context.save();
  context.setLineDash([6, 4]);
  context.strokeStyle = BOUNDS_COLOR;
  context.lineWidth = 1;
  context.strokeRect(
    Math.round(topLeft.x) + 0.5,
    Math.round(topLeft.y) + 0.5,
    Math.round(bottomRight.x - topLeft.x),
    Math.round(bottomRight.y - topLeft.y),
  );
  context.setLineDash([]);
  context.fillStyle = BOUNDS_COLOR;
  context.font = LABEL_FONT;
  context.fillText(`L=${bounds.sideLength.toFixed(4)}`, topLeft.x + 4, topLeft.y - 6);
  context.restore();
}

function drawVertices(context: CanvasRenderingContext2D, layout: PuzzleLayout, camera: Camera): void {
  context.save();
  context.fillStyle = VERTEX_COLOR;
  context.beginPath();
  for (const square of layout.squares) {
    for (const vertex of square.quad) {
      const point = worldToScreen(camera, vertex);
      context.moveTo(point.x + VERTEX_RADIUS, point.y);
      context.arc(point.x, point.y, VERTEX_RADIUS, 0, Math.PI * 2);
    }
  }
  context.fill();
  context.restore();
}

function drawLabels(context: CanvasRenderingContext2D, layout: PuzzleLayout, camera: Camera): void {
  context.save();
  context.fillStyle = LABEL_COLOR;
  context.font = LABEL_FONT;
  context.textAlign = 'center';
  context.textBaseline = 'middle';
  for (const square of layout.squares) {
    const point = worldToScreen(camera, { x: square.pose.x, y: square.pose.y });
    context.fillText(String(square.squareId), point.x, point.y);
  }
  context.restore();
}
