export const DECIMAL_LITERAL = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/;
export const MAX_LITERAL_LENGTH = 100;
export const MAX_COORDINATE_MAGNITUDE = 1e4;
export const MAX_ANGLE_MAGNITUDE = 100;

export type LiteralProblem = 'empty' | 'syntax' | 'range';

export type LiteralResult =
  | { ok: true; value: number }
  | { ok: false; problem: LiteralProblem; message: string };

export function parseDecimalLiteral(raw: string): LiteralResult {
  const literal = raw.trim();
  if (literal.length === 0) return { ok: false, problem: 'empty', message: '缺少数值' };
  if (literal.length > MAX_LITERAL_LENGTH) {
    return { ok: false, problem: 'syntax', message: `字面量超过 ${MAX_LITERAL_LENGTH} 字符` };
  }
  if (!DECIMAL_LITERAL.test(literal)) return { ok: false, problem: 'syntax', message: '不是十进制字面量' };
  const value = Number(literal);
  if (!Number.isFinite(value)) return { ok: false, problem: 'range', message: '超出双精度范围' };
  return { ok: true, value };
}

export function formatDecimal(value: number, digits = 6): string {
  return Number.isFinite(value) ? value.toFixed(digits) : String(value);
}
