import { aabbCenter } from '../domain/geometry';
import type { Aabb, Camera, LayoutBounds, Vertex, ViewportSize } from '../domain/types';

export const MIN_SCALE = 0.25;
export const MAX_SCALE = 4000;
export const CANVAS_PADDING = 36;
export const WHEEL_ZOOM_FACTOR = 1.15;
export const PAN_DRAG_THRESHOLD = 3;

export function clampScale(scale: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale));
}

export function worldToScreen(camera: Camera, point: Vertex): Vertex {
  return { x: point.x * camera.scale + camera.offsetX, y: camera.offsetY - point.y * camera.scale };
}

export function screenToWorld(camera: Camera, point: Vertex): Vertex {
  return { x: (point.x - camera.offsetX) / camera.scale, y: (camera.offsetY - point.y) / camera.scale };
}

export function panCamera(camera: Camera, deltaX: number, deltaY: number): Camera {
  return { ...camera, offsetX: camera.offsetX + deltaX, offsetY: camera.offsetY + deltaY };
}

export function zoomAt(camera: Camera, anchor: Vertex, factor: number): Camera {
  const scale = clampScale(camera.scale * factor);
  const world = screenToWorld(camera, anchor);
  return { scale, offsetX: anchor.x - world.x * scale, offsetY: anchor.y + world.y * scale };
}

export function centerCamera(camera: Camera, point: Vertex, viewport: ViewportSize): Camera {
  return {
    scale: camera.scale,
    offsetX: viewport.width / 2 - point.x * camera.scale,
    offsetY: viewport.height / 2 + point.y * camera.scale,
  };
}

/** 等比例适配：用 min(宽,高) 计算比例尺，因此 x/y 不会拉伸。 */
export function fitBounds(bounds: LayoutBounds | null, viewport: ViewportSize, padding = CANVAS_PADDING): Camera {
  const center = bounds ? aabbCenter(bounds.aabb) : { x: 0, y: 0 };
  const side = bounds ? Math.max(bounds.sideLength, 1e-6) : 1;
  const available = Math.max(1, Math.min(viewport.width, viewport.height) - 2 * padding);
  return centerCamera({ scale: clampScale(available / side), offsetX: 0, offsetY: 0 }, center, viewport);
}

/** pair 跳转：让该区域约占视口 1/2.5，避免两个正方形贴在边缘。 */
export function focusRegion(region: Aabb, viewport: ViewportSize, padding = CANVAS_PADDING): Camera {
  const span = Math.max(region.maxX - region.minX, region.maxY - region.minY, 0.25);
  const available = Math.max(1, Math.min(viewport.width, viewport.height) - 2 * padding);
  return centerCamera({ scale: clampScale(available / (span * 2.5)), offsetX: 0, offsetY: 0 }, aabbCenter(region), viewport);
}
