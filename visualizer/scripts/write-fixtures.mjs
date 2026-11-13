// 生成可直接拖入浏览器的 CSV 夹具：node scripts/write-fixtures.mjs
// 应用内的「示例布局 / n=1000 网格夹具」按钮使用 src/domain/fixtures.ts 的同一套生成逻辑，
// 因此应用不依赖本脚本产物；本脚本只为手工拖放验收提供真实文件。
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const outputDir = join(dirname(fileURLToPath(import.meta.url)), '..', 'fixtures');
const HEADER = 'n,square_id,x,y,angle';

function gridCsv(n) {
  const columns = Math.ceil(Math.sqrt(n));
  const rows = Array.from({ length: n }, (_, index) => {
    const x = (index % columns) + 0.5;
    const y = Math.floor(index / columns) + 0.5;
    return `${n},${index},${x},${y},0`;
  });
  return [HEADER, ...rows].join('\n') + '\n';
}

const scientific = Array.from({ length: 16 }, (_, index) => {
  const x = (index % 4) + 0.5;
  const y = Math.floor(index / 4) + 0.5;
  return `16,${index},${x.toExponential(1)},${y.toExponential(1)},0e0`;
});

const demo = [
  HEADER,
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
  ...scientific,
].join('\n');

await mkdir(outputDir, { recursive: true });
await writeFile(join(outputDir, 'demo.csv'), `${demo}\n`, 'utf8');
await writeFile(join(outputDir, 'grid-1000.csv'), gridCsv(1000), 'utf8');
console.log(`wrote ${join(outputDir, 'demo.csv')} and ${join(outputDir, 'grid-1000.csv')}`);
