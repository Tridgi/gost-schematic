/** Strict display mm -> authoritative signed integer micrometres, no floating-point rounding. */
export const MAX_POINT_UM = 1_000_000_000;
export type ParseResult = { ok: true; um: number } | { ok: false; code: 'EMPTY' | 'INVALID_FORMAT' | 'PRECISION' | 'OUT_OF_RANGE' };

export function parseMillimetres(raw: string): ParseResult {
  const s=raw.trim().replace(',', '.');
  if (!s) return {ok:false,code:'EMPTY'};
  if (!/^[+-]?(?:\d+)(?:\.\d+)?$/.test(s)) return {ok:false,code:'INVALID_FORMAT'};
  const positive=s[0]!=='-';
  const unsigned=/^[+-]/.test(s)?s.slice(1):s;
  const [whole,fractional='']=unsigned.split('.');
  if (fractional.length>3) return {ok:false,code:'PRECISION'};
  const magnitude=BigInt(whole)*1000n+BigInt(fractional.padEnd(3,'0')||'0');
  const signed=positive?magnitude:-magnitude;
  if(signed>BigInt(MAX_POINT_UM)||signed<-BigInt(MAX_POINT_UM)) return {ok:false,code:'OUT_OF_RANGE'};
  return {ok:true,um:Number(signed)};
}

export function formatMillimetres(um: number): string {
  if (!Number.isSafeInteger(um)||Math.abs(um)>MAX_POINT_UM) throw new RangeError('expected signed integer µm');
  const sign=um<0?'-':'';
  const abs=Math.abs(um);
  return sign+Math.floor(abs/1000)+'.'+String(abs%1000).padStart(3,'0');
}
