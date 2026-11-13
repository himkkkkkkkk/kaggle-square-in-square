export const CSV_HEADER = 'n,square_id,x,y,angle';

export interface GridSquare {
  squareId: number;
  x: number;
  y: number;
}

export function gridSquares(n: number, offsetX = 0, offsetY = 0): GridSquare[] {
  const columns = Math.ceil(Math.sqrt(n));
  return Array.from({ length: n }, (_, index) => ({
    squareId: index,
    x: offsetX + (index % columns) + 0.5,
    y: offsetY + Math.floor(index / columns) + 0.5,
  }));
}

function formatCoordinate(value: number): string {
  return Object.is(value, -0) ? '0' : String(value);
}

/** 解析 √n × √n 网格：n=1 得 L=1、n=4 得 L=2、n=1000 得 L=32。 */
export function gridCsv(n: number, offsetX = 0, offsetY = 0): string {
  const rows = gridSquares(n, offsetX, offsetY).map(
    (square) => `${n},${square.squareId},${formatCoordinate(square.x)},${formatCoordinate(square.y)},0`,
  );
  return [CSV_HEADER, ...rows].join('\n') + '\n';
}

export function singleSquareCsv(angle: number): string {
  return [CSV_HEADER, `1,0,0,0,${formatCoordinate(angle)}`].join('\n') + '\n';
}

export function twoSquaresCsv(secondX: number): string {
  return [CSV_HEADER, '2,0,0,0,0', `2,1,${formatCoordinate(secondX)},0,0`].join('\n') + '\n';
}

/** 多题示例：n=5 含一对明显重叠，n=9 中心旋转 45°，n=16 使用科学计数法。 */
export function demoCsv(): string {
  const scientific = gridSquares(16)
    .map((square) => `16,${square.squareId},${square.x.toExponential(1)},${square.y.toExponential(1)},0e0`)
    .join('\n');
  const rows = [
    '1,0,0.5,0.5,0',
    '2,0,0.5,0.5,0',
    '2,1,1.5,0.5,0',
    '4,0,0.5,0.5,0',
    '4,1,1.5,0.5,0',
    '4,2,0.5,1.5,0',
    '4,3,1.5,1.5,0',
    '5,0,0.5,0.5,0',
    '5,1,0.7,0.5,0',
    '5,2,2.5,0.5,0',
    '5,3,0.5,2.5,0',
    '5,4,2.5,2.5,0',
    '9,0,0.5,0.5,0',
    '9,1,1.5,0.5,0',
    '9,2,2.5,0.5,0',
    '9,3,0.5,1.5,0',
    '9,4,1.5,1.5,0.7853981633974483',
    '9,5,2.5,1.5,0',
    '9,6,0.5,2.5,0',
    '9,7,1.5,2.5,0',
    '9,8,2.5,2.5,0',
    scientific,
  ].join('\n');
  return `${CSV_HEADER}\n${rows}\n`;
}
