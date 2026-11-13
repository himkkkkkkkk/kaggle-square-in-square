import { describe, expect, it } from 'vitest';
import { MAX_SCALE, MIN_SCALE, centerCamera, fitBounds, panCamera, screenToWorld, worldToScreen, zoomAt } from '../canvas/camera';
import { boundsFromAabb } from '../domain/geometry';

const wide = { width: 800, height: 400 };
const tall = { width: 400, height: 800 };

describe('相机变换', () => {
  it('适配保持等比例：宽高互换得到同一比例尺', () => {
    const bounds = boundsFromAabb({ minX: -1, minY: -1, maxX: 1, maxY: 1 });
    expect(fitBounds(bounds, wide).scale).toBeCloseTo(fitBounds(bounds, tall).scale, 12);
  });

  it('适配后容器位于视口中心', () => {
    const bounds = boundsFromAabb({ minX: 0, minY: 0, maxX: 2, maxY: 2 });
    const camera = fitBounds(bounds, wide);
    const center = worldToScreen(camera, { x: 1, y: 1 });
    expect(center.x).toBeCloseTo(wide.width / 2, 9);
    expect(center.y).toBeCloseTo(wide.height / 2, 9);
  });

  it('滚轮缩放时锚点世界坐标不动', () => {
    const camera = { scale: 50, offsetX: 400, offsetY: 300 };
    const anchor = { x: 520, y: 260 };
    const before = screenToWorld(camera, anchor);
    const after = worldToScreen(zoomAt(camera, anchor, 1.15), before);
    expect(after.x).toBeCloseTo(anchor.x, 9);
    expect(after.y).toBeCloseTo(anchor.y, 9);
  });

  it('缩放钳制在上下限内', () => {
    let camera = { scale: MAX_SCALE, offsetX: 0, offsetY: 0 };
    camera = zoomAt(camera, { x: 0, y: 0 }, 10);
    expect(camera.scale).toBe(MAX_SCALE);
    camera = zoomAt(camera, { x: 0, y: 0 }, 1e-12);
    expect(camera.scale).toBe(MIN_SCALE);
  });

  it('平移只改变偏移量，不改变比例尺', () => {
    const camera = { scale: 40, offsetX: 10, offsetY: 20 };
    const panned = panCamera(camera, 25, -15);
    expect(panned.scale).toBe(camera.scale);
    const before = worldToScreen(camera, { x: 1, y: 2 });
    const after = worldToScreen(panned, { x: 1, y: 2 });
    expect(after.x).toBeCloseTo(before.x + 25, 12);
    expect(after.y).toBeCloseTo(before.y - 15, 12);
  });

  it('居中把世界点放到视口中心', () => {
    const camera = centerCamera({ scale: 30, offsetX: 0, offsetY: 0 }, { x: 2.5, y: -1.5 }, wide);
    const screen = worldToScreen(camera, { x: 2.5, y: -1.5 });
    expect(screen.x).toBeCloseTo(wide.width / 2, 9);
    expect(screen.y).toBeCloseTo(wide.height / 2, 9);
  });
});
